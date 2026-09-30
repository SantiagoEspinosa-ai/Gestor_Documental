"""Tests de app/core/modelos.py y de la migracion 0001, sin PostgreSQL.

Se usa un fichero SQLite temporal: Alembic abre varias conexiones y con `sqlite://` en memoria
cada una veria una BD vacia distinta. Datos ficticios siempre.
"""
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.modelos import AlertaBD, Documento, Folio, Proceso, Resultado, Usuario

BACKEND = Path(__file__).resolve().parents[1]
TABLAS = {"usuarios", "procesos", "folios", "documentos", "resultados", "alertas", "correcciones",
          "auditoria"}


@pytest.fixture
def bd(monkeypatch, tmp_path):
    """BD SQLite migrada con `alembic upgrade head`. Devuelve (config de alembic, engine)."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test",
        "DATABASE_URL": url,
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test",
        "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test",
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test",
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()

    config = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield config, engine
    engine.dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def sesion(bd):
    _, engine = bd
    with Session(engine) as s:
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                      tipos_opcionales=[], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        s.add(Folio(folio="ONB-2026-000001", proceso="onboarding", anio=2026, secuencia=1))
        s.commit()
        yield s


def _documento(s: Session) -> Documento:
    doc = Documento(folio="ONB-2026-000001", nombre_archivo="credencial_ficticia.pdf",
                    ruta_s3="onboarding/2026/000001/x.pdf", hash_sha256="0" * 64)
    s.add(doc)
    s.commit()
    return doc


def test_upgrade_crea_las_8_tablas_y_downgrade_las_borra(bd):
    config, engine = bd
    assert TABLAS <= set(inspect(engine).get_table_names())
    command.downgrade(config, "base")
    assert not TABLAS & set(inspect(engine).get_table_names())


def test_rol_invalido_falla_por_la_check(sesion):
    sesion.add(Usuario(usuario="usuario_ficticio", hash_contrasena="x", rol="superusuario"))
    with pytest.raises(IntegrityError, match="ck_usuarios_rol"):
        sesion.commit()


def test_folio_repetido_por_proceso_anio_secuencia_falla(sesion):
    sesion.add(Folio(folio="ONB-2026-000001-BIS", proceso="onboarding", anio=2026, secuencia=1))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        sesion.commit()


def test_valores_por_defecto_del_folio_y_del_documento(sesion):
    folio = sesion.get(Folio, "ONB-2026-000001")
    assert folio.estado_general == "en_revision"
    assert folio.creado_en is not None
    assert _documento(sesion).estado_analisis == "pendiente"


def test_alerta_de_expediente_sin_documento(sesion):
    alerta = AlertaBD(folio="ONB-2026-000001", documento_id=None, codigo="EXP-001",
                      severidad="bloqueante", mensaje="Falta un tipo requerido", confianza=1.0)
    sesion.add(alerta)
    sesion.commit()
    guardada = sesion.get(AlertaBD, alerta.id)
    assert isinstance(guardada.id, uuid.UUID)
    assert guardada.documento_id is None
    assert guardada.resuelta_por_revisor is False
    assert guardada.aplica is None


def test_severidad_invalida_falla_por_la_check(sesion):
    sesion.add(AlertaBD(folio="ONB-2026-000001", codigo="X", severidad="urgente", mensaje="x",
                        confianza=0.5))
    with pytest.raises(IntegrityError, match="ck_alertas_severidad"):
        sesion.commit()


def test_resultados_versionados_por_documento(sesion):
    doc = _documento(sesion)
    sesion.add_all([Resultado(documento_id=doc.id, version=1, json={"v": 1}),
                    Resultado(documento_id=doc.id, version=2, json={"v": 2})])
    sesion.commit()
    assert sesion.query(Resultado).filter_by(documento_id=doc.id).count() == 2

    sesion.add(Resultado(documento_id=doc.id, version=2, json={"v": "repetida"}))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        sesion.commit()
