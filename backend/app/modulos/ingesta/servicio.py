"""API publica del modulo ingesta: recibir un original, guardarlo en S3 y registrarlo (ADR-005)."""
import hashlib
import logging
import uuid
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.almacenamiento import Almacenamiento, clave_original
from app.core.config import get_settings
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Documento, Folio
from app.modulos.ingesta import tipos
from app.schemas.resultado import EstadoAnalisis, EstadoGeneral, Severidad

log = logging.getLogger(__name__)


def _extension(nombre_archivo: str) -> str:
    return PurePath(nombre_archivo).suffix.lower().lstrip(".")


def ingestar(sesion: Session, almacenamiento: Almacenamiento, folio: str, nombre_archivo: str,
             datos: bytes, tipo_contenido: str, tipo_declarado: str | None, usuario: str) -> Documento:
    """Valida, sube el original a S3 y crea el documento en `pendiente`. Un duplicado no bloquea."""
    # a) folio abierto
    fila_folio = sesion.get(Folio, folio)
    if fila_folio is None:
        raise ErrorApi(404, "FOLIO_NO_ENCONTRADO", f"No existe el folio '{folio}'")
    if fila_folio.estado_general != EstadoGeneral.en_revision.value:
        raise ErrorApi(409, "FOLIO_CERRADO", "El folio ya tiene decision y no admite cambios")

    # b) tamano
    maximo_mb = get_settings().tamano_maximo_archivo_mb
    if len(datos) > maximo_mb * 1024 * 1024:
        raise ErrorApi(413, "ARCHIVO_DEMASIADO_GRANDE", f"El archivo supera {maximo_mb} MB")
    if not datos:
        raise ErrorApi(422, "PETICION_INVALIDA", "El archivo esta vacio")

    # c) tipo y formato
    if tipo_declarado and not tipos.existe_tipo(tipo_declarado):
        raise ErrorApi(422, "PETICION_INVALIDA", "tipo_declarado no existe")
    extension = _extension(nombre_archivo)
    if not extension or extension not in tipos.formatos_permitidos(tipo_declarado):
        raise ErrorApi(415, "FORMATO_NO_PERMITIDO", "Formato de archivo no permitido")

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
