"""API publica del modulo expediente: crear, consultar y listar folios (ADR-005: solo esto se importa)."""
import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as insert_postgresql
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.config import get_settings
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Correccion, Documento, Folio, Proceso, Resultado, SecuenciaFolio
from app.modulos.configuracion import servicio as configuracion
from app.modulos.ingesta import servicio as ingesta
from app.modulos.expediente.recomendacion import DocumentoParaRecomendar, calcular_recomendacion_global
from app.modulos.validacion import servicio as validacion
from app.schemas.resultado import (Alerta, ComparacionCampo, DecisionHumana, EstadoAnalisis, EstadoGeneral,
                                   Recomendacion, ResultadoDocumento, ResultadoExpediente, ResumenFolio,
                                   Severidad)

MAX_SECUENCIA = 999_999  # NNNNNN


def _siguiente_secuencia(sesion: Session, proceso: str, anio: int) -> int:
    """Siguiente numero de (proceso, anio) con una sola sentencia: atomico sin FOR UPDATE."""
    insert = insert_postgresql if sesion.get_bind().dialect.name == "postgresql" else insert_sqlite
    sentencia = (
        insert(SecuenciaFolio)
        .values(proceso=proceso, anio=anio, ultimo=1)
        .on_conflict_do_update(index_elements=["proceso", "anio"],
                               set_={"ultimo": SecuenciaFolio.ultimo + 1})
        .returning(SecuenciaFolio.ultimo)
    )
    return sesion.execute(sentencia).scalar_one()


def _crear_exp001(sesion: Session, folio: str, tipo: str) -> None:
    """Alerta de expediente (documento_id NULL) por un tipo requerido que falta en el folio."""
    sesion.add(AlertaBD(folio=folio, documento_id=None, codigo="EXP-001",
                        severidad=Severidad.bloqueante.value, confianza=1.0, campo=tipo,
                        mensaje=f"Falta el documento requerido: {ingesta.nombre_visible_tipo(tipo)}"))


# Dos criterios distintos de "tipo" de un documento; no se mezclan:
# - tipo EFECTIVO (confirmado > detectado > declarado): que documento ES. Lo usan EXP-001, EXP-002,
#   las comparaciones y la recomendacion.
# - tipo de EXTRACCION (confirmado > declarado > detectado, ADR-006 2.5): con que ficha se extrajeron
#   los datos. Lo usan corregir_datos (validar campos) y confirmar_clasificacion (reproceso o no).

def _tipo_efectivo(sesion: Session, documento: Documento) -> str | None:
    """Tipo EFECTIVO: confirmado por el revisor > detectado en el resultado vigente > declarado al subir."""
    if documento.tipo_documental_confirmado:
        return documento.tipo_documental_confirmado
    return _resultado_vigente(sesion, documento).get("tipo_documental_detectado") or documento.tipo_declarado


def recalcular_exp001(sesion: Session, folio: str) -> None:
    """Ajusta las EXP-001 del folio a los documentos `completado` que tiene. Sin commit; idempotente.

    Tipo presente: se borran sus EXP-001 sin revisar (`aplica` NULL) y las confirmadas (`aplica` True):
    la condicion ya no se da. Solo se conservan los falsos positivos (`aplica` False).
    Tipo que falta: se crea su EXP-001 si no hay ninguna de ese campo.
    Lo llaman el procesamiento de cada documento y confirmar_clasificacion.
    """
    sesion.flush()  # autoflush=False: ver los cambios pendientes de quien llama (estado, resultado)
    fila = sesion.get(Folio, folio)
    requeridos = sesion.get(Proceso, fila.proceso).tipos_requeridos or []
    if not requeridos:
        return

    completados = sesion.scalars(select(Documento).where(
        Documento.folio == folio, Documento.estado_analisis == EstadoAnalisis.completado.value))
    presentes = {_tipo_efectivo(sesion, d) for d in completados.all()}
    existentes = sesion.scalars(select(AlertaBD).where(
        AlertaBD.folio == folio, AlertaBD.documento_id.is_(None), AlertaBD.codigo == "EXP-001")).all()

    for tipo in requeridos:
        del_tipo = [a for a in existentes if a.campo == tipo]
        if tipo in presentes:
            for alerta in del_tipo:
                if alerta.aplica is not False:  # solo sobreviven los falsos positivos
                    sesion.delete(alerta)
        elif not del_tipo:
            _crear_exp001(sesion, folio, tipo)
    sesion.flush()  # para que una segunda llamada en la misma transaccion no duplique


