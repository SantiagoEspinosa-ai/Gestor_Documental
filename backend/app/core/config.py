"""Settings de la aplicacion, leidos del entorno o de `.env` (ver `.env.example`).

Solo las variables que usa la plataforma (core, api, ingesta, expediente). Las de Ollama, OpenRouter
y Tesseract las leen los adaptadores de PERSONA_2 y aqui se ignoran.
"""
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> raiz del repo
RAIZ_REPO = Path(__file__).resolve().parents[3]

# Valores de ejemplo de .env.example que no pueden llegar a produccion
_MARCADORES_EJEMPLO = ("CAMBIA_ESTO", "TU_CLAVE_AQUI")
# Secretos de firma (JWT y HMAC de los webhooks): un valor corto o el de .env.example se adivina y permite
# firmar tokens o webhooks falsos. Se exige en todos los entornos, tambien en dev
LONGITUD_MINIMA_SECRETO = 32
COMO_GENERAR_SECRETO = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


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
    url_prefirmada_segundos: int = Field(300, gt=0)  # caducidad de las URL del visor

    # Webhooks
    webhook_secret_hmac: SecretStr

    # Ingesta (ADR-006 1.4: ARCHIVO_DEMASIADO_GRANDE)
    tamano_maximo_archivo_mb: int = 20

    # Llamadas simultaneas al motor de IA (ingesta/procesamiento.py); 1 con Ollama sin GPU
    max_procesamientos_simultaneos: int = Field(1, gt=0)
    # Al arrancar, relanzar los analisis que un reinicio dejo en pendiente o procesando (ingesta.servicio)
    reanudar_analisis_al_arrancar: bool = True
    # Veces que se relanza un mismo analisis interrumpido; al superarlo, el documento pasa a error (SYS-001)
    max_reintentos_reanudar: int = Field(3, ge=1)

    # Motor de analisis (H10): real = orquestador de PERSONA_2 (Ollama); stub = sin Ollama, solo pruebas (e2e de humo).
    # Otro valor no arranca (Literal)
    motor_analisis: Literal["real", "stub"] = "real"

    # Zona horaria del negocio: decide el anio del folio (no UTC)
    zona_horaria: str = "America/Mexico_City"

    # Origenes del navegador que pueden llamar a la API (CORS). En .env, separados por comas
    cors_origenes: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origenes", mode="before")
    @classmethod
    def _cors_origenes_separados_por_comas(cls, valor):
        if isinstance(valor, str):
            valor = [origen.strip() for origen in valor.split(",")]
        origenes = [origen for origen in valor if origen]
        if "*" in origenes:
            raise ValueError("CORS_ORIGENES no admite el comodin '*': indica los origenes uno a uno")
        return origenes

    @field_validator("zona_horaria")
    @classmethod
    def _zona_horaria_valida(cls, valor: str) -> str:
        try:
            ZoneInfo(valor)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"zona horaria desconocida: {valor}") from None
        return valor

    @field_validator("config_dir", mode="before")
    @classmethod
    def _config_dir_por_defecto(cls, valor):
        # CONFIG_DIR vacio en .env equivale a no definirla
        return valor or RAIZ_REPO / "config"

    @model_validator(mode="after")
    def _secretos_de_firma_validos(self):
        """En cualquier entorno: secret_key y webhook_secret_hmac sin el valor de ejemplo y con al menos
        LONGITUD_MINIMA_SECRETO caracteres. webhook_secret_hmac puede ir vacio (= no se envian webhooks)."""
        for campo, vacio_permitido in (("secret_key", False), ("webhook_secret_hmac", True)):
            valor = getattr(self, campo).get_secret_value()
            if not valor and vacio_permitido:
                continue
            if valor.startswith(_MARCADORES_EJEMPLO):
                raise ValueError(f"{campo} tiene el valor de ejemplo de .env.example; genera uno propio con: "
                                 f"{COMO_GENERAR_SECRETO}")
            if len(valor) < LONGITUD_MINIMA_SECRETO:
                raise ValueError(f"{campo} debe tener al menos {LONGITUD_MINIMA_SECRETO} caracteres; genera uno con: "
                                 f"{COMO_GENERAR_SECRETO}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
