"""Tests de app/core/config.py. Nunca leen el .env real: _env_file=None y entorno por monkeypatch."""
import pytest
from pydantic import ValidationError

from app.core.config import RAIZ_REPO, Settings, get_settings

OBLIGATORIAS = {
    "SECRET_KEY": "clave-ficticia-de-test-de-32-caracteres",
    "DATABASE_URL": "postgresql+psycopg://usuario_test:contrasena_test@localhost:5432/test",
    "AWS_ACCESS_KEY_ID": "clave-ficticia-de-test-de-32-caracteres",
    "AWS_SECRET_ACCESS_KEY": "clave-ficticia-de-test-de-32-caracteres",
    "S3_BUCKET": "bucket-de-test",
    "WEBHOOK_SECRET_HMAC": "clave-ficticia-de-test-de-32-caracteres",
}


@pytest.fixture
def entorno(monkeypatch):
    for nombre in (*OBLIGATORIAS, "APP_ENV", "CONFIG_DIR", "JWT_ALGORITMO", "JWT_EXPIRA_MINUTOS",
                   "AWS_REGION", "TAMANO_MAXIMO_ARCHIVO_MB", "CORS_ORIGENES"):
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
    assert "clave-ficticia-de-test-de-32-caracteres" not in texto
    assert "contrasena_test" not in texto


def test_config_dir_vacio_usa_config_de_la_raiz(entorno):
    entorno.setenv("CONFIG_DIR", "")
    assert Settings(_env_file=None).config_dir == RAIZ_REPO / "config"


def test_config_dir_del_entorno(entorno, tmp_path):
    entorno.setenv("CONFIG_DIR", str(tmp_path))
    assert Settings(_env_file=None).config_dir == tmp_path


@pytest.mark.parametrize("app_env", ["dev", "prod"])
@pytest.mark.parametrize("campo", ["SECRET_KEY", "WEBHOOK_SECRET_HMAC"])
@pytest.mark.parametrize("ejemplo", ["CAMBIA_ESTO_EN_PRODUCCION", "CAMBIA_ESTO", "TU_CLAVE_AQUI_" + "x" * 40])
def test_rechaza_el_valor_de_ejemplo_en_cualquier_entorno(entorno, app_env, campo, ejemplo):
    entorno.setenv("APP_ENV", app_env)
    entorno.setenv(campo, ejemplo)
    with pytest.raises(ValidationError, match="valor de ejemplo") as error:
        Settings(_env_file=None)
    assert "secrets.token_urlsafe(48)" in str(error.value)  # dice como generar uno


@pytest.mark.parametrize("campo", ["SECRET_KEY", "WEBHOOK_SECRET_HMAC"])
def test_rechaza_secretos_cortos(entorno, campo):
    entorno.setenv(campo, "a" * 31)
    with pytest.raises(ValidationError, match="al menos 32 caracteres"):
        Settings(_env_file=None)


def test_acepta_secretos_validos_de_32_o_mas(entorno):
    entorno.setenv("SECRET_KEY", "a" * 32)
    entorno.setenv("WEBHOOK_SECRET_HMAC", "b" * 64)
    entorno.setenv("APP_ENV", "prod")
    s = Settings(_env_file=None)
    assert len(s.secret_key.get_secret_value()) == 32


def test_webhook_vacio_permitido_y_secret_key_vacio_no(entorno):
    entorno.setenv("WEBHOOK_SECRET_HMAC", "")
    assert Settings(_env_file=None).webhook_secret_hmac.get_secret_value() == ""
    entorno.setenv("SECRET_KEY", "")
    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None)


def test_env_file_es_el_de_la_raiz_del_repo():
    assert Settings.model_config["env_file"] == RAIZ_REPO / ".env"


def test_get_settings_usa_cache(entorno):
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
