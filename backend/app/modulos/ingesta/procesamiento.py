"""Procesamiento de un documento en segundo plano: descarga el original, llama al motor y guarda.

Corre como BackgroundTask despues de la respuesta HTTP: abre su propia sesion y nunca relanza.
Reparto con PERSONA_2: el motor hace las reglas del documento (VAL, REG, CLS) y su recomendacion;
la plataforma guarda el resultado y cada alerta del motor en la tabla `alertas` (asi reciben id).
"""
import json
import logging
import uuid

from sqlalchemy import func, select

from app.core import auditoria
from app.core.almacenamiento import get_almacenamiento
from app.core.db import SesionLocal, get_engine
from app.core.modelos import AlertaBD, Documento, Resultado
# TODO: sustituir por: from app.modulos.orquestador.servicio import procesar_documento as analizar (PERSONA_2)
from app.modulos.ingesta.motor_stub import procesar_documento as analizar
from app.schemas.resultado import EstadoAnalisis, ReferenciaArchivoOriginal

log = logging.getLogger(__name__)

_COLUMNAS_AUDITORIA = {"modelo", "version_prompt"}


def _detalle_serializable(datos: dict) -> dict:
    """datos_auditoria sin modelo/version_prompt (van a sus columnas) y solo lo serializable a JSON."""
    detalle = {}
    for clave, valor in datos.items():
        if clave in _COLUMNAS_AUDITORIA:
            continue
        try:
            json.dumps(valor)
        except (TypeError, ValueError):
            continue
        detalle[clave] = valor
    return detalle


def procesar(documento_id: uuid.UUID, tipo_confirmado: str | None = None) -> None:
    with SesionLocal(bind=get_engine()) as sesion:
        doc = sesion.get(Documento, documento_id)
        if doc is None:
            log.error("procesar: no existe el documento %s", documento_id)
            return
        doc.estado_analisis = EstadoAnalisis.procesando.value
        sesion.commit()

        try:
            contenido = get_almacenamiento().descargar(doc.ruta_s3)
            resultado, datos = analizar(
                contenido, identificador=str(doc.id), nombre_archivo=doc.nombre_archivo,
                tipo_declarado=doc.tipo_declarado, folio=doc.folio,
                referencia=ReferenciaArchivoOriginal(nombre_archivo=doc.nombre_archivo, ruta=doc.ruta_s3,
                                                     hash=doc.hash_sha256),
                tipo_confirmado=tipo_confirmado)
            if (resultado.identificador_unico_documento != str(doc.id)
                    or resultado.folio_solicitud != doc.folio):
                # Solo ids en el log: nada de datos extraidos
                raise ValueError(f"El motor devolvio un resultado de otro documento o folio ({doc.id})")
        except Exception:
            log.exception("Fallo al procesar el documento %s", documento_id)
            _marcar_error(sesion, documento_id)
            return

        try:
            version = (sesion.scalar(select(func.max(Resultado.version))
                                     .where(Resultado.documento_id == doc.id)) or 0) + 1
            sesion.add(Resultado(documento_id=doc.id, version=version, json=resultado.model_dump(mode="json")))
            for a in resultado.alertas_encontradas:
                sesion.add(AlertaBD(folio=doc.folio, documento_id=doc.id, codigo=a.codigo,
                                    severidad=a.severidad.value, mensaje=a.mensaje, confianza=a.confianza,
                                    campo=a.campo, version_resultado=version))
            doc.estado_analisis = resultado.estado_analisis.value  # completado o error, lo que diga el motor
            # TODO: recalcular EXP-001: cuenta el tipo confirmado > detectado > declarado; conservar si aplica=false
            auditoria.registrar(sesion, "documento_procesado", folio=doc.folio, documento_id=doc.id,
                                modelo=datos.get("modelo"), version_prompt=datos.get("version_prompt"),
                                detalle=_detalle_serializable(datos))
            sesion.commit()
        except Exception:
            log.exception("Fallo al guardar el resultado del documento %s", documento_id)
            _marcar_error(sesion, documento_id)


def _marcar_error(sesion, documento_id: uuid.UUID) -> None:
    sesion.rollback()
    doc = sesion.get(Documento, documento_id)
    if doc is not None:
        doc.estado_analisis = EstadoAnalisis.error.value
        sesion.commit()
