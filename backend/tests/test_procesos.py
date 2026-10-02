"""Tests de app/core/procesos.py y del lifespan de main.py. SQLite temporal y YAML en tmp_path."""
import logging
import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import Folio, Proceso
from app.core.procesos import ErrorProcesos, leer_procesos, sincronizar_procesos
from app.main import app
from app.modulos.configuracion import servicio as configuracion

CONFIG_REPO = Path(__file__).resolve().parents[2] / "config"
# Las fichas de config/tipos del repo; leer_procesos las recibe como parametro (ADR-005)
TIPOS = {"comprobante_domicilio", "credencial_elector", "pasaporte"}

ONBOARDING = {
    "prefijo_folio": "ONB",
    "tipos_requeridos": ["credencial_elector", "comprobante_domicilio"],
    "tipos_opcionales": ["pasaporte"],
    "permitir_antecedentes": True,
    "caducidad_antecedentes_dias": 365,
    "webhook_url": "",
    "modelos": "default",
}


def escribir_config(config_dir: Path, procesos: dict) -> Path:
    """config/ de prueba: los tipos reales del repo y un procesos.yaml a medida."""
    if not (config_dir / "tipos").exists():
        shutil.copytree(CONFIG_REPO / "tipos", config_dir / "tipos")
    (config_dir / "procesos.yaml").write_text(yaml.safe_dump({"procesos": procesos}), encoding="utf-8")
    return config_dir


@pytest.fixture(autouse=True)
def fichas_aisladas(monkeypatch):
    """El lifespan llama a configuracion.cargar(CONFIG_DIR temporal): al acabar el test se restauran
    las fichas que hubiera cargadas, para no arrastrar estado global a otros tests."""
    monkeypatch.setattr(configuracion, "_tipos", None)


