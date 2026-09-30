"""Settings de la aplicacion, leidos del entorno o de `.env` (ver `.env.example`).

Solo las variables que usa la plataforma (core, api, ingesta, expediente). Las de Ollama, OpenRouter
y Tesseract las leen los adaptadores de PERSONA_2 y aqui se ignoran.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> raiz del repo
RAIZ_REPO = Path(__file__).resolve().parents[3]

# Valores de ejemplo de .env.example que no pueden llegar a produccion
_MARCADORES_EJEMPLO = ("CAMBIA_ESTO", "TU_CLAVE_AQUI")


class Settings(BaseSettings):
    # .env de la raiz del repo, sea cual sea el directorio de trabajo
    model_config = SettingsConfigDict(env_file=RAIZ_REPO / ".env", extra="ignore", case_sensitive=False)

    app_env: Literal["dev", "prod"] = "dev"

    # Auth
    secret_key: SecretStr
    jwt_algoritmo: str = "HS256"
    jwt_expira_minutos: int = 480

    # BD: SecretStr porque la cadena de conexion lleva la contrasena
    database_url: SecretStr

    # Ficheros YAML de config/ (tipos, procesos, modelos). En Docker, /config
    config_dir: Path = Field(default_factory=lambda: RAIZ_REPO / "config")

    # Amazon S3
    aws_access_key_id: SecretStr
    aws_secret_access_key: SecretStr
    aws_region: str = "us-east-1"
    s3_bucket: str

    # Webhooks
    webhook_secret_hmac: SecretStr

    # Ingesta (ADR-006 1.4: ARCHIVO_DEMASIADO_GRANDE)
    tamano_maximo_archivo_mb: int = 20

    @field_validator("config_dir", mode="before")
    @classmethod
    def _config_dir_por_defecto(cls, valor):
        # CONFIG_DIR vacio en .env equivale a no definirla
        return valor or RAIZ_REPO / "config"

    @model_validator(mode="after")
    def _sin_valores_de_ejemplo_en_prod(self):
        if self.app_env == "prod":
            for campo in ("secret_key", "webhook_secret_hmac"):
                if getattr(self, campo).get_secret_value().startswith(_MARCADORES_EJEMPLO):
                    raise ValueError(f"{campo} tiene el valor de ejemplo de .env.example")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