def _mensaje_exp002(tipo: str) -> str:
    # ADR-009: "desconocido" (detectado sin ficha) no es un tipo "no previsto", sino uno no reconocido
    if tipo == configuracion.NOMBRE_RESERVADO:
        return "Tipo de documento no reconocido"
    return f"Tipo de documento no previsto en el proceso: {ingesta.nombre_visible_tipo(tipo)}"


def recalcular_exp002(sesion: Session, folio: str) -> None:
    """EXP-002 (informativa, de plataforma, EN EL DOCUMENTO) por cada documento `completado` cuyo tipo
    EFECTIVO no esta ni en `tipos_requeridos` ni en `tipos_opcionales` del proceso. Sin commit; idempotente.

    Si el tipo deja de ser no previsto (p. ej. al confirmar otro), se borran sus EXP-002 sin revisar o
    confirmadas; solo se conservan los falsos positivos (`aplica` False). No bloquea ni cambia la
    recomendacion (es informativa). Los documentos no completados no se tocan.
    """
    sesion.flush()  # autoflush=False: ver los cambios pendientes de quien llama
    proceso = sesion.get(Proceso, sesion.get(Folio, folio).proceso)
    previstos = set(proceso.tipos_requeridos or []) | set(proceso.tipos_opcionales or [])
    completados = sesion.scalars(select(Documento).where(
        Documento.folio == folio, Documento.estado_analisis == EstadoAnalisis.completado.value)).all()
    for doc in completados:
        tipo = _tipo_efectivo(sesion, doc)
        no_previsto = tipo if tipo and tipo not in previstos else None
        existentes = sesion.scalars(select(AlertaBD).where(
            AlertaBD.documento_id == doc.id, AlertaBD.codigo == "EXP-002")).all()
        for alerta in existentes:
            if alerta.campo != no_previsto and alerta.aplica is not False:  # solo falsos positivos
                sesion.delete(alerta)
        if no_previsto and not any(a.campo == no_previsto for a in existentes):
            sesion.add(AlertaBD(folio=folio, documento_id=doc.id, version_resultado=None, codigo="EXP-002",
                                severidad=Severidad.informativa.value, confianza=1.0, campo=no_previsto,
                                mensaje=_mensaje_exp002(no_previsto)))
    sesion.flush()  # para que una segunda llamada en la misma transaccion no duplique


def _tipo_extraccion(sesion: Session, documento: Documento) -> str | None:
    """Tipo de EXTRACCION (ADR-006 2.5): confirmado previo > declarado > detectado del resultado vigente."""
    return (documento.tipo_documental_confirmado or documento.tipo_declarado
            or _resultado_vigente(sesion, documento).get("tipo_documental_detectado"))


def _resultado_vigente(sesion: Session, documento: Documento) -> dict:
    return sesion.scalar(select(Resultado.json).where(Resultado.documento_id == documento.id)
                         .order_by(Resultado.version.desc()).limit(1)) or {}


def comparaciones_actuales(sesion: Session, folio: str) -> list[ComparacionCampo]:
    """Comparaciones entre los documentos `completado` del folio, calculadas al vuelo (no se guardan)."""
    completados = sesion.scalars(select(Documento).where(
        Documento.folio == folio, Documento.estado_analisis == EstadoAnalisis.completado.value)
        .order_by(Documento.creado_en, Documento.id)).all()
    # Con los datos ya corregidos por el revisor (construir_resultado aplica las correcciones)
    armados = [ingesta.construir_resultado(sesion, d) for d in completados]
    documentos = [validacion.DocumentoComparable(
        id=r.identificador_unico_documento,
        tipo=r.tipo_documental_confirmado or r.tipo_documental_detectado or r.tipo_documental_declarado,
        datos=r.datos_extraidos) for r in armados]
    return validacion.comparar(documentos, _fichas())


