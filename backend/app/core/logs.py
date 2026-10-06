"""Filtro de logs para datos sensibles (ADR-010 A5): ultima barrera por si un valor llega a un log.

La regla es no escribir nunca valores de `datos_extraidos` en los logs (como mucho el nombre del campo);
este filtro tapa, ademas, lo que tenga forma de dato sensible en el mensaje, en la traza de la excepcion
y en el stack: CURP, clave de elector, numero de pasaporte y lineas MRZ. Respeta ids, folios
(ONB-2026-000001) y UUID (en minusculas, como los genera Python).

`instalar()` se llama al arrancar la app (main.py). Un filtro de logger solo ve lo que se registra en
ESE logger, no lo que le llega por propagacion; por eso se pone tambien en los handlers del logger raiz,
en los de los loggers ya creados (uvicorn configura los suyos antes de cargar la app) y en
`logging.lastResort` (el que escribe si el raiz no tiene handlers).
"""
import logging
import re

MASCARA = "****"
_PATRONES = (
    re.compile(r"(?<![A-Z0-9<])[A-Z0-9<]{30,}(?![A-Z0-9<])"),          # linea MRZ
    re.compile(r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d"),                  # CURP
    re.compile(r"[A-Z]{6}\d{8}[HM]\d{3}"),                               # clave de elector
    re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{8,9}\b"),  # numero de pasaporte (palabra completa)
)


def tapar(texto: str) -> str:
    for patron in _PATRONES:
        texto = patron.sub(MASCARA, texto)
    return texto


class FiltroDatosSensibles(logging.Filter):
    """Reescribe el registro con el mensaje ya formateado y tapado. Nunca descarta un registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            mensaje = record.getMessage()
        except Exception:  # noqa: BLE001  argumentos que no casan: que lo trate el handler
            return True
        record.msg, record.args = tapar(mensaje), None
        if record.exc_info:
            # Se formatea aqui y se quita exc_info: asi ningun formateador vuelve a escribir la traza sin tapar
            record.exc_text = record.exc_text or logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
        if record.exc_text:
            record.exc_text = tapar(record.exc_text)
        if record.stack_info:
            record.stack_info = tapar(record.stack_info)
        return True


_FILTRO = FiltroDatosSensibles()


def _anadir(destino: logging.Filterer) -> None:
    if _FILTRO not in destino.filters:
        destino.addFilter(_FILTRO)


def instalar() -> None:
    """Idempotente. Raiz (logger y handlers), handlers de los loggers existentes y lastResort."""
    raiz = logging.getLogger()
    _anadir(raiz)
    handlers = list(raiz.handlers)
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            handlers += logger.handlers
    if logging.lastResort is not None:
        handlers.append(logging.lastResort)
    for handler in handlers:
        _anadir(handler)
