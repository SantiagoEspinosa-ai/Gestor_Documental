"""Errores de la API con el formato del Contrato 2: `{"codigo": "...", "mensaje": "..."}`.

Codigos: catalogo del ADR-006 1.4 (`docs/contratos/codigos_error.md`).
"""
from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorApi(Exception):
    def __init__(self, http: int, codigo: str, mensaje: str):
        self.http = http
        self.codigo = codigo
        self.mensaje = mensaje
        super().__init__(f"{http} {codigo}: {mensaje}")


async def manejar_error_api(request: Request, exc: ErrorApi) -> JSONResponse:
    return JSONResponse(status_code=exc.http, content={"codigo": exc.codigo, "mensaje": exc.mensaje})
