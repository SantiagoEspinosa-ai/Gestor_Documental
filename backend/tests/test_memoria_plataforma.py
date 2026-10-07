"""H14, parte de la plataforma: regenerar_resumen indexa el resumen.md enmascarado en la memoria de folios,
el script de reindexado y la migracion 0005. Mismo entorno que test_enmascaramiento_api (SQLite temporal +
moto, motor falso con datos sensibles ficticios). Datos ficticios."""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.engine import make_url

from app.core import db
from app.core.config import get_settings
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.rag.modelos import MemoriaFolio
from tests.test_enmascaramiento_api import SENSIBLES, _cliente, entorno  # noqa: F401

BACKEND = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("reindexar", BACKEND.parent / "scripts" / "reindexar_resumenes.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


class S3Roto:
    def subir_derivado(self, datos, clave, tipo_contenido):
        raise RuntimeError("S3 caido (ficticio)")

    def descargar(self, clave):
        raise RuntimeError("S3 caido (ficticio)")


def _folio_con_documentos(entorno, decidir: bool = True) -> str:
    """Folio con una credencial y un pasaporte con datos sensibles; rechazado si `decidir`."""
    sesion, s3, _ = entorno
    folio = expediente.crear_folio(sesion, "onboarding", "CLI-000101", "x").folio
    for nombre, tipo in (("c.pdf", "credencial_elector"), ("p.pdf", "pasaporte")):
        doc = ingestar(sesion, s3, folio, nombre, f"%PDF-1.4 {uuid.uuid4()}".encode(), tipo, "x")
        procesamiento.procesar(doc.id)
    if decidir:
        r = _cliente("revisor").post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})
        assert r.status_code == 200
    return folio


def _memoria(sesion, folio) -> MemoriaFolio | None:
    sesion.expire_all()
    return sesion.get(MemoriaFolio, folio)


def test_tras_decidir_el_folio_queda_indexado_sin_valores_sensibles(entorno):
    sesion = entorno[0]
    folio = _folio_con_documentos(entorno)
    fila = _memoria(sesion, folio)
    assert fila is not None and fila.fragmento.strip()
    assert "Decision: Rechazado" in fila.resumen_md and "Decision: Rechazado" in fila.fragmento
    assert r"\*\*\*\*" in fila.resumen_md  # los datos del resumen, enmascarados (Markdown escapa los *)
    for valor in SENSIBLES:
        assert valor not in fila.resumen_md and valor not in fila.fragmento
    # El mismo texto que se sube a S3
    assert fila.resumen_md == _cliente("admin").get(f"/api/v1/folios/{folio}/resumen.md").text


def test_si_s3_falla_se_indexa_igual(entorno, monkeypatch):
    sesion = entorno[0]
    monkeypatch.setattr(expediente, "_almacenamiento", lambda: S3Roto())
    folio = _folio_con_documentos(entorno)
    fila = _memoria(sesion, folio)
    assert fila is not None and "Decision: Rechazado" in fila.resumen_md


def test_si_indexar_falla_la_decision_responde_200(entorno, monkeypatch):
    sesion = entorno[0]

    def roto(*args, **kwargs):
        raise RuntimeError("memoria caida (ficticio)")
    monkeypatch.setattr(expediente.rag, "indexar_resumen", roto)
    folio = _folio_con_documentos(entorno, decidir=False)
    r = _cliente("revisor").post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})
    assert (r.status_code, r.json()["estado_general"]) == (200, "rechazado")
    assert _memoria(sesion, folio) is None


def test_el_script_indexa_los_cerrados_y_con_solo_cerrados_no_toca_los_abiertos(entorno, capsys):
    sesion = entorno[0]
    cerrado = _folio_con_documentos(entorno)
    abierto = _folio_con_documentos(entorno, decidir=False)
    sesion.execute(delete(MemoriaFolio))  # como antes de desplegar la memoria
    sesion.commit()

    assert script.reindexar(sesion, solo_cerrados=True) == (1, [])
    assert _memoria(sesion, cerrado) is not None and _memoria(sesion, abierto) is None

    assert script.reindexar(sesion) == (2, [])
    fila = _memoria(sesion, abierto)
    assert fila is not None and all(v not in fila.resumen_md for v in SENSIBLES)


def test_el_script_informa_de_los_fallidos_sin_contenido(entorno, monkeypatch, capsys):
    sesion = entorno[0]
    folio = _folio_con_documentos(entorno)
    monkeypatch.setattr(expediente.rag, "indexar_resumen", lambda *a, **k: None)  # no indexa nada
    sesion.execute(delete(MemoriaFolio))
    sesion.commit()
    assert script.reindexar(sesion) == (1, [folio])
    monkeypatch.setattr(script, "SesionLocal", lambda bind: sesion)
    monkeypatch.setattr(sesion, "close", lambda: None)
    monkeypatch.setattr("sys.argv", ["reindexar_resumenes.py"])
    assert script.main() == 1
    salida = capsys.readouterr().out
    assert salida.splitlines() == ["Folios procesados: 1", f"Fallidos: 1 ({folio})"]


# --- migracion 0005 ---

def _alembic(monkeypatch, url: str) -> Config:
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test-de-32-caracteres", "DATABASE_URL": url,
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test-de-32-caracteres", "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test-de-32-caracteres",
        "S3_BUCKET": "bucket-de-test", "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test-de-32-caracteres",
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    return Config(str(BACKEND / "alembic.ini"))


def _sube_y_baja(config: Config, url: str) -> None:
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        columnas = {c["name"]: c for c in inspect(engine).get_columns("memoria_folios")}
        assert set(columnas) == {"folio", "resumen_md", "fragmento", "actualizado_en"}
        assert not any(c["nullable"] for c in columnas.values())
        assert inspect(engine).get_pk_constraint("memoria_folios")["constrained_columns"] == ["folio"]
        [fk] = inspect(engine).get_foreign_keys("memoria_folios")
        assert (fk["referred_table"], fk["referred_columns"]) == ("folios", ["folio"])
        command.downgrade(config, "-1")
        assert "memoria_folios" not in inspect(engine).get_table_names()
        assert "folios" in inspect(engine).get_table_names()  # solo baja la 0005
        command.upgrade(config, "head")
        assert "memoria_folios" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_migracion_0005_sube_y_baja_en_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'migraciones.db'}"
    try:
        _sube_y_baja(_alembic(monkeypatch, url), url)
    finally:
        get_settings.cache_clear()
        db.get_engine.cache_clear()


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requiere TEST_POSTGRES_URL")
def test_migraciones_suben_y_bajan_en_postgres(monkeypatch):
    # BD propia y vacia: la de TEST_POSTGRES_URL la usan otros tests con create_all, sin alembic_version
    base = make_url(os.environ["TEST_POSTGRES_URL"])
    nombre = "gestor_migraciones_test"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conexion:
        conexion.execute(text(f"DROP DATABASE IF EXISTS {nombre}"))
        conexion.execute(text(f"CREATE DATABASE {nombre}"))
    url = base.set(database=nombre).render_as_string(hide_password=False)
    try:
        _sube_y_baja(_alembic(monkeypatch, url), url)
    finally:
        get_settings.cache_clear()
        db.get_engine.cache_clear()
        with admin.connect() as conexion:
            conexion.execute(text(f"DROP DATABASE IF EXISTS {nombre} WITH (FORCE)"))
        admin.dispose()
