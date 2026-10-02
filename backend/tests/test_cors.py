"""Tests de CORS (CORS_ORIGENES en core/config.py y core/cors.py). Sin BD ni .env real."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app

SECRETO = "clave-ficticia-de-test"
VITE = "http://localhost:5173"


@pytest.fixture
def entorno(monkeypatch):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": "sqlite://",
        "AWS_ACCESS_KEY_ID": SECRETO,
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": SECRETO,
        "CORS_ORIGENES": VITE,
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _preflight(origen: str):
    # Sin "with": no se ejecuta el lifespan (no hace falta BD para un preflight)
    return TestClient(app).options("/api/v1/folios", headers={
        "Origin": origen, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type"})


def test_por_defecto_el_origen_de_vite(entorno):
    entorno.delenv("CORS_ORIGENES")
    assert Settings(_env_file=None).cors_origenes == [VITE]


def test_lista_separada_por_comas_sin_espacios(entorno):
    entorno.setenv("CORS_ORIGENES", f" {VITE} , http://127.0.0.1:5173 ,")
    assert Settings(_env_file=None).cors_origenes == [VITE, "http://127.0.0.1:5173"]


def test_el_comodin_no_se_admite(entorno):
    entorno.setenv("CORS_ORIGENES", f"{VITE},*")
    with pytest.raises(ValidationError, match="comodin"):
        Settings(_env_file=None)


def test_preflight_desde_vite_recibe_allow_origin(entorno):
    r = _preflight(VITE)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == VITE
    assert "access-control-allow-credentials" not in r.headers
    assert {"GET", "POST", "PATCH"} <= set(r.headers["access-control-allow-methods"].replace(" ", "").split(","))


def test_preflight_desde_otro_origen_no_recibe_allow_origin(entorno):
    r = _preflight("http://evil.example")
    assert "access-control-allow-origin" not in r.headers


def test_el_comodin_impide_arrancar(entorno):
    entorno.setenv("CORS_ORIGENES", f"{VITE},*")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="comodin"):
        with TestClient(app):
            pass
