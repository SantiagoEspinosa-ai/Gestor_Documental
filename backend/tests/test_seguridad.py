"""Tests de app/core/seguridad.py, errores.py y scripts/crear_usuario.py.

SQLite temporal y claves ficticias. Las dependencias se prueban con una mini app de FastAPI
del test: todavia no hay routers.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import ErrorApi, manejar_error_api
from app.core.modelos import Usuario
from app.core.seguridad import (crear_token, hash_contrasena, requiere_rol, usuario_actual,
                                verificar_contrasena)

SECRETO = "clave-ficticia-de-test"
CONTRASENA = "contrasena-ficticia"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": SECRETO,
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": SECRETO,
        "JWT_EXPIRA_MINUTOS": "30",
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def cliente(sesion):
    app = FastAPI()
    app.add_exception_handler(ErrorApi, manejar_error_api)

    @app.get("/yo")
    def yo(usuario: Usuario = Depends(usuario_actual)):
        return {"usuario": usuario.usuario, "rol": usuario.rol}

    @app.get("/solo-admin")
    def solo_admin(usuario: Usuario = Depends(requiere_rol("admin"))):
        return {"ok": True}

    return TestClient(app)


def _usuario(sesion, nombre="revisor_ficticio", rol="revisor") -> Usuario:
    return script.crear_usuario(sesion, nombre, rol, CONTRASENA)


def _cabecera(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- contrasenas ---

def test_hash_y_verificacion():
    h = hash_contrasena(CONTRASENA)
    assert h != CONTRASENA
    assert verificar_contrasena(CONTRASENA, h)
    assert not verificar_contrasena("otra-contrasena", h)


def test_mas_de_72_bytes_falla():
    with pytest.raises(ValueError, match="72 bytes"):
        hash_contrasena("a" * 73)
    with pytest.raises(ValueError, match="72 bytes"):
        hash_contrasena("ñ" * 37)  # 74 bytes en UTF-8


# --- tokens y dependencias ---

def test_token_de_ida_y_vuelta(sesion):
    token, expires_in = crear_token("revisor_ficticio", "revisor")
    claims = jwt.decode(token, SECRETO, algorithms=["HS256"])
    assert (claims["sub"], claims["rol"]) == ("revisor_ficticio", "revisor")
    assert expires_in == 30 * 60
    assert claims["exp"] - claims["iat"] == expires_in


def test_usuario_actual_con_token_valido(cliente, sesion):
    _usuario(sesion)
    token, _ = crear_token("revisor_ficticio", "revisor")
    r = cliente.get("/yo", headers=_cabecera(token))
    assert r.status_code == 200
    assert r.json() == {"usuario": "revisor_ficticio", "rol": "revisor"}


def test_token_caducado(cliente, sesion):
    _usuario(sesion)
    pasado = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = jwt.encode({"sub": "revisor_ficticio", "rol": "revisor", "iat": pasado - timedelta(hours=1),
                        "exp": pasado}, SECRETO, algorithm="HS256")
    r = cliente.get("/yo", headers=_cabecera(token))
    assert (r.status_code, r.json()["codigo"]) == (401, "TOKEN_CADUCADO")


def test_token_firmado_con_otra_clave(cliente, sesion):
    _usuario(sesion)
    token = jwt.encode({"sub": "revisor_ficticio", "rol": "admin",
                        "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       "otra-clave-ficticia", algorithm="HS256")
    r = cliente.get("/yo", headers=_cabecera(token))
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")


def test_sin_cabecera(cliente):
    r = cliente.get("/yo")
    assert r.status_code == 401
    assert r.json() == {"codigo": "NO_AUTENTICADO", "mensaje": "Falta el token de acceso o no es valido"}


def test_usuario_borrado_de_la_bd(cliente, sesion):
    usuario = _usuario(sesion)
    token, _ = crear_token("revisor_ficticio", "revisor")
    sesion.delete(usuario)
    sesion.commit()
    r = cliente.get("/yo", headers=_cabecera(token))
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")


def test_rol_no_permitido(cliente, sesion):
    _usuario(sesion)
    token, _ = crear_token("revisor_ficticio", "revisor")
    r = cliente.get("/solo-admin", headers=_cabecera(token))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")


def test_rol_permitido(cliente, sesion):
    _usuario(sesion, "admin_ficticio", "admin")
    token, _ = crear_token("admin_ficticio", "admin")
    assert cliente.get("/solo-admin", headers=_cabecera(token)).status_code == 200


def test_el_rol_sale_de_la_bd_no_del_token(cliente, sesion):
    _usuario(sesion)  # revisor en BD
    token, _ = crear_token("revisor_ficticio", "admin")
    assert cliente.get("/solo-admin", headers=_cabecera(token)).status_code == 403


def test_requiere_rol_valida_los_roles_al_definirse():
    with pytest.raises(ValueError, match="superusuario"):
        requiere_rol("admin", "superusuario")


# --- scripts/crear_usuario.py ---

def test_crear_usuario_guarda_hash_y_no_la_contrasena(sesion):
    usuario = _usuario(sesion)
    assert usuario.hash_contrasena != CONTRASENA
    assert CONTRASENA not in usuario.hash_contrasena
    assert verificar_contrasena(CONTRASENA, usuario.hash_contrasena)


def test_crear_usuario_duplicado_falla(sesion):
    _usuario(sesion)
    with pytest.raises(ValueError, match="ya existe"):
        _usuario(sesion)


def test_crear_usuario_reemplazar(sesion):
    _usuario(sesion)
    usuario = script.crear_usuario(sesion, "revisor_ficticio", "admin", "otra-contrasena-ficticia",
                                   reemplazar=True)
    assert usuario.rol == "admin"
    assert verificar_contrasena("otra-contrasena-ficticia", usuario.hash_contrasena)
    assert sesion.query(Usuario).count() == 1


def test_crear_usuario_contrasena_corta(sesion):
    with pytest.raises(ValueError, match="al menos 8"):
        script.crear_usuario(sesion, "revisor_ficticio", "revisor", "corta")