def recalcular_cmp001(sesion: Session, folio: str) -> None:
    """Una CMP-001 (critica, de expediente) por campo comparado que no coincide. Sin commit; idempotente.

    El mensaje lleva solo el nombre del campo, nunca los valores (son datos personales). En campos que
    ya coinciden o ya no se comparan se borran las CMP-001 sin revisar (`aplica` NULL) y las confirmadas
    (`aplica` True); solo se conservan los falsos positivos (`aplica` False).
    """
    sesion.flush()  # autoflush=False: ver los cambios pendientes de quien llama
    no_coinciden = {c.campo for c in comparaciones_actuales(sesion, folio) if not c.coincide}
    existentes = sesion.scalars(select(AlertaBD).where(
        AlertaBD.folio == folio, AlertaBD.documento_id.is_(None), AlertaBD.codigo == "CMP-001")).all()

    for alerta in existentes:
        if alerta.campo not in no_coinciden and alerta.aplica is not False:  # solo falsos positivos
            sesion.delete(alerta)
    con_alerta = {a.campo for a in existentes}
    for campo in sorted(no_coinciden - con_alerta):
        sesion.add(AlertaBD(folio=folio, documento_id=None, codigo="CMP-001",
                            severidad=Severidad.critica.value, confianza=1.0, campo=campo,
                            mensaje=f"Los documentos no coinciden en {campo}"))
    sesion.flush()  # para que una segunda llamada en la misma transaccion no duplique


def crear_folio(sesion: Session, proceso: str, referencia_externa: str | None, usuario: str,
                ahora: datetime | None = None) -> Folio:
    """Crea `{PREFIJO}-{AAAA}-{NNNNNN}`. El anio es el de la zona horaria del negocio."""
    fila_proceso = sesion.get(Proceso, proceso)
    if fila_proceso is None:
        raise ErrorApi(404, "PROCESO_NO_ENCONTRADO", f"No existe el proceso '{proceso}'")

    ahora = ahora or datetime.now(timezone.utc)
    anio = ahora.astimezone(ZoneInfo(get_settings().zona_horaria)).year
    secuencia = _siguiente_secuencia(sesion, proceso, anio)
    if secuencia > MAX_SECUENCIA:
        sesion.rollback()
        raise ErrorApi(409, "SECUENCIA_AGOTADA",
                       f"Se ha agotado la numeracion de folios de '{proceso}' en {anio}")

    folio = Folio(folio=f"{fila_proceso.prefijo_folio}-{anio}-{secuencia:06d}", proceso=proceso,
                  anio=anio, secuencia=secuencia, referencia_externa=referencia_externa)
    sesion.add(folio)
    # flush antes de las alertas: sin relationship, SQLAlchemy no ordena los INSERT por la FK
    sesion.flush()
    # Un folio nuevo no tiene documentos: una EXP-001 por cada tipo requerido (misma transaccion).
    # Despues las ajusta recalcular_exp001 al procesar cada documento
    for tipo in fila_proceso.tipos_requeridos:
        _crear_exp001(sesion, folio.folio, tipo)
    auditoria.registrar(sesion, "folio_creado", usuario=usuario, folio=folio.folio)
    sesion.commit()
    return folio


def _fichas() -> dict[str, dict]:
    # Las mismas de GET /tipos-documentales: ingesta las arma desde configuracion.servicio
    return {f["nombre"]: f for f in ingesta.listar_tipos()}


def _documentos_y_alertas(sesion: Session, folio: str) -> tuple[list[ResultadoDocumento], list[Alerta]]:
    """Todos los documentos del folio armados como GET /documentos/{id} y las alertas de expediente."""
    documentos = sesion.scalars(select(Documento).where(Documento.folio == folio)
                                .order_by(Documento.creado_en, Documento.id)).all()
    # Alertas de expediente = las del folio sin documento (ADR-006 2.1)
    alertas_expediente = sesion.scalars(
        select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.documento_id.is_(None))
        .order_by(AlertaBD.creado_en, AlertaBD.campo)).all()
    return ([ingesta.construir_resultado(sesion, d) for d in documentos],
            [ingesta.alerta_desde_bd(a) for a in alertas_expediente])


