"""Puerto `Almacenamiento` y adaptador `AlmacenamientoS3` para los originales (ADR-005).

Amazon S3 real, sin endpoint personalizado (ADR-001). El original nunca se sobrescribe
(diapositiva 10): la subida es condicional con `IfNoneMatch="*"`. Cifrado en reposo SSE-S3.
boto3 solo aparece en este fichero.
"""
import logging
import re
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

log = logging.getLogger(__name__)

_EXTENSION = re.compile(r"^[a-z0-9]{1,5}$")
_CODIGOS_NO_ENCONTRADO = {"NoSuchKey", "404", "NotFound"}
_CODIGOS_YA_EXISTE = {"PreconditionFailed", "ConditionalRequestConflict"}


class ErrorAlmacenamiento(Exception):
    """Mensajes sin claves de acceso ni URL firmadas."""


class ObjetoNoEncontrado(ErrorAlmacenamiento):
    pass


class Almacenamiento(Protocol):
    def subir(self, datos: bytes, clave: str, tipo_contenido: str) -> None: ...

    def descargar(self, clave: str) -> bytes: ...

    def url_prefirmada(self, clave: str) -> str: ...

    def existe(self, clave: str) -> bool: ...


def clave_original(proceso: str, anio: int, secuencia: int, identificador: str, extension: str) -> str:
    """Clave S3 del original: `{proceso}/{anio}/{secuencia:06d}/{identificador}.{ext}`."""
    if not proceso or "/" in proceso or ".." in proceso:
        raise ValueError(f"Proceso no valido para una clave S3: {proceso!r}")
    ext = extension.lower().lstrip(".")
    if not _EXTENSION.match(ext):
        raise ValueError(f"Extension no valida: {extension!r}")
    return f"{proceso}/{anio}/{secuencia:06d}/{identificador}.{ext}"


def _codigo(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Code", "")


class AlmacenamientoS3:
    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str, segundos_url: int):
        self.bucket = bucket
        self.segundos_url = segundos_url
        # s3v4 + virtual: URL firmadas con el endpoint regional (bucket.s3.<region>.amazonaws.com).
        # Con el endpoint global, un bucket fuera de us-east-1 responde 307 y la firma deja de valer.
        self._s3 = boto3.client("s3", region_name=region, aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key,
                                config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))

    def _error(self, operacion: str, clave: str, e: Exception) -> ErrorAlmacenamiento:
        # Solo operacion, clave y codigo de error: nunca credenciales ni URL firmadas
        detalle = _codigo(e) if isinstance(e, ClientError) else type(e).__name__
        log.warning("Error de S3 en %s de '%s': %s", operacion, clave, detalle)
        return ErrorAlmacenamiento(f"No se pudo completar '{operacion}' en el almacenamiento")

    def subir(self, datos: bytes, clave: str, tipo_contenido: str) -> None:
        try:
            self._s3.put_object(Bucket=self.bucket, Key=clave, Body=datos, ContentType=tipo_contenido,
                                ServerSideEncryption="AES256", IfNoneMatch="*")
        except ClientError as e:
            if _codigo(e) in _CODIGOS_YA_EXISTE:
                raise ErrorAlmacenamiento(f"El objeto '{clave}' ya existe; los originales no se sobrescriben") from None
            raise self._error("subir", clave, e) from None
        except BotoCoreError as e:
            raise self._error("subir", clave, e) from None

    def descargar(self, clave: str) -> bytes:
        try:
            return self._s3.get_object(Bucket=self.bucket, Key=clave)["Body"].read()
        except ClientError as e:
            if _codigo(e) in _CODIGOS_NO_ENCONTRADO:
                raise ObjetoNoEncontrado(f"No existe el objeto '{clave}'") from None
            raise self._error("descargar", clave, e) from None
        except BotoCoreError as e:
            raise self._error("descargar", clave, e) from None

    def url_prefirmada(self, clave: str) -> str:
        try:
            return self._s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": clave},
                                                   ExpiresIn=self.segundos_url)
        except (ClientError, BotoCoreError) as e:
            raise self._error("url_prefirmada", clave, e) from None

    def existe(self, clave: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=clave)
            return True
        except ClientError as e:
            if _codigo(e) in _CODIGOS_NO_ENCONTRADO:
                return False
            raise self._error("existe", clave, e) from None
        except BotoCoreError as e:
            raise self._error("existe", clave, e) from None


@lru_cache
def get_almacenamiento() -> Almacenamiento:
    """Dependencia de FastAPI: adaptador S3 configurado desde los settings."""
    s = get_settings()
    return AlmacenamientoS3(bucket=s.s3_bucket, region=s.aws_region,
                            access_key=s.aws_access_key_id.get_secret_value(),
                            secret_key=s.aws_secret_access_key.get_secret_value(),
                            segundos_url=s.url_prefirmada_segundos)
