"""Tests de /api/v1/auth, de los manejadores globales de errores y de core/auditoria.py.

SQLite temporal y datos ficticios. TestClient(app) sin `with`: no se ejecuta el lifespan.
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auditoria, db
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import registrar_manejadores
from app.core.modelos import Auditoria
from app.main import app
from app.modulos.api import auth

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
CONTRASENA = "contrasena-ficticia"
LOGIN = "/api/v1/auth/login"

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
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        script.crear_usuario(s, "revisor_ficticio", "revisor", CONTRASENA)
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def cliente(sesion):
    return TestClient(app)


def _logins(sesion) -> list[tuple[str, str]]:
    sesion.expire_all()
    filas = sesion.scalars(select(Auditoria).where(Auditoria.accion == "login").order_by(Auditoria.id))
    return [(f.usuario, f.detalle["resultado"]) for f in filas]


def test_login_correcto_y_token_valido_en_yo(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA})
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"access_token", "rol", "expires_in"}
    assert (cuerpo["rol"], cuerpo["expires_in"]) == ("revisor", 480 * 60)

    yo = cliente.get("/api/v1/auth/yo", headers={"Authorization": f"Bearer {cuerpo['access_token']}"})
    assert yo.status_code == 200
    assert yo.json() == {"usuario": "revisor_ficticio", "rol": "revisor"}


def test_contrasena_mala_y_usuario_inexistente_responden_igual(cliente, monkeypatch):
    llamadas = []
    original = auth.verificar_contrasena

    def espia(texto, hash_guardado):
        llamadas.append(hash_guardado)
        return original(texto, hash_guardado)

    monkeypatch.setattr(auth, "verificar_contrasena", espia)
    mala = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "otra-contrasena"})
    inexistente = cliente.post(LOGIN, json={"usuario": "nadie_ficticio", "contrasena": "otra-contrasena"})

    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json() == {"codigo": "CREDENCIALES_INVALIDAS",
                                                  "mensaje": "Usuario o contrasena incorrectos"}
    assert mala.headers["www-authenticate"] == inexistente.headers["www-authenticate"] == "Bearer"
    assert len(llamadas) == 2  # tambien se verifica contra el hash ficticio
    assert llamadas[1] == auth._hash_ficticio()


def test_contrasena_de_80_bytes_da_401(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "x" * 80})
    assert (r.status_code, r.json()["codigo"]) == (401, "CREDENCIALES_INVALIDAS")


def test_falta_la_contrasena_422_sin_valores(cliente):
    r = cliente.post(LOGIN, json={"usuario": "valor-que-no-debe-salir"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "PETICION_INVALIDA"
    assert "contrasena" in r.json()["mensaje"]
    assert "valor-que-no-debe-salir" not in r.text


def test_campo_extra_422(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA,
                                  "token_type": "bearer"})
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")
    assert "token_type" in r.json()["mensaje"]


def test_yo_sin_token(cliente):
    r = cliente.get("/api/v1/auth/yo")
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")
    assert r.headers["www-authenticate"] == "Bearer"


def test_ruta_inexistente_404(cliente):
    r = cliente.get("/api/v1/no-existe")
    assert r.status_code == 404
    assert r.json() == {"codigo": "RUTA_NO_ENCONTRADA", "mensaje": "Ruta no encontrada"}


def test_metodo_no_permitido_405(cliente):
    r = cliente.get(LOGIN)
    assert (r.status_code, r.json()["codigo"]) == (405, "METODO_NO_PERMITIDO")


def test_error_no_controlado_500_sin_detalles():
    mini = FastAPI()
    registrar_manejadores(mini)

    @mini.get("/rompe")
    def rompe():
        raise RuntimeError("detalle interno secreto")

    r = TestClient(mini, raise_server_exceptions=False).get("/rompe")
    assert r.status_code == 500
    assert r.json() == {"codigo": "ERROR_INTERNO", "mensaje": "Error interno"}
    assert "detalle interno secreto" not in r.text


def test_una_fila_de_auditoria_por_intento(cliente, sesion):
    cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA})
    cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "otra-contrasena"})
    cliente.post(LOGIN, json={"usuario": "nadie_ficticio", "contrasena": "otra-contrasena"})
    assert _logins(sesion) == [("revisor_ficticio", "ok"), ("revisor_ficticio", "fallido"),
                               ("nadie_ficticio", "fallido")]
    for fila in sesion.scalars(select(Auditoria)):
        assert CONTRASENA not in str(fila.detalle)


def test_registrar_accion_desconocida(sesion):
    with pytest.raises(ValueError, match="desconocida"):
        auditoria.registrar(sesion, "borrar_todo")
