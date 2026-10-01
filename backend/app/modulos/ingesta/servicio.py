"""API publica del modulo ingesta: recibir un original, guardarlo en S3, registrarlo y consultarlo (ADR-005)."""
import hashlib
import logging
import uuid
from pathlib import PurePath

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.almacenamiento import Almacenamiento, clave_original
from app.core.config import get_settings
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Correccion, Documento, Folio, Resultado
from app.modulos.ingesta import procesamiento, tipos
from app.schemas.resultado import Correccion as CorreccionContrato
from app.schemas.resultado import (Alerta, EstadoAnalisis, EstadoGeneral, ReferenciaArchivoOriginal,
                                   ResultadoDocumento, Severidad)

log = logging.getLogger(__name__)

MAX_NOMBRE = 255

# El tipo de contenido sale de la extension, nunca del cliente: un .pdf enviado como text/html se
# abriria como pagina web desde la URL firmada
_TIPO_CONTENIDO = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
_FIRMA_MAGICA = {"pdf": b"%PDF-", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff", "png": b"\x89PNG\r\n\x1a\n"}


def _nombre_seguro(nombre_archivo: str) -> str:
    """Solo el nombre, sin ruta; recortado a 255 caracteres conservando la extension."""
    nombre = PurePath(nombre_archivo.replace("\\", "/")).name.strip()
    if not nombre:
        raise ErrorApi(422, "PETICION_INVALIDA", "El archivo no tiene nombre")
    if len(nombre) > MAX_NOMBRE:
        sufijo = PurePath(nombre).suffix[:MAX_NOMBRE // 2]
        nombre = nombre[:MAX_NOMBRE - len(sufijo)] + sufijo
    return nombre


def alerta_desde_bd(a: AlertaBD) -> Alerta:
    """AlertaBD -> Alerta del Contrato 1, con `id` (ADR-006 1.3) y revision (ADR-006 2.2)."""
    return Alerta(id=str(a.id), codigo=a.codigo, mensaje=a.mensaje, severidad=a.severidad,
                  confianza=a.confianza, campo=a.campo, resuelta_por_revisor=a.resuelta_por_revisor,
                  aplica=a.aplica, comentario_revisor=a.comentario, resuelta_por=a.resuelta_por,
                  resuelta_en=a.resuelta_en)


def ingestar(sesion: Session, almacenamiento: Almacenamiento, folio: str, nombre_archivo: str,
             datos: bytes, tipo_declarado: str | None, usuario: str) -> Documento:
    """Valida, sube el original a S3 y crea el documento en `pendiente`. Un duplicado no bloquea."""
    # a) folio abierto
    fila_folio = sesion.get(Folio, folio)
    if fila_folio is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")
    if fila_folio.estado_general != EstadoGeneral.en_revision.value:
        raise ErrorApi(409, "FOLIO_CERRADO", "El folio ya tiene decision y no admite cambios")

    # b) tamano y nombre
    maximo_mb = get_settings().tamano_maximo_archivo_mb
    if len(datos) > maximo_mb * 1024 * 1024:
        raise ErrorApi(413, "ARCHIVO_DEMASIADO_GRANDE", f"El archivo supera {maximo_mb} MB")
    if not datos:
        raise ErrorApi(422, "PETICION_INVALIDA", "El archivo esta vacio")
    nombre_archivo = _nombre_seguro(nombre_archivo)

    # c) tipo, formato y contenido real
    if tipo_declarado and not tipos.existe_tipo(tipo_declarado):
        raise ErrorApi(422, "PETICION_INVALIDA", "tipo_declarado no existe")
    extension = PurePath(nombre_archivo).suffix.lower().lstrip(".")
    if not extension or extension not in tipos.formatos_permitidos(tipo_declarado):
        raise ErrorApi(415, "FORMATO_NO_PERMITIDO", "Formato de archivo no permitido")
    firma = _FIRMA_MAGICA.get(extension)
    if firma and not datos.startswith(firma):
        raise ErrorApi(415, "FORMATO_NO_PERMITIDO", "El contenido del archivo no corresponde a su extension")
    tipo_contenido = _TIPO_CONTENIDO.get(extension, "application/octet-stream")

    # d) hash y duplicado en el mismo folio
    hash_sha256 = hashlib.sha256(datos).hexdigest()
    anterior = sesion.scalar(select(Documento.id).where(Documento.folio == folio,
                                                        Documento.hash_sha256 == hash_sha256)
                             .order_by(Documento.creado_en).limit(1))

    # e) documento, subida y registro
    documento_id = uuid.uuid4()
    clave = clave_original(fila_folio.proceso, fila_folio.anio, fila_folio.secuencia,
                           str(documento_id), extension)
    documento = Documento(id=documento_id, folio=folio, nombre_archivo=nombre_archivo, ruta_s3=clave,
                          hash_sha256=hash_sha256, tipo_declarado=tipo_declarado,
                          estado_analisis=EstadoAnalisis.pendiente.value)
    sesion.add(documento)
    sesion.flush()
    try:
        almacenamiento.subir(datos, clave, tipo_contenido)
    except Exception:
        sesion.rollback()
        log.exception("No se pudo subir el original del documento %s", documento_id)
        raise ErrorApi(500, "ERROR_INTERNO", "Error interno") from None

    if anterior is not None:
        sesion.add(AlertaBD(folio=folio, documento_id=documento_id, codigo="DUP-001",
                            severidad=Severidad.critica.value, confianza=1.0,
                            mensaje=f"Este archivo ya se subio en este folio (documento {anterior})"))
    # Sin nombre_archivo: los nombres de fichero suelen llevar el nombre de la persona
    auditoria.registrar(sesion, "documento_subido", usuario=usuario, folio=folio, documento_id=documento_id,
                        detalle={"hash_sha256": hash_sha256, "tamano_bytes": len(datos),
                                 "duplicado": anterior is not None})
    try:
        sesion.commit()
    except Exception:
        # El IAM no tiene s3:DeleteObject: el objeto queda huerfano y hay que revisarlo a mano
        log.error("Original subido a S3 sin registro en BD (objeto huerfano): %s", clave)
        sesion.rollback()
        raise
    return documento


def obtener_documento(sesion: Session, documento_id: str) -> Documento:
    """Documento por id; 404 DOCUMENTO_NO_ENCONTRADO si no existe o el id no es un UUID."""
    try:
        doc = sesion.get(Documento, uuid.UUID(documento_id))
    except ValueError:
        doc = None
    if doc is None:
        raise ErrorApi(404, "DOCUMENTO_NO_ENCONTRADO", "No existe el documento")
    return doc


def _aplicar_correcciones(sesion: Session, resultado: ResultadoDocumento, documento_id: uuid.UUID,
                          version: int) -> ResultadoDocumento:
    """Correcciones de esa version, en orden: gana el ultimo valor; confianza 1.0 y evidencia
    "correccion_revisor" (ADR-006 2.4). Las de otras versiones no se aplican."""
    filas = sesion.scalars(select(Correccion).where(
        Correccion.documento_id == documento_id, Correccion.version_resultado == version)
        .order_by(Correccion.creado_en, Correccion.id)).all()
    if not filas:
        return resultado
    datos = dict(resultado.datos_extraidos)
    confianzas = dict(resultado.nivel_confianza_por_campo)
    evidencias = dict(resultado.evidencia_por_campo)
    for c in filas:
        datos[c.campo] = c.valor_nuevo
        confianzas[c.campo] = 1.0
        evidencias[c.campo] = "correccion_revisor"
    return resultado.model_copy(update={
        "datos_extraidos": datos, "nivel_confianza_por_campo": confianzas, "evidencia_por_campo": evidencias,
        "correcciones": [CorreccionContrato(campo=c.campo, valor_anterior=c.valor_anterior,
                                            valor_nuevo=c.valor_nuevo, usuario=c.usuario, fecha=c.creado_en)
                         for c in filas]})


def construir_resultado(sesion: Session, documento: Documento) -> ResultadoDocumento:
    """ResultadoDocumento de un documento, con la BD como fuente de verdad.

    Con resultado: la version mayor, sobrescribiendo con la BD `estado_analisis`,
    `tipo_documental_confirmado` y `alertas_encontradas` (tabla `alertas`, con id y revision: las de
    plataforma y las del motor de esa version), y con las correcciones del revisor de ESA version
    aplicadas encima (ADR-006 2.4).
    Sin resultado todavia: uno minimo con el estado de la fila y sus alertas.
    Lo usan GET /documentos/{id} y el expediente, para que los dos digan lo mismo.
    """
    fila = sesion.scalar(select(Resultado).where(Resultado.documento_id == documento.id)
                         .order_by(Resultado.version.desc()).limit(1))
    # De plataforma (version_resultado NULL) + las del motor de la version vigente; las de versiones
    # anteriores del motor ya no se muestran al reprocesar
    vigentes = AlertaBD.version_resultado.is_(None)
    if fila is not None:
        vigentes = or_(vigentes, AlertaBD.version_resultado == fila.version)
    alertas = [alerta_desde_bd(a) for a in sesion.scalars(
        select(AlertaBD).where(AlertaBD.documento_id == documento.id, vigentes)
        .order_by(AlertaBD.creado_en, AlertaBD.id))]
    estado = EstadoAnalisis(documento.estado_analisis)
    if fila is not None:
        resultado = ResultadoDocumento.model_validate(fila.json).model_copy(update={
            "estado_analisis": estado,
            "tipo_documental_confirmado": documento.tipo_documental_confirmado,
            "alertas_encontradas": alertas,
        })
        return _aplicar_correcciones(sesion, resultado, documento.id, fila.version)
    return ResultadoDocumento(
        folio_solicitud=documento.folio,
        identificador_unico_documento=str(documento.id),
        tipo_documental_declarado=documento.tipo_declarado,
        tipo_documental_detectado=None,
        tipo_documental_confirmado=documento.tipo_documental_confirmado,
        alertas_encontradas=alertas,
        estado_analisis=estado,
        referencia_archivo_original=ReferenciaArchivoOriginal(nombre_archivo=documento.nombre_archivo,
                                                              ruta=documento.ruta_s3,
                                                              hash=documento.hash_sha256),
    )


def obtener_resultado(sesion: Session, documento_id: str) -> ResultadoDocumento:
    """GET /documentos/{id}. 404 si no existe o el id no es un UUID."""
    return construir_resultado(sesion, obtener_documento(sesion, documento_id))


def url_original(sesion: Session, almacenamiento: Almacenamiento, documento_id: str) -> str:
    """URL prefirmada y temporal del original.

    Sin auditoria: no esta en ACCIONES_AUDITORIA. El "mostrar" auditado es de la etapa 3.
    """
    return almacenamiento.url_prefirmada(obtener_documento(sesion, documento_id).ruta_s3)


def listar_tipos() -> list[dict]:
    """Fichas de los tipos documentales (GET /tipos-documentales)."""
    return tipos.listar_fichas()


def nombre_visible_tipo(tipo: str) -> str:
    """Nombre legible de un tipo documental (p. ej. para mensajes de alerta)."""
    return tipos.nombre_visible(tipo)


def procesar_documento(documento_id: uuid.UUID, tipo_confirmado: str | None = None) -> None:
    """Procesa el documento en segundo plano (BackgroundTask): ver `procesamiento.procesar`."""
    procesamiento.procesar(documento_id, tipo_confirmado)


def existe_tipo(tipo: str) -> bool:
    """True si hay ficha para ese tipo documental."""
    return tipos.existe_tipo(tipo)