def _bloqueantes_sin_resolver(documentos: list[ResultadoDocumento],
                              alertas_expediente: list[Alerta]) -> list[Alerta]:
    """Regla ADR-006 2.2 sobre las alertas VISIBLES (las de documento como construir_resultado, de
    plataforma y del motor de la version vigente, y las de expediente): bloqueantes con aplica distinto
    de False. La usan la lista de folios y la decision."""
    visibles = [a for d in documentos for a in d.alertas_encontradas] + alertas_expediente
    return [a for a in visibles if a.severidad == Severidad.bloqueante and a.aplica is not False]


def _recomendar(documentos: list[ResultadoDocumento], alertas_expediente: list[Alerta],
                fichas: dict[str, dict]) -> Recomendacion:
    """Recomendacion global a partir del expediente ya armado (la por documento es del motor)."""
    para_recomendar = [DocumentoParaRecomendar(
        estado=d.estado_analisis,
        tipo=d.tipo_documental_confirmado or d.tipo_documental_detectado or d.tipo_documental_declarado,
        # Tipo confirmado por el revisor: vale 1.0, como un campo corregido (ADR-006 2.4; acordado con PERSONA_2, D2)
        confianza_clasificacion=1.0 if d.tipo_documental_confirmado else d.confianza_clasificacion,
        confianza_por_campo=d.nivel_confianza_por_campo) for d in documentos]
    alertas = [a for d in documentos for a in d.alertas_encontradas] + alertas_expediente
    return calcular_recomendacion_global(para_recomendar, alertas, fichas)


def obtener_expediente(sesion: Session, folio: str) -> ResultadoExpediente:
    fila = sesion.get(Folio, folio)
    if fila is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")

    documentos, alertas_expediente = _documentos_y_alertas(sesion, folio)
    # Los nombres de columna de BD se traducen aqui a los del Contrato 1
    return ResultadoExpediente(
        folio=fila.folio,
        proceso=fila.proceso,
        referencia_externa=fila.referencia_externa,  # ADR-004
        fecha_solicitud=fila.creado_en,              # ADR-004
        estado_general=EstadoGeneral(fila.estado_general),
        documentos=documentos,
        comparaciones=comparaciones_actuales(sesion, folio),
        alertas_expediente=alertas_expediente,
        recomendacion_global=_recomendar(documentos, alertas_expediente, _fichas()),
        decision_humana=DecisionHumana(fila.decision) if fila.decision else None,
        comentario_decision=fila.decision_comentario,  # ADR-006 G
        usuario_decision=fila.decision_usuario,
        fecha_decision=fila.decision_fecha,
    )


def listar_folios(sesion: Session, proceso: str | None = None,
                  estado_general: EstadoGeneral | None = None, pagina: int = 1,
                  tamano_pagina: int = 20) -> tuple[list[ResumenFolio], int]:
    """Pagina de folios (ResumenFolio, ADR-006 1.1), del mas reciente al mas antiguo, y el total."""
    filtros = []
    if proceso:
        filtros.append(Folio.proceso == proceso)
    if estado_general:
        filtros.append(Folio.estado_general == EstadoGeneral(estado_general).value)

    total = sesion.scalar(select(func.count()).select_from(Folio).where(*filtros))

    n_documentos = (select(func.count()).select_from(Documento)
                    .where(Documento.folio == Folio.folio).scalar_subquery())
    filas = sesion.execute(
        select(Folio, n_documentos)
        .where(*filtros)
        .order_by(Folio.creado_en.desc(), Folio.folio.desc())
        .offset((pagina - 1) * tamano_pagina)
        .limit(tamano_pagina)
    ).all()
    fichas = _fichas()
    elementos = []
    for f, docs in filas:
        # N+1: el expediente de cada folio de la pagina se arma aparte (aceptable en el MVP). Asi la
        # recomendacion y las bloqueantes ven las mismas alertas que GET /folios/{folio}
        documentos, alertas_expediente = _documentos_y_alertas(sesion, f.folio)
        elementos.append(ResumenFolio(
            folio=f.folio, proceso=f.proceso, estado_general=EstadoGeneral(f.estado_general),
            recomendacion_global=_recomendar(documentos, alertas_expediente, fichas), n_documentos=docs,
            n_bloqueantes_sin_resolver=len(_bloqueantes_sin_resolver(documentos, alertas_expediente)),
            fecha_solicitud=f.creado_en, referencia_externa=f.referencia_externa))  # ADR-008
    return elementos, total


