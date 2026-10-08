"""Procesamiento de un documento en segundo plano: descarga el original, llama al motor y guarda.

Corre como BackgroundTask despues de la respuesta HTTP: abre su propia sesion y nunca relanza.
Reparto con PERSONA_2: el motor hace las reglas del documento (VAL, REG, CLS) y su recomendacion;
la plataforma guarda el resultado y cada alerta del motor en la tabla `alertas` (asi reciben id).
"""
import json
import logging
import threading
import uuid
from functools import lru_cache

from sqlalchemy import func, select

from app.core import auditoria, webhooks
from app.core.almacenamiento import get_almacenamiento
from app.core.config import get_settings
from app.core.db import SesionLocal, get_engine
from app.core.modelos import AlertaBD, Documento, Folio, Proceso, Resultado
from app.modulos.ingesta import motor_stub
from app.modulos.orquestador import servicio as orquestador
from app.schemas.resultado import EstadoAnalisis, FaseAnalisis, ReferenciaArchivoOriginal

log = logging.getLogger(__name__)

_COLUMNAS_AUDITORIA = {"modelo", "version_prompt"}


def analizar(contenido: bytes, **kwargs):
    """El motor de MOTOR_ANALISIS (H10): `real` = `orquestador.servicio.procesar_documento` (PERSONA_2);
    `stub` = `motor_stub`, solo para pruebas sin Ollama (e2e de humo). Misma firma y mismos errores
    acordados: SYS-001/SYS-002 llegan como resultado en `error`; cualquier otra cosa lanza."""
    if get_settings().motor_analisis == "stub":
        return motor_stub.procesar_documento(contenido, **kwargs)
    return orquestador.procesar_documento(contenido, **kwargs)


# ADR-014: fase de cada analisis en curso, solo en memoria (un proceso uvicorn, como el semaforo). Se pierde al
# reiniciar; no va a la BD, a la auditoria ni a los webhooks. Lo lee construir_resultado (GET /documentos/{id} y
# el expediente) mientras el documento esta pendiente o procesando.
_fases: dict[uuid.UUID, FaseAnalisis] = {}
_cerrojo_fases = threading.Lock()


def fijar_fase(documento_id: uuid.UUID, fase: FaseAnalisis) -> None:
    with _cerrojo_fases:
        _fases[documento_id] = fase


def leer_fase(documento_id: uuid.UUID) -> FaseAnalisis | None:
    with _cerrojo_fases:
        return _fases.get(documento_id)


def borrar_fase(documento_id: uuid.UUID) -> None:
    with _cerrojo_fases:
        _fases.pop(documento_id, None)


@lru_cache
def _semaforo(tamano: int) -> threading.BoundedSemaphore:
    """Limite de llamadas simultaneas al motor (MAX_PROCESAMIENTOS_SIMULTANEOS, 1 por defecto).

    Con Ollama sin GPU cada documento tarda 60-250 s y varios a la vez agotan la RAM. Vale para un solo
    proceso uvicorn: las BackgroundTasks van en hilos del mismo proceso. Con varios workers haria falta
    una cola (fuera del MVP).
    """
    return threading.BoundedSemaphore(tamano)


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


def _expediente_servicio():
    """`expediente.servicio`, importado al usarlo y no arriba, para romper el ciclo de imports:
    expediente.servicio -> ingesta.servicio -> procesamiento -> expediente.servicio.
    Es su API publica (ADR-005); solo cambia el momento del import.
    """
    from app.modulos.expediente import servicio
    return servicio


def despues_del_commit(sesion, documento_id: uuid.UUID) -> None:
    """Tras guardar el analisis (o el error): regenera el resumen.md del folio y avisa por webhook."""
    try:
        doc = sesion.get(Documento, documento_id)
        if doc is not None:
            _expediente_servicio().regenerar_resumen(sesion, doc.folio)  # tampoco lanza
    except Exception:  # noqa: BLE001  el resumen no cambia el documento
        log.exception("No se pudo regenerar el resumen tras procesar el documento %s", documento_id)
    _notificar(sesion, documento_id)