@pytest.fixture
def sesion(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_el_procesos_yaml_del_repo_es_valido():
    procesos = leer_procesos(CONFIG_REPO, TIPOS)
    assert [p.nombre for p in procesos] == ["onboarding"]
    assert procesos[0].webhook_url is None  # "" -> None


def test_varios_errores_se_informan_juntos(tmp_path):
    malo = {**ONBOARDING, "prefijo_folio": "onb", "tipos_opcionales": ["tipo_inventado"],
            "campo_desconocido": 1}
    with pytest.raises(ErrorProcesos) as e:
        leer_procesos(escribir_config(tmp_path, {"onboarding": malo}), TIPOS)
    texto = str(e.value)
    assert len(e.value.errores) == 3
    assert "onboarding.prefijo_folio" in texto
    assert "onboarding.campo_desconocido" in texto
    assert "onboarding.tipos_opcionales: el tipo 'tipo_inventado' no existe" in texto


def test_tipo_inexistente_y_tipo_repetido(tmp_path):
    malo = {**ONBOARDING, "tipos_opcionales": ["tipo_inventado", "credencial_elector"]}
    with pytest.raises(ErrorProcesos) as e:
        leer_procesos(escribir_config(tmp_path, {"onboarding": malo}), TIPOS)
    assert len(e.value.errores) == 2
    assert "'tipo_inventado' no existe" in str(e.value)
    assert "'credencial_elector' ya esta en tipos_requeridos" in str(e.value)


def test_los_tipos_existentes_son_los_que_se_pasan():
    with pytest.raises(ErrorProcesos, match="'pasaporte' no existe en tipos/"):
        leer_procesos(CONFIG_REPO, TIPOS - {"pasaporte"})


def test_prefijo_repetido_entre_procesos(tmp_path):
    with pytest.raises(ErrorProcesos, match="'ONB' ya lo usa onboarding"):
        leer_procesos(escribir_config(tmp_path, {"onboarding": ONBOARDING, "otro": ONBOARDING}), TIPOS)


def test_yaml_mal_formado(tmp_path):
    escribir_config(tmp_path, {})
    (tmp_path / "procesos.yaml").write_text("procesos: [sin cerrar", encoding="utf-8")
    with pytest.raises(ErrorProcesos, match="no se puede leer"):
        leer_procesos(tmp_path, TIPOS)


def test_sincronizar_dos_veces_no_duplica(sesion):
    procesos = leer_procesos(CONFIG_REPO, TIPOS)
    sincronizar_procesos(sesion, procesos)
    sincronizar_procesos(sesion, procesos)
    assert sesion.scalar(select(func.count()).select_from(Proceso)) == 1


def test_cambiar_caducidad_actualiza_la_fila(sesion, tmp_path):
    sincronizar_procesos(sesion, leer_procesos(escribir_config(tmp_path, {"onboarding": ONBOARDING}), TIPOS))
    cambiado = {**ONBOARDING, "caducidad_antecedentes_dias": 30}
    sincronizar_procesos(sesion, leer_procesos(escribir_config(tmp_path, {"onboarding": cambiado}), TIPOS))
    assert sesion.get(Proceso, "onboarding").caducidad_antecedentes_dias == 30


def test_proceso_quitado_del_yaml_no_se_borra(sesion, tmp_path, caplog):
    otro = {**ONBOARDING, "prefijo_folio": "OTR"}
    sincronizar_procesos(sesion, leer_procesos(
        escribir_config(tmp_path, {"onboarding": ONBOARDING, "otro": otro}), TIPOS))
    with caplog.at_level(logging.WARNING):
        sincronizar_procesos(sesion, leer_procesos(escribir_config(tmp_path, {"onboarding": ONBOARDING}), TIPOS))
    assert sesion.get(Proceso, "otro") is not None
    assert "'otro' esta en BD pero ya no" in caplog.text


def test_no_se_cambia_el_prefijo_si_hay_folios(sesion, tmp_path):
    sincronizar_procesos(sesion, leer_procesos(escribir_config(tmp_path, {"onboarding": ONBOARDING}), TIPOS))
    sesion.add(Folio(folio="ONB-2026-000001", proceso="onboarding", anio=2026, secuencia=1))
    sesion.commit()
    cambiado = {**ONBOARDING, "prefijo_folio": "NUE", "caducidad_antecedentes_dias": 30}
    with pytest.raises(ErrorProcesos, match="ya hay folios"):
        sincronizar_procesos(sesion, leer_procesos(escribir_config(tmp_path, {"onboarding": cambiado}), TIPOS))
    sesion.expire_all()
    fila = sesion.get(Proceso, "onboarding")
    assert (fila.prefijo_folio, fila.caducidad_antecedentes_dias) == ("ONB", 365)


def test_lifespan_carga_los_procesos(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'app.db'}"
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test",
        "DATABASE_URL": url,
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test",
        "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test",
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test",
        "CONFIG_DIR": str(escribir_config(tmp_path / "config", {"onboarding": ONBOARDING})),
    }.items():
        monkeypatch.setenv(nombre, valor)
    # Las fichas se cargan del CONFIG_DIR temporal, no del repo
    ficha = tmp_path / "config" / "tipos" / "pasaporte.yaml"
    ficha.write_text(ficha.read_text(encoding="utf-8").replace(
        "nombre_visible: Pasaporte", "nombre_visible: Pasaporte de test"), encoding="utf-8")
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    try:
        with TestClient(app) as cliente:
            assert cliente.get("/salud").status_code == 200
        with Session(db.get_engine()) as s:
            assert s.get(Proceso, "onboarding").prefijo_folio == "ONB"
        assert {t.nombre for t in configuracion.listar()} == TIPOS
        assert configuracion.obtener("pasaporte").nombre_visible == "Pasaporte de test"
    finally:
        db.get_engine().dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()


def test_lifespan_no_arranca_con_una_ficha_invalida(monkeypatch, tmp_path):
    config_dir = escribir_config(tmp_path / "config", {"onboarding": ONBOARDING})
    with (config_dir / "tipos" / "pasaporte.yaml").open("a", encoding="utf-8") as f:
        f.write("clave_inventada: 1\n")
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'app.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test",
        "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test",
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test",
        "CONFIG_DIR": str(config_dir),
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    try:
        with pytest.raises(configuracion.ErrorConfiguracion, match="pasaporte.yaml: clave_inventada"):
            with TestClient(app):
                pass
        with Session(db.get_engine()) as s:
            assert s.get(Proceso, "onboarding") is None  # no llega a sincronizar los procesos
    finally:
        db.get_engine().dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()


def test_lifespan_sin_tablas_pide_alembic(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": "clave-ficticia-de-test",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'vacia.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test",
        "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test",
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test",
        "CONFIG_DIR": str(CONFIG_REPO),
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            with TestClient(app):
                pass
    finally:
        db.get_engine().dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()
