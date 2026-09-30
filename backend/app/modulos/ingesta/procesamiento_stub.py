"""Stub de `procesar_documento`: lo lanza la ingesta como BackgroundTask.

PERSONA_2 lo sustituira en la etapa 2 por el procesamiento real (orquestador + motor_ia). Mientras
tanto deja un `ResultadoDocumento` ficticio pero valido, para que el flujo y la UI funcionen.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.db import SesionLocal, get_engine
from app.core.modelos import AlertaBD, Documento, Resultado
from app.schemas.resultado import (Alerta, EstadoAnalisis, FechaYModelo, Recomendacion,
                                   ReferenciaArchivoOriginal, ResultadoDocumento)

log = logging.getLogger(__name__)

MODELO = "stub"
VERSION_PROMPT = "stub@v0"


def _alerta(a: AlertaBD) -> Alerta:
    return Alerta(id=str(a.id), codigo=a.codigo, mensaje=a.mensaje, severidad=a.severidad,
                  confianza=a.confianza, campo=a.campo, resuelta_por_revisor=a.resuelta_por_revisor,
                  aplica=a.aplica, comentario_revisor=a.comentario, resuelta_por=a.resuelta_por,
                  resuelta_en=a.resuelta_en)


def _resultado_ficticio(sesion: Session, doc: Documento) -> ResultadoDocumento:
    alertas = sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id == doc.id)
                             .order_by(AlertaBD.creado_en))
    return ResultadoDocumento(
        folio_solicitud=doc.folio,
        identificador_unico_documento=str(doc.id),
        tipo_documental_declarado=doc.tipo_declarado,
        tipo_documental_detectado=doc.tipo_declarado,
        confianza_clasificacion=1.0,
        datos_extraidos={},
        alertas_encontradas=[_alerta(a) for a in alertas],
        recomendacion=Recomendacion.revision_manual,
        estado_analisis=EstadoAnalisis.completado,
        fecha_y_modelo_utilizado=FechaYModelo(fecha_analisis=datetime.now(timezone.utc), proveedor="stub",
                                              modelo=MODELO, version_prompt=VERSION_PROMPT),
        referencia_archivo_original=ReferenciaArchivoOriginal(nombre_archivo=doc.nombre_archivo,
                                                              ruta=doc.ruta_s3, hash=doc.hash_sha256),
    )


def procesar_documento(documento_id: uuid.UUID) -> None:
    """Corre despues de la respuesta HTTP: abre su propia sesion y nunca relanza."""
    with SesionLocal(bind=get_engine()) as sesion:
        try:
            doc = sesion.get(Documento, documento_id)
            if doc is None:
                log.error("procesar_documento: no existe el documento %s", documento_id)
                return
            doc.estado_analisis = EstadoAnalisis.procesando.value
            sesion.commit()

            resultado = _resultado_ficticio(sesion, doc)
            version = (sesion.scalar(select(func.max(Resultado.version))
                                     .where(Resultado.documento_id == doc.id)) or 0) + 1
            sesion.add(Resultado(documento_id=doc.id, version=version, json=resultado.model_dump(mode="json")))
            doc.estado_analisis = EstadoAnalisis.completado.value
            auditoria.registrar(sesion, "documento_procesado", folio=doc.folio, documento_id=doc.id,
                                modelo=MODELO, version_prompt=VERSION_PROMPT)
            sesion.commit()
        except Exception:
            log.exception("Fallo al procesar el documento %s", documento_id)
            sesion.rollback()
            doc = sesion.get(Documento, documento_id)
            if doc is not None:
                doc.estado_analisis = EstadoAnalisis.error.value
                sesion.commit()
