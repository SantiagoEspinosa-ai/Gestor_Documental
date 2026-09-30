"""Errores de la API con el formato del Contrato 2: `{"codigo": "...", "mensaje": "..."}`.

Codigos: catalogo del ADR-006 1.4 (`docs/contratos/codigos_error.md`). Todo error de la API,
tambien los de validacion, rutas inexistentes y errores no controlados, sale con este formato.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

# 401 siempre con esta cabecera (RFC 6750)
CABECERA_BEARER = {"WWW-Authenticate": "Bearer"}


class ErrorApi(Exception):
    def __init__(self, http: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None):
        self.http = http
        self.codigo = codigo
        self.mensaje = mensaje
        self.headers = headers
        super().__init__(f"{http} {codigo}: {mensaje}")


def _respuesta(http: int, codigo: str, mensaje: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=http, content={"codigo": codigo, "mensaje": mensaje}, headers=headers)


async def manejar_error_api(request: Request, exc: ErrorApi) -> JSONResponse:
    return _respuesta(exc.http, exc.codigo, exc.mensaje, exc.headers)


async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Solo nombres de campo y tipo de fallo: los valores podrian ser contrasenas
    campos = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path", "header")]
        campos.append(f"{'.'.join(loc) or 'cuerpo'} ({err['type']})")
    return _respuesta(422, "PETICION_INVALIDA", f"Peticion no valida en: {', '.join(campos)}")


async def manejar_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo, mensaje = {
        404: ("RUTA_NO_ENCONTRADA", "Ruta no encontrada"),
        405: ("METODO_NO_PERMITIDO", "Metodo no permitido en esta ruta"),
    }.get(exc.status_code, ("PETICION_INVALIDA", "Peticion no valida"))
    return _respuesta(exc.status_code, codigo, mensaje, getattr(exc, "headers", None))


async def manejar_error_interno(request: Request, exc: Exception) -> JSONResponse:
    # La traza solo va al log; al cliente, nunca detalles internos
    log.exception("Error no controlado en %s %s", request.method, request.url.path)
    return _respuesta(500, "ERROR_INTERNO", "Error interno")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorApi, manejar_error_api)
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(StarletteHTTPException, manejar_http)
    app.add_exception_handler(Exception, manejar_error_interno)
