"""Tests de app/core/config.py. Nunca leen el .env real: _env_file=None y entorno por monkeypatch."""
import pytest
from pydantic import ValidationError

from app.core.config import RAIZ_REPO, Settings, get_settings

OBLIGATORIAS = {
    "SECRET_KEY": "clave-ficticia-de-test",
    "DATABASE_URL": "postgresql+psycopg://usuario_test:contrasena_test@localhost:5432/test",
    "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test",
    "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test",
    "S3_BUCKET": "bucket-de-test",
    "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test",
}


@pytest.fixture
def entorno(monkeypatch):
    for nombre in (*OBLIGATORIAS, "APP_ENV", "CONFIG_DIR", "JWT_ALGORITMO", "JWT_EXPIRA_MINUTOS",
                   "AWS_REGION", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    for nombre, valor in OBLIGATORIAS.items():
        monkeypatch.setenv(nombre, valor)
    return monkeypatch


def test_falta_una_obligatoria(entorno):
    entorno.delenv("SECRET_KEY")
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None)


def test_valores_por_defecto(entorno):
    s = Settings(_env_file=None)
    assert s.app_env == "dev"
    assert s.jwt_algoritmo == "HS256"
    assert s.jwt_expira_minutos == 480
    assert s.aws_region == "us-east-1"
    assert s.tamano_maximo_archivo_mb == 20
    assert s.config_dir == RAIZ_REPO / "config"


def test_los_secretos_no_aparecen_en_repr(entorno):
    texto = repr(Settings(_env_file=None))
    assert "clave-ficticia-de-test" not in texto
    assert "contrasena_test" not in texto


def test_config_dir_vacio_usa_config_de_la_raiz(entorno):
    entorno.setenv("CONFIG_DIR", "")
    assert Settings(_env_file=None).config_dir == RAIZ_REPO / "config"


def test_config_dir_del_entorno(entorno, tmp_path):
    entorno.setenv("CONFIG_DIR", str(tmp_path))
    assert Settings(_env_file=None).config_dir == tmp_path


def test_prod_rechaza_valores_de_ejemplo(entorno):
    entorno.setenv("APP_ENV", "prod")
    entorno.setenv("SECRET_KEY", "CAMBIA_ESTO_EN_PRODUCCION")
    with pytest.raises(ValidationError, match="valor de ejemplo"):
        Settings(_env_file=None)


def test_dev_acepta_valores_de_ejemplo(entorno):
    entorno.setenv("SECRET_KEY", "CAMBIA_ESTO_EN_PRODUCCION")
    assert Settings(_env_file=None).app_env == "dev"


def test_get_settings_usa_cache(entorno):
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
