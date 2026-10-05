"""Webhooks de salida (Contrato 2, "Webhook (salida)"): POST firmado con HMAC-SHA256 y 3 reintentos.

Cuerpo: `{evento, fecha, folio, identificador_unico_documento?, datos}`; `datos` es un ResultadoDocumento
(documento.*) o un ResultadoExpediente (folio.estado_cambiado), serializado como en la API. Cabecera
`X-Firma: sha256=<hex HMAC-SHA256(cuerpo, WEBHOOK_SECRET_HMAC)>` sobre los mismos bytes que se envian.

core no importa modulos (ADR-005): quien llama pasa el resultado ya construido y la URL del proceso.
Se envia en un hilo aparte y despues del commit: un fallo nunca cambia el documento ni el folio. Los logs
solo llevan evento, folio, intento, estado HTTP y el host; nunca el cuerpo, la firma, el secreto ni la URL.
"""
import hashlib
import hmac
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

log = logging.getLogger(__name__)

EVENTOS = ("documento.completado", "documento.error", "folio.estado_cambiado")
# Primer intento inmediato y, si falla, 3 reintentos con esta espera antes de cada uno (segundos): 4 como maximo
ESPERAS_REINTENTO_S = (1, 5, 25)
TIMEOUT_S = 5
_MARCADOR_EJEMPLO = "CAMBIA_ESTO"  # valor de .env.example

# Para los tests: transporte de httpx (MockTransport) y forma de lanzar el envio
_transporte: httpx.BaseTransport | None = None


def _esperar(segundos: float) -> None:
    time.sleep(segundos)


def _lanzar(funcion: Callable[[], object]) -> None:
    """En un hilo aparte: el envio (hasta ~31 s con los reintentos) no retiene la peticion ni la tarea."""
    threading.Thread(target=funcion, name="webhook", daemon=True).start()


def enmascarar_para_webhook(datos: dict) -> dict:
    """ADR-010 A5: aqui se enmascaran los campos sensibles cuando llegue H15. Unico punto para el webhook.
    Con H15, este punto y `expediente/resumen.enmascarar_para_resumen` usaran la MISMA funcion de mascara
    (`****` + 4 ultimos caracteres), para que el webhook y el resumen no se separen."""
    return datos


def firmar(cuerpo: bytes, secreto: str) -> str:
    return "sha256=" + hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()


def construir_cuerpo(evento: str, folio: str, datos: BaseModel, identificador: str | None = None) -> bytes:
    """Bytes JSON del cuerpo del contrato. `identificador_unico_documento` solo en los eventos documento.*"""
    cuerpo = {"evento": evento, "fecha": datetime.now(timezone.utc).isoformat(), "folio": folio}
    if evento.startswith("documento."):
        cuerpo["identificador_unico_documento"] = identificador
    cuerpo["datos"] = enmascarar_para_webhook(datos.model_dump(mode="json"))
    return json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")


def _host(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.hostname or '?'}"


def _motivo_para_no_enviar(url: str) -> str | None:
    settings = get_settings()
    secreto = settings.webhook_secret_hmac.get_secret_value() if settings.webhook_secret_hmac else ""
    if not secreto:
        return "WEBHOOK_SECRET_HMAC vacio"
    if settings.app_env != "dev":
        if secreto.startswith(_MARCADOR_EJEMPLO):
            return "WEBHOOK_SECRET_HMAC tiene el valor de ejemplo"
        if urlsplit(url).scheme != "https":
            return "solo se admite https fuera de APP_ENV=dev"
    return None


def entregar(url: str, evento: str, folio: str, datos: BaseModel, identificador: str | None = None) -> bool:
    """Envia el evento: primer intento inmediato y hasta 3 reintentos (1, 5 y 25 s); True si alguno da 2xx. Los fallos de red o de destino no
    lanzan; solo un evento fuera del contrato (error de programacion)."""
    if evento not in EVENTOS:
        raise ValueError(f"evento desconocido: {evento}")
    motivo = _motivo_para_no_enviar(url)
    if motivo:
        log.warning("Webhook %s del folio %s no enviado a %s: %s", evento, folio, _host(url), motivo)
        return False
    cuerpo = construir_cuerpo(evento, folio, datos, identificador)
    cabeceras = {"Content-Type": "application/json",
                 "X-Firma": firmar(cuerpo, get_settings().webhook_secret_hmac.get_secret_value())}
    # Sin seguir redirecciones (un 3xx es un fallo) y verificando el certificado
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, verify=True, transport=_transporte) as cliente:
        for intento, espera in enumerate((0, *ESPERAS_REINTENTO_S), start=1):
            if espera:
                _esperar(espera)
            try:
                estado = cliente.post(url, content=cuerpo, headers=cabeceras).status_code
            except httpx.HTTPError as e:
                log.warning("Webhook %s del folio %s, intento %d a %s: sin respuesta (%s)",
                            evento, folio, intento, _host(url), type(e).__name__)
                continue
            if 200 <= estado < 300:
                log.info("Webhook %s del folio %s entregado a %s en el intento %d (HTTP %d)",
                         evento, folio, _host(url), intento, estado)
                return True
            log.warning("Webhook %s del folio %s, intento %d a %s: HTTP %d", evento, folio, intento, _host(url), estado)
    log.error("Webhook %s del folio %s no entregado a %s tras %d intentos", evento, folio, _host(url), 1 + len(ESPERAS_REINTENTO_S))
    return False


def enviar_en_segundo_plano(url: str | None, evento: str, folio: str, datos: BaseModel,
                            identificador: str | None = None) -> None:
    """Llamar DESPUES del commit. Sin `url` (el proceso no tiene webhook) no hace nada."""
    if not url:
        return

    def tarea() -> None:
        try:
            entregar(url, evento, folio, datos, identificador)
        except Exception:  # noqa: BLE001  un fallo del webhook no afecta a nada mas
            log.exception("Fallo inesperado al enviar el webhook %s del folio %s", evento, folio)

    _lanzar(tarea)