# --- revision: resolver alertas (E2.6a) ---

def _alerta(sesion: Session, alerta_id: str) -> AlertaBD | None:
    try:
        return sesion.get(AlertaBD, uuid.UUID(alerta_id))
    except ValueError:  # un id que no es UUID es una alerta que no existe (404, no 422)
        return None


def _alerta_no_encontrada() -> ErrorApi:
    return ErrorApi(404, "ALERTA_NO_ENCONTRADA", "La alerta no existe en este documento o folio")


def _exigir_folio_abierto(fila: Folio) -> None:
    if fila.estado_general != EstadoGeneral.en_revision.value:
        raise ErrorApi(409, "FOLIO_CERRADO", "El folio ya tiene decision y no admite cambios")


def _guardar_resolucion(sesion: Session, alerta: AlertaBD, aplica: bool, comentario: str | None,
                        usuario: str) -> None:
    """Sobrescribe la resolucion (se puede volver a resolver mientras el folio este abierto)."""
    alerta.aplica = aplica
    alerta.comentario = comentario
    alerta.resuelta_por = usuario
    alerta.resuelta_en = datetime.now(timezone.utc)
    alerta.resuelta_por_revisor = True
    # Sin el comentario: es texto libre y puede llevar datos personales (ya esta en la alerta)
    auditoria.registrar(sesion, "alerta_resuelta", usuario=usuario, folio=alerta.folio,
                        documento_id=alerta.documento_id,
                        detalle={"alerta_id": str(alerta.id), "codigo": alerta.codigo, "aplica": aplica})
    sesion.commit()


def resolver_alerta_documento(sesion: Session, documento_id: str, alerta_id: str, aplica: bool,
                              comentario: str | None, usuario: str) -> ResultadoDocumento:
    """POST /documentos/{id}/alertas/{alerta_id}/resolver. Solo alertas visibles en el documento:
    de plataforma o del motor de la version vigente del resultado."""
    doc = ingesta.obtener_documento(sesion, documento_id)
    alerta = _alerta(sesion, alerta_id)
    vigente = sesion.scalar(select(func.max(Resultado.version)).where(Resultado.documento_id == doc.id))
    if (alerta is None or alerta.documento_id != doc.id
            or alerta.version_resultado not in (None, vigente)):
        raise _alerta_no_encontrada()
    _exigir_folio_abierto(sesion.get(Folio, doc.folio))
    # En error si se puede resolver (decision del usuario); pendiente o procesando no
    if doc.estado_analisis in (EstadoAnalisis.pendiente.value, EstadoAnalisis.procesando.value):
        raise ErrorApi(409, "DOCUMENTO_EN_PROCESO", "El documento todavia se esta procesando")
    _guardar_resolucion(sesion, alerta, aplica, comentario, usuario)
    return ingesta.construir_resultado(sesion, doc)


def resolver_alerta_expediente(sesion: Session, folio: str, alerta_id: str, aplica: bool,
                               comentario: str | None, usuario: str) -> ResultadoExpediente:
    """POST /folios/{folio}/alertas/{alerta_id}/resolver, sobre `alertas_expediente`."""
    fila = sesion.get(Folio, folio)
    if fila is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")
    alerta = _alerta(sesion, alerta_id)
    if alerta is None or alerta.folio != folio or alerta.documento_id is not None:
        raise _alerta_no_encontrada()
    _exigir_folio_abierto(fila)
    _guardar_resolucion(sesion, alerta, aplica, comentario, usuario)
    return obtener_expediente(sesion, folio)


def _exigir_documento_revisable(sesion: Session, doc: Documento) -> None:
    """Orden comun de las acciones del revisor sobre un documento: folio abierto y documento completado."""
    _exigir_folio_abierto(sesion.get(Folio, doc.folio))
    if doc.estado_analisis in (EstadoAnalisis.pendiente.value, EstadoAnalisis.procesando.value):
        raise ErrorApi(409, "DOCUMENTO_EN_PROCESO", "El documento todavia se esta procesando")
    if doc.estado_analisis == EstadoAnalisis.error.value:
        raise ErrorApi(409, "DOCUMENTO_CON_ERROR", "El documento no se pudo procesar; vuelve a subirlo")