def _notificar(sesion, documento_id: uuid.UUID) -> None:
    """Webhook documento.completado o documento.error, DESPUES del commit y en segundo plano (core/webhooks.py).
    Solo si el proceso del folio tiene `webhook_url`. Nunca lanza: un fallo no cambia el documento."""
    try:
        doc = sesion.get(Documento, documento_id)
        if doc is None or doc.estado_analisis not in (EstadoAnalisis.completado.value, EstadoAnalisis.error.value):
            return
        proceso = sesion.get(Proceso, sesion.get(Folio, doc.folio).proceso)
        if not proceso.webhook_url:
            return
        # El mismo armado que GET /documentos/{id}, enmascarado igual (ADR-010 A5); import diferido:
        # servicio importa este modulo
        from app.modulos.ingesta import servicio
        evento = "documento.completado" if doc.estado_analisis == EstadoAnalisis.completado.value else "documento.error"
        webhooks.enviar_en_segundo_plano(proceso.webhook_url, evento, doc.folio,
                                         servicio.enmascarar(servicio.construir_resultado(sesion, doc)),
                                         identificador=str(doc.id))
    except Exception:  # noqa: BLE001
        log.exception("No se pudo preparar el webhook del documento %s", documento_id)


def procesar(documento_id: uuid.UUID, tipo_confirmado: str | None = None) -> None:
    """Analiza el documento y guarda el resultado. La fase (ADR-014) se borra siempre al terminar: completado,
    error o excepcion."""
    try:
        _procesar(documento_id, tipo_confirmado)
    finally:
        borrar_fase(documento_id)


def _procesar(documento_id: uuid.UUID, tipo_confirmado: str | None) -> None:
    with SesionLocal(bind=get_engine()) as sesion:
        doc = sesion.get(Documento, documento_id)
        if doc is None:
            log.error("procesar: no existe el documento %s", documento_id)
            return
        doc.estado_analisis = EstadoAnalisis.procesando.value
        sesion.commit()

        try:
            contenido = get_almacenamiento().descargar(doc.ruta_s3)
            # Solo la llamada al motor va limitada; descarga y BD quedan fuera. Mientras espera su turno,
            # el documento sigue en "procesando" (la UI ya sondea) con la fase en_cola (ADR-014)
            doc_id = doc.id  # el callback no toca la sesion de SQLAlchemy (otro hilo puede avisar la fase)
            fijar_fase(doc_id, FaseAnalisis.en_cola)
            with _semaforo(get_settings().max_procesamientos_simultaneos):
                resultado, datos = analizar(
                    contenido, identificador=str(doc.id), nombre_archivo=doc.nombre_archivo,
                    tipo_declarado=doc.tipo_declarado, folio=doc.folio,
                    referencia=ReferenciaArchivoOriginal(nombre_archivo=doc.nombre_archivo, ruta=doc.ruta_s3,
                                                         hash=doc.hash_sha256),
                    tipo_confirmado=tipo_confirmado, al_avanzar=lambda fase: fijar_fase(doc_id, fase))
            if (resultado.identificador_unico_documento != str(doc.id)
                    or resultado.folio_solicitud != doc.folio):
                # Solo ids en el log: nada de datos extraidos
                raise ValueError(f"El motor devolvio un resultado de otro documento o folio ({doc.id})")
        except Exception:
            log.exception("Fallo al procesar el documento %s", documento_id)
            _marcar_error(sesion, documento_id)
            despues_del_commit(sesion, documento_id)  # documento.error, ya con el estado guardado
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
            doc.intentos_reanudar = 0  # el analisis ha terminado: el limite de reanudar vuelve a empezar
            expediente = _expediente_servicio()
            expediente.recalcular_exp001(sesion, doc.folio)
            expediente.recalcular_exp002(sesion, doc.folio)
            expediente.recalcular_cmp001(sesion, doc.folio)
            auditoria.registrar(sesion, "documento_procesado", folio=doc.folio, documento_id=doc.id,
                                modelo=datos.get("modelo"), version_prompt=datos.get("version_prompt"),
                                detalle=_detalle_serializable(datos))
            sesion.commit()
        except Exception:
            log.exception("Fallo al guardar el resultado del documento %s", documento_id)
            _marcar_error(sesion, documento_id)
        # Tras el commit (o tras marcar el error): completado o error segun lo guardado
        despues_del_commit(sesion, documento_id)


def _marcar_error(sesion, documento_id: uuid.UUID) -> None:
    sesion.rollback()
    doc = sesion.get(Documento, documento_id)
    if doc is not None:
        doc.estado_analisis = EstadoAnalisis.error.value
        sesion.commit()
