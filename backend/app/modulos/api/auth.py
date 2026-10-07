"""Router de autenticacion: POST /api/v1/auth/login y GET /api/v1/auth/yo (Contrato 2, ADR-006 H), con
limite de intentos fallidos por usuario (ADR-011)."""
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.config import get_settings
from app.core.db import get_sesion
from app.core.errores import CABECERA_BEARER, ErrorApi
from app.core.modelos import Auditoria, Usuario
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


def _segundos_bloqueado(sesion: Session, usuario: str) -> int | None:
    """ADR-011: segundos hasta poder volver a intentarlo, o None si no esta bloqueado.

    Cuenta en la auditoria los `login` fallidos del usuario escrito (exista o no) dentro de la ventana y
    posteriores a su ultimo `ok`. Sin estado nuevo: aguanta reinicios y varios workers. Los `bloqueado` no
    cuentan, para que insistir no alargue el bloqueo. Con `login_max_fallidos` o mas, se puede volver a
    intentar cuando el N-esimo mas reciente salga de la ventana (entonces quedan N-1).
    """
    ajustes = get_settings()
    ventana = timedelta(minutes=ajustes.login_ventana_minutos)
    ahora = datetime.now(timezone.utc)
    filas = sesion.execute(select(Auditoria.creado_en, Auditoria.detalle)
                           .where(Auditoria.accion == "login", Auditoria.usuario == usuario,
                                  Auditoria.creado_en >= ahora - ventana)
                           .order_by(Auditoria.creado_en.desc(), Auditoria.id.desc()))
    fallidos = []
    for creado_en, detalle in filas:
        resultado = (detalle or {}).get("resultado")
        if resultado == "ok":
            break
        if resultado == "fallido":
            # SQLite devuelve la fecha sin zona (CURRENT_TIMESTAMP es UTC); PostgreSQL, con zona
            fallidos.append(creado_en if creado_en.tzinfo else creado_en.replace(tzinfo=timezone.utc))
    if len(fallidos) < ajustes.login_max_fallidos:
        return None
    libre_en = fallidos[ajustes.login_max_fallidos - 1] + ventana
    return max(1, math.ceil((libre_en - ahora).total_seconds()))


@router.post("/login", response_model=LoginSalida)
def login(entrada: LoginEntrada, sesion: Session = Depends(get_sesion)) -> LoginSalida:
    # Antes de buscar el usuario y sin comprobar la contrasena: misma respuesta exista o no (ADR-011)
    segundos = _segundos_bloqueado(sesion, entrada.usuario)
    if segundos is not None:
        auditoria.registrar(sesion, "login", usuario=entrada.usuario, detalle={"resultado": "bloqueado"})
        sesion.commit()
        raise ErrorApi(429, "DEMASIADOS_INTENTOS", "Demasiados intentos fallidos; vuelve a intentarlo mas tarde",
                       {"Retry-After": str(segundos)})

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