_INVALIDO = object()


def _valor_corregido(definicion: dict, valor):
    """Valor a guardar, o _INVALIDO. Reglas (decision del usuario en la revision del PR #9):
    - null: solo en campos con `obligatorio: false`; vacia el campo;
    - tipo `anio`: entero de 4 cifras o texto "AAAA"; se guarda como entero (como lo da el motor);
    - el resto: texto no vacio; `fecha` en AAAA-MM-DD; si hay `patron`, tiene que cumplirlo."""
    if valor is None:
        return None if not definicion.get("obligatorio", False) else _INVALIDO
    if definicion.get("tipo") == "anio":
        if isinstance(valor, int) and not isinstance(valor, bool) and 1000 <= valor <= 9999:
            return valor
        if isinstance(valor, str) and re.fullmatch(r"\d{4}", valor):
            return int(valor)
        return _INVALIDO
    if not isinstance(valor, str) or not valor.strip():
        return _INVALIDO
    if definicion.get("tipo") == "fecha":
        try:
            datetime.strptime(valor, "%Y-%m-%d")
        except ValueError:
            return _INVALIDO
    patron = definicion.get("patron")
    if patron and not re.fullmatch(patron, valor):
        return _INVALIDO
    return valor


def corregir_datos(sesion: Session, documento_id: str, cambios: dict, usuario: str) -> ResultadoDocumento:
    """PATCH /documentos/{id}/datos (ADR-006 2.4). Una Correccion por campo sobre la version vigente del
    Resultado (sin version nueva); construir_resultado las aplica. Los mensajes de error nombran el
    campo, nunca el valor (son datos personales)."""
    doc = ingesta.obtener_documento(sesion, documento_id)
    _exigir_documento_revisable(sesion, doc)
    vigente = sesion.scalar(select(func.max(Resultado.version)).where(Resultado.documento_id == doc.id))
    if vigente is None:
        raise ErrorApi(409, "DOCUMENTO_EN_PROCESO", "El documento todavia no tiene resultado")
    if not cambios:
        raise ErrorApi(422, "PETICION_INVALIDA", "No hay campos que corregir")

    actual = ingesta.construir_resultado(sesion, doc)  # con las correcciones previas ya aplicadas
    # Se valida con la ficha con la que se EXTRAJERON los datos, no con el tipo efectivo
    campos = (_fichas().get(_tipo_extraccion(sesion, doc)) or {}).get("campos") or {}
    a_guardar = {}
    for campo, valor in cambios.items():
        if campo not in campos:
            raise ErrorApi(422, "PETICION_INVALIDA", f"campo desconocido: {campo}")
        a_guardar[campo] = _valor_corregido(campos[campo] or {}, valor)
        if a_guardar[campo] is _INVALIDO:
            raise ErrorApi(422, "PETICION_INVALIDA", f"valor no valido para el campo {campo}")

    for campo, valor in a_guardar.items():
        sesion.add(Correccion(documento_id=doc.id, campo=campo, valor_anterior=actual.datos_extraidos.get(campo),
                              valor_nuevo=valor, usuario=usuario, version_resultado=vigente))
    recalcular_cmp001(sesion, doc.folio)
    # Solo los nombres de los campos: los valores son datos personales
    auditoria.registrar(sesion, "dato_corregido", usuario=usuario, folio=doc.folio, documento_id=doc.id,
                        detalle={"campos": sorted(cambios)})
    sesion.commit()
    return ingesta.construir_resultado(sesion, doc)


