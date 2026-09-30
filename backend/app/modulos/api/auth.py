"""Router de autenticacion: POST /api/v1/auth/login y GET /api/v1/auth/yo (Contrato 2, ADR-006 H)."""
from functools import lru_cache

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.db import get_sesion
from app.core.errores import CABECERA_BEARER, ErrorApi
from app.core.modelos import Usuario
from app.core.seguridad import crear_token, hash_contrasena, usuario_actual, verificar_contrasena

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: str = Field(max_length=100)
    contrasena: str


class LoginSalida(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    rol: str
    expires_in: int  # segundos


class UsuarioYo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: str
    rol: str


@lru_cache
def _hash_ficticio() -> str:
    """Hash para comparar cuando el usuario no existe: el login tarda lo mismo exista o no."""
    return hash_contrasena("contrasena-ficticia-para-igualar-tiempos")


def _credenciales_invalidas() -> ErrorApi:
    return ErrorApi(401, "CREDENCIALES_INVALIDAS", "Usuario o contrasena incorrectos", CABECERA_BEARER)


@router.post("/login", response_model=LoginSalida)
def login(entrada: LoginEntrada, sesion: Session = Depends(get_sesion)) -> LoginSalida:
    usuario = sesion.scalar(select(Usuario).where(Usuario.usuario == entrada.usuario))
    try:
        valida = verificar_contrasena(entrada.contrasena,
                                      usuario.hash_contrasena if usuario else _hash_ficticio())
    except ValueError:  # mas de 72 bytes: misma respuesta que una contrasena incorrecta
        valida = False
    correcto = usuario is not None and valida

    auditoria.registrar(sesion, "login", usuario=entrada.usuario,
                        detalle={"resultado": "ok" if correcto else "fallido"})
    sesion.commit()
    if not correcto:
        raise _credenciales_invalidas()

    token, expires_in = crear_token(usuario.usuario, usuario.rol)
    return LoginSalida(access_token=token, rol=usuario.rol, expires_in=expires_in)


@router.get("/yo", response_model=UsuarioYo)
def yo(usuario: Usuario = Depends(usuario_actual)) -> UsuarioYo:
    return UsuarioYo(usuario=usuario.usuario, rol=usuario.rol)
