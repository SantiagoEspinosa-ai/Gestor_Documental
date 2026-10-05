"""Tests de app/core/almacenamiento.py. Solo moto (S3 simulado): nunca contra AWS real."""
import logging

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.core.almacenamiento import (AlmacenamientoS3, ErrorAlmacenamiento, ObjetoNoEncontrado,
                                     clave_derivado, clave_original)

BUCKET = "bucket-de-test"
REGION = "us-east-1"
SECRETO = "secreto-ficticio-de-test"
CLAVE = "onboarding/2026/000001/00000000-0000-4000-8000-000000000001.pdf"


@pytest.fixture
def s3(monkeypatch):
    # Credenciales ficticias tambien en el entorno, por si boto3 las buscara ahi
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "clave-ficticia")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SECRETO)
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        yield AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                               secret_key=SECRETO, segundos_url=120)


def test_subir_y_descargar(s3):
    s3.subir(b"%PDF-ficticio", CLAVE, "application/pdf")
    assert s3.descargar(CLAVE) == b"%PDF-ficticio"
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=CLAVE)
    assert cabecera["ContentType"] == "application/pdf"
    assert cabecera["ServerSideEncryption"] == "AES256"


def test_no_se_sobrescribe_un_original(s3):
    s3.subir(b"original", CLAVE, "application/pdf")
    with pytest.raises(ErrorAlmacenamiento, match="ya existe"):
        s3.subir(b"otro contenido", CLAVE, "application/pdf")
    assert s3.descargar(CLAVE) == b"original"


def test_subir_derivado_sobrescribe_con_sse(s3):
    clave = "onboarding/2026/000001/resumen.md"
    s3.subir_derivado(b"# version 1", clave, "text/markdown; charset=utf-8")
    s3.subir_derivado(b"# version 2", clave, "text/markdown; charset=utf-8")
    assert s3.descargar(clave) == b"# version 2"
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=clave)
    assert cabecera["ServerSideEncryption"] == "AES256"
    assert cabecera["ContentType"] == "text/markdown; charset=utf-8"


def test_subir_derivado_no_afloja_los_originales(s3):
    s3.subir(b"original", CLAVE, "application/pdf")
    s3.subir_derivado(b"resumen", "onboarding/2026/000001/resumen.md", "text/markdown")
    with pytest.raises(ErrorAlmacenamiento, match="ya existe"):
        s3.subir(b"otro contenido", CLAVE, "application/pdf")
    assert s3.descargar(CLAVE) == b"original"


def test_clave_derivado():
    assert clave_derivado("onboarding", 2026, 7, "resumen.md") == "onboarding/2026/000007/resumen.md"
    for proceso, nombre in (("on/boarding", "resumen.md"), ("onboarding", "../resumen.md"), ("onboarding", "")):
        with pytest.raises(ValueError):
            clave_derivado(proceso, 2026, 7, nombre)


def test_descargar_inexistente(s3):
    with pytest.raises(ObjetoNoEncontrado):
        s3.descargar("no/existe.pdf")


def test_url_prefirmada(s3):
    s3.subir(b"x", CLAVE, "application/pdf")
    url = s3.url_prefirmada(CLAVE)
    assert BUCKET in url
    assert CLAVE in url
    assert "X-Amz-Signature=" in url or "Signature=" in url
    assert "X-Amz-Expires=120" in url or "Expires=" in url


def test_url_prefirmada_usa_el_endpoint_regional():
    # Con el endpoint global, un bucket fuera de us-east-1 responde 307 y la URL no sirve
    s3 = AlmacenamientoS3(bucket=BUCKET, region="us-east-2", access_key="clave-ficticia",
                          secret_key=SECRETO, segundos_url=60)
    url = s3.url_prefirmada(CLAVE)  # firmar no llama a AWS
    assert url.startswith(f"https://{BUCKET}.s3.us-east-2.amazonaws.com/")
    assert "X-Amz-Signature=" in url


def test_existe(s3):
    assert not s3.existe(CLAVE)
    s3.subir(b"x", CLAVE, "application/pdf")
    assert s3.existe(CLAVE)


def test_clave_original():
    assert clave_original("onboarding", 2026, 7, "abc", ".PDF") == "onboarding/2026/000007/abc.pdf"
    assert clave_original("onboarding", 2026, 123456, "abc", "jpeg") == "onboarding/2026/123456/abc.jpeg"


@pytest.mark.parametrize("extension", ["", "tar.gz", "exe/", "pdf!", "abcdef", "../x"])
def test_clave_original_rechaza_extensiones(extension):
    with pytest.raises(ValueError, match="Extension"):
        clave_original("onboarding", 2026, 1, "abc", extension)


@pytest.mark.parametrize("proceso", ["", "on/boarding", "..", "on..boarding"])
def test_clave_original_rechaza_procesos(proceso):
    with pytest.raises(ValueError, match="Proceso"):
        clave_original(proceso, 2026, 1, "abc", "pdf")


def test_client_error_generico_sin_secretos(s3, monkeypatch, caplog):
    def denegado(**kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": f"clave {SECRETO}"}}, "GetObject")

    monkeypatch.setattr(s3._s3, "get_object", denegado)
    with caplog.at_level(logging.WARNING), pytest.raises(ErrorAlmacenamiento) as e:
        s3.descargar(CLAVE)
    assert not isinstance(e.value, ObjetoNoEncontrado)
    assert SECRETO not in str(e.value)
    assert "clave-ficticia" not in str(e.value)
    assert "AccessDenied" in caplog.text
    assert SECRETO not in caplog.text
