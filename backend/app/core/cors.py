"""CORS con los origenes de `CORS_ORIGENES` (Settings).

Los Settings no se pueden leer al importar `main.py` (en los tests el entorno se fija despues), asi que
el `CORSMiddleware` de Starlette se construye con los Settings vigentes en la primera peticion y se
rehace si cambian (`get_settings.cache_clear()`).
"""
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings, get_settings

# Los metodos del Contrato 2; OPTIONS (preflight) lo responde el propio middleware
METODOS = ["GET", "POST", "PATCH", "OPTIONS"]
# El token va en la cabecera Authorization, no en cookies: sin credenciales
CABECERAS = ["Authorization", "Content-Type"]


class CorsDesdeSettings:
    def __init__(self, app: ASGIApp):
        self.app = app
        self._settings: Settings | None = None
        self._cors: CORSMiddleware | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan y websockets pasan sin tocar
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        if settings is not self._settings:
            self._cors = CORSMiddleware(self.app, allow_origins=settings.cors_origenes, allow_methods=METODOS,
                                        allow_headers=CABECERAS, allow_credentials=False)
            self._settings = settings
        await self._cors(scope, receive, send)
