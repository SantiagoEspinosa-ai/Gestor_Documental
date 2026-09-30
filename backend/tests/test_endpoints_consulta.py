"""Tests de los endpoints de consulta (GET /procesos, ...). SQLite temporal, datos ficticios."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import Proceso
from app.core.seguridad import crear_token
from app.main import app

SECRETO = "clave-ficticia-de-test"

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
    monkeypatch.delenv("CONFIG_DIR", raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add_all([
            Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                    tipos_opcionales=["pasaporte"], permitir_antecedentes=True, caducidad_antecedentes_dias=365,
                    webhook_url=None, modelos="default"),
            Proceso(nombre="alta_proveedor", prefijo_folio="ALT", tipos_requeridos=["comprobante_domicilio"],
                    tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=30,
                    webhook_url="https://integrador.ejemplo.invalid/webhook", modelos="default"),
        ])
        for rol in ("admin", "revisor", "integrador"):
            script.crear_usuario(s, f"{rol}_ficticio", rol, "contrasena-ficticia")
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def cliente(sesion):
    return TestClient(app)


def _cab(rol: str) -> dict:
    return {"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"}


# --- GET /procesos ---

CAMPOS_PROCESO = {"nombre", "prefijo_folio", "tipos_requeridos", "tipos_opcionales", "permitir_antecedentes",
                  "caducidad_antecedentes_dias", "webhook_url", "modelos"}


@pytest.mark.parametrize("rol", ["admin", "integrador"])
def test_procesos_completos_para_admin_e_integrador(cliente, rol):
    r = cliente.get("/api/v1/procesos", headers=_cab(rol))
    assert r.status_code == 200
    procesos = r.json()
    assert [p["nombre"] for p in procesos] == ["alta_proveedor", "onboarding"]
    assert all(set(p) == CAMPOS_PROCESO for p in procesos)
    assert procesos[1]["webhook_url"] is None  # nulo, pero presente
    assert procesos[0]["webhook_url"] == "https://integrador.ejemplo.invalid/webhook"


def test_procesos_sin_configuracion_para_el_revisor(cliente):
    procesos = cliente.get("/api/v1/procesos", headers=_cab("revisor")).json()
    assert len(procesos) == 2
    assert all(set(p) == CAMPOS_PROCESO - {"webhook_url", "modelos"} for p in procesos)
    assert procesos[1]["tipos_opcionales"] == ["pasaporte"]


def test_procesos_sin_token(cliente):
    r = cliente.get("/api/v1/procesos")
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")


# --- GET /tipos-documentales ---

CAMPOS_TIPO = {"nombre", "nombre_visible", "categoria", "descripcion", "formatos_permitidos", "campos",
               "confianza_minima_clasificacion", "confianza_minima_campo", "reglas", "comparaciones"}


def test_tipos_documentales(cliente):
    r = cliente.get("/api/v1/tipos-documentales", headers=_cab("integrador"))
    assert r.status_code == 200
    tipos = r.json()
    assert [t["nombre"] for t in tipos] == ["comprobante_domicilio", "credencial_elector", "pasaporte"]
    for t in tipos:
        assert set(t) == CAMPOS_TIPO
        assert t["formatos_permitidos"] == ["pdf", "jpg", "jpeg", "png"]
        for campo in t["campos"].values():
            assert set(campo) in ({"tipo", "obligatorio"}, {"tipo", "obligatorio", "patron"})
    pasaporte = tipos[2]
    assert pasaporte["campos"]["numero_pasaporte"]["patron"] == "^[A-Z0-9]{8,9}$"
    assert "patron" not in pasaporte["campos"]["nombre_completo"]
    assert pasaporte["comparaciones"] == {"credencial_elector": ["nombre_completo", "fecha_nacimiento"]}
    assert pasaporte["confianza_minima_clasificacion"] == 0.85



def test_tipos_documentales_sin_token(cliente):
    r = cliente.get("/api/v1/tipos-documentales")
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")
