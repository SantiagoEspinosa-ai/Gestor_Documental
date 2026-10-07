"""Tests de app/core/db.py sin PostgreSQL: SQLite en memoria y entorno por monkeypatch."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def sqlite_en_memoria(monkeypatch):
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test-de-32-caracteres",
        "DATABASE_URL": "sqlite://",
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test-de-32-caracteres",
        "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test-de-32-caracteres",
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test-de-32-caracteres",
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    yield
    get_settings.cache_clear()
    db.get_engine.cache_clear()


def test_importar_db_no_crea_el_engine():
    # Proceso limpio y sin DATABASE_URL: si importar conectara o leyera settings, fallaria
    entorno = {k: v for k, v in os.environ.items() if k.upper() != "DATABASE_URL"}
    codigo = "import app.core.db as db; assert db.get_engine.cache_info().currsize == 0"
    subprocess.run([sys.executable, "-c", codigo], check=True, env=entorno, cwd=BACKEND)


def test_get_sesion_da_una_sesion_que_funciona_y_se_cierra(sqlite_en_memoria):
    generador = db.get_sesion()
    sesion = next(generador)
    assert isinstance(sesion, Session)
    assert sesion.execute(text("SELECT 1")).scalar() == 1
    assert sesion.in_transaction()

    with pytest.raises(StopIteration):
        next(generador)
    assert not sesion.in_transaction()
