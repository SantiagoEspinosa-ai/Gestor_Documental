"""API publica del modulo expediente: crear, consultar y listar folios (ADR-005: solo esto se importa)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as insert_postgresql
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.config import get_settings
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Documento, Folio, Proceso, Resultado, SecuenciaFolio
from app.modulos.ingesta import servicio as ingesta
from app.schemas.resultado import (DecisionHumana, EstadoAnalisis, EstadoGeneral, ResultadoExpediente,
                                   ResumenFolio, Severidad)

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


def _tipo_efectivo(sesion: Session, documento: Documento) -> str | None:
    """Confirmado por el revisor > detectado en el resultado vigente > declarado al subir."""
    if documento.tipo_documental_confirmado:
        return documento.tipo_documental_confirmado
    vigente = sesion.scalar(select(Resultado.json).where(Resultado.documento_id == documento.id)
                            .order_by(Resultado.version.desc()).limit(1))
    return (vigente or {}).get("tipo_documental_detectado") or documento.tipo_declarado


def recalcular_exp001(sesion: Session, folio: str) -> None:
    """Ajusta las EXP-001 del folio a los documentos `completado` que tiene. Sin commit; idempotente.

    Tipo presente: se borran sus EXP-001 sin revisar (`aplica` NULL); las revisadas se conservan.
    Tipo que falta: se crea su EXP-001 si no hay ninguna de ese campo.
    TODO (E2.6): confirmar clasificacion tambien llama a recalcular_exp001.
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
                if alerta.aplica is None:
                    sesion.delete(alerta)
        elif not del_tipo:
            _crear_exp001(sesion, folio, tipo)
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


def obtener_expediente(sesion: Session, folio: str) -> ResultadoExpediente:
    fila = sesion.get(Folio, folio)
    if fila is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")

    # Todos los documentos del folio, tengan resultado o no; el mismo armado que GET /documentos/{id}
    documentos = sesion.scalars(select(Documento).where(Documento.folio == folio)
                                .order_by(Documento.creado_en, Documento.id)).all()
    # Alertas de expediente = las del folio sin documento (ADR-006 2.1)
    alertas_expediente = sesion.scalars(
        select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.documento_id.is_(None))
        .order_by(AlertaBD.creado_en, AlertaBD.campo)
    )
    # Los nombres de columna de BD se traducen aqui a los del Contrato 1
    return ResultadoExpediente(
        folio=fila.folio,
        proceso=fila.proceso,
        referencia_externa=fila.referencia_externa,  # ADR-004
        fecha_solicitud=fila.creado_en,              # ADR-004
        estado_general=EstadoGeneral(fila.estado_general),
        documentos=[ingesta.construir_resultado(sesion, d) for d in documentos],
        comparaciones=[],
        alertas_expediente=[ingesta.alerta_desde_bd(a) for a in alertas_expediente],
        recomendacion_global=None,
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
    # Regla ADR-006 2.2: bloqueante con aplica NULL (sin revisar) o true (confirmada)
    n_bloqueantes = (select(func.count()).select_from(AlertaBD)
                     .where(AlertaBD.folio == Folio.folio,
                            AlertaBD.severidad == Severidad.bloqueante.value,
                            or_(AlertaBD.aplica.is_(None), AlertaBD.aplica.is_(True)))
                     .scalar_subquery())
    filas = sesion.execute(
        select(Folio, n_documentos, n_bloqueantes)
        .where(*filtros)
        .order_by(Folio.creado_en.desc(), Folio.folio.desc())
        .offset((pagina - 1) * tamano_pagina)
        .limit(tamano_pagina)
    )
    elementos = [
        ResumenFolio(folio=f.folio, proceso=f.proceso, estado_general=EstadoGeneral(f.estado_general),
                     recomendacion_global=None, n_documentos=docs, n_bloqueantes_sin_resolver=bloq,
                     fecha_solicitud=f.creado_en, referencia_externa=f.referencia_externa)  # ADR-008
        for f, docs, bloq in filas
    ]
    return elementos, total
