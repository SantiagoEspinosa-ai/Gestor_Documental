"""Contrasenas (bcrypt), JWT (python-jose) y dependencias de FastAPI para autenticar y autorizar."""
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_sesion
from app.core.errores import CABECERA_BEARER, ErrorApi
from app.core.modelos import ROLES, Usuario

# bcrypt solo usa los primeros 72 bytes: por encima se rechaza en vez de truncar en silencio
_MAX_BYTES_BCRYPT = 72

_bearer = HTTPBearer(auto_error=False)


def _bytes_contrasena(texto: str) -> bytes:
    datos = texto.encode("utf-8")
    if len(datos) > _MAX_BYTES_BCRYPT:
        raise ValueError(f"La contrasena no puede superar {_MAX_BYTES_BCRYPT} bytes")
    return datos


def hash_contrasena(texto: str) -> str:
    return bcrypt.hashpw(_bytes_contrasena(texto), bcrypt.gensalt()).decode("ascii")


def verificar_contrasena(texto: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(_bytes_contrasena(texto), hash_guardado.encode("ascii"))


def crear_token(usuario: str, rol: str) -> tuple[str, int]:
    """JWT con sub, rol, iat y exp. Devuelve (token, expires_in en segundos) (ADR-006 H)."""
    settings = get_settings()
    expires_in = settings.jwt_expira_minutos * 60
    ahora = datetime.now(timezone.utc)
    claims = {"sub": usuario, "rol": rol, "iat": ahora, "exp": ahora + timedelta(seconds=expires_in)}
    token = jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algoritmo)
    return token, expires_in


def _no_autenticado() -> ErrorApi:
    return ErrorApi(401, "NO_AUTENTICADO", "Falta el token de acceso o no es valido", CABECERA_BEARER)


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sesion: Session = Depends(get_sesion),
) -> Usuario:
    """Usuario del token Bearer, cargado de BD. 401 si falta, es invalido, ha caducado o ya no existe."""
    if credenciales is None:
        raise _no_autenticado()
    settings = get_settings()
    try:
        claims = jwt.decode(credenciales.credentials, settings.secret_key.get_secret_value(),
                            algorithms=[settings.jwt_algoritmo])
    except ExpiredSignatureError:
        raise ErrorApi(401, "TOKEN_CADUCADO", "La sesion ha caducado; vuelve a iniciar sesion",
                       CABECERA_BEARER) from None
    except JWTError:
        raise _no_autenticado() from None

    usuario = sesion.scalar(select(Usuario).where(Usuario.usuario == claims.get("sub")))
    if usuario is None:
        raise _no_autenticado()
    return usuario


def es_folio_ajeno(usuario: Usuario, creado_por: str | None) -> bool:
    """ADR-012 (propuesto): el integrador solo accede a los folios que ha creado. Un folio anterior a la
    columna (creado_por NULL) no es de ningun integrador. Revisor y admin ven todos. Quien llama responde
    404, como si el folio no existiera, para no revelar que existe."""
    return usuario.rol == "integrador" and creado_por != usuario.usuario


def requiere_rol(*roles: str):
    """Dependencia que exige uno de los roles dados. 403 SIN_PERMISO si no."""
    desconocidos = set(roles) - set(ROLES)
    if not roles or desconocidos:
        raise ValueError(f"Roles no validos: {sorted(desconocidos) or 'ninguno'}")

    def _comprobar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise ErrorApi(403, "SIN_PERMISO", "Tu rol no tiene permiso para esta accion")
        return usuario

    return _comprobar