def confirmar_clasificacion(sesion: Session, documento_id: str, tipo: str,
                            usuario: str) -> tuple[ResultadoDocumento, bool]:
    """POST /documentos/{id}/confirmar-clasificacion (ADR-006 2.5). Devuelve (resultado, reprocesar).

    Mismo tipo con el que se extrajo: se guarda, las CLS-001 visibles sin revisar quedan resueltas y no
    se reprocesa. Otro tipo: se guarda, el documento vuelve a `pendiente` y quien llama lanza el
    reproceso con `tipo_confirmado` (el servicio no conoce BackgroundTasks).
    """
    doc = ingesta.obtener_documento(sesion, documento_id)
    _exigir_documento_revisable(sesion, doc)
    if not ingesta.existe_tipo(tipo):
        raise ErrorApi(422, "PETICION_INVALIDA", "tipo_documental no existe")

    vigente = sesion.scalar(select(Resultado).where(Resultado.documento_id == doc.id)
                            .order_by(Resultado.version.desc()).limit(1))
    extraido = _tipo_extraccion(sesion, doc)  # antes de guardar el confirmado nuevo
    doc.tipo_documental_confirmado = tipo
    reprocesar = tipo != extraido

    if reprocesar:
        doc.estado_analisis = EstadoAnalisis.pendiente.value  # completado -> pendiente (endpoints.md)
    else:
        visibles = AlertaBD.version_resultado.is_(None)
        if vigente is not None:
            visibles = or_(visibles, AlertaBD.version_resultado == vigente.version)
        for alerta in sesion.scalars(select(AlertaBD).where(
                AlertaBD.documento_id == doc.id, AlertaBD.codigo == "CLS-001", AlertaBD.aplica.is_(None), visibles)):
            alerta.aplica = False
            alerta.comentario = "Resuelta al confirmar la clasificacion"
            alerta.resuelta_por = usuario
            alerta.resuelta_en = datetime.now(timezone.utc)
            alerta.resuelta_por_revisor = True
    # Un documento pendiente ya no cuenta para EXP-001 ni para las comparaciones
    recalcular_exp001(sesion, doc.folio)
    recalcular_exp002(sesion, doc.folio)
    recalcular_cmp001(sesion, doc.folio)
    auditoria.registrar(sesion, "clasificacion_confirmada", usuario=usuario, folio=doc.folio,
                        documento_id=doc.id, detalle={"tipo": tipo, "reproceso": reprocesar})
    sesion.commit()
    return ingesta.construir_resultado(sesion, doc), reprocesar


def decidir_folio(sesion: Session, folio: str, decision: DecisionHumana, comentario: str | None,
                  usuario: str) -> ResultadoExpediente:
    """POST /folios/{folio}/decision (ADR-006 2.2 y G). Tras decidir, el folio queda cerrado para siempre.

    Un documento en `error` NO bloquea la decision: no lo pide el contrato y la decision es humana.
    """
    fila = sesion.get(Folio, folio)
    if fila is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")
    _exigir_folio_abierto(fila)
    en_proceso = sesion.scalar(select(func.count()).select_from(Documento).where(
        Documento.folio == folio,
        Documento.estado_analisis.in_([EstadoAnalisis.pendiente.value, EstadoAnalisis.procesando.value])))
    if en_proceso:  # al aprobar y al rechazar (decidido con PERSONA_3)
        raise ErrorApi(409, "DOCUMENTO_EN_PROCESO", "Hay documentos del folio que todavia se estan procesando")
    if decision == DecisionHumana.aprobar:
        # Regla 2.2: una bloqueante visible con aplica distinto de False impide aprobar (rechazar, no)
        if _bloqueantes_sin_resolver(*_documentos_y_alertas(sesion, folio)):
            raise ErrorApi(409, "DECISION_BLOQUEADA", "Hay alertas bloqueantes que impiden aprobar el folio")

    # UPDATE condicional: si otro revisor decidio entre medias, afecta a 0 filas
    estado = EstadoGeneral.aprobado if decision == DecisionHumana.aprobar else EstadoGeneral.rechazado
    actualizadas = sesion.execute(
        update(Folio).where(Folio.folio == folio, Folio.estado_general == EstadoGeneral.en_revision.value)
        .values(estado_general=estado.value, decision=decision.value, decision_comentario=comentario,
                decision_usuario=usuario, decision_fecha=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)).rowcount
    if actualizadas == 0:
        sesion.rollback()
        raise ErrorApi(409, "FOLIO_CERRADO", "El folio ya tiene decision y no admite cambios")
    # Sin el comentario: es texto libre (ya esta en el folio)
    auditoria.registrar(sesion, "decision_tomada", usuario=usuario, folio=folio,
                        detalle={"decision": decision.value})
    sesion.commit()
    sesion.expire(fila)  # el UPDATE no paso por el ORM: releer el folio
    # TODO (etapa 3): webhook folio.estado_cambiado
    return obtener_expediente(sesion, folio)
