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
from collections.abc import Mapping
from typing import Any

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


def _tapar_valor(valor: Any) -> Any:
    """Un argumento del mensaje, tapado sin cambiar su tipo cuando no hace falta: los numeros, booleanos y
    None pasan tal cual (siguen valiendo para %d o %f); un str se tapa; cualquier otro objeto (una excepcion,
    un objeto con __str__) se convierte a texto solo si ese texto lleva algo que tapar."""
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    if isinstance(valor, str):
        return tapar(valor)
    texto = str(valor)
    tapado = tapar(texto)
    return tapado if tapado != texto else valor


def _tapar_args(args: Any) -> Any:
    """Los args del registro con el mismo tipo: tupla -> tupla, Mapping -> dict (para %(clave)s) y uno solo
    igual. Asi los formateadores que leen los args por posicion (uvicorn.access) siguen funcionando."""
    if isinstance(args, tuple):
        return tuple(_tapar_valor(a) for a in args)
    if isinstance(args, Mapping):
        return {clave: _tapar_valor(valor) for clave, valor in args.items()}
    return _tapar_valor(args)


class FiltroDatosSensibles(logging.Filter):
    """Tapa el mensaje y cada argumento por separado, sin formatear el registro: el formateador de cada
    handler (p. ej. el AccessFormatter de uvicorn, que lee los args por posicion) recibe los args con su forma.
    Nunca lanza ni descarta un registro: si algo falla, lo ya tapado se queda y el resto sigue como estaba."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = tapar(record.msg)
            if record.args:
                record.args = _tapar_args(record.args)
        except Exception:  # noqa: BLE001  el filtro nunca rompe el log
            pass
        try:
            if record.exc_info:
                # Se formatea aqui y se quita exc_info: asi ningun formateador vuelve a escribir la traza sin tapar
                record.exc_text = record.exc_text or logging.Formatter().formatException(record.exc_info)
                record.exc_info = None
            if record.exc_text:
                record.exc_text = tapar(record.exc_text)
            if record.stack_info:
                record.stack_info = tapar(record.stack_info)
        except Exception:  # noqa: BLE001
            pass
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
