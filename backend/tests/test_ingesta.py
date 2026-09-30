"""Tests de modulos/ingesta (servicio y stub de procesamiento). SQLite temporal y moto; datos ficticios."""
import re
import uuid

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3, ErrorAlmacenamiento
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Auditoria, Documento, Proceso, Resultado
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento_stub
from app.modulos.ingesta.procesamiento_stub import procesar_documento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import ResultadoDocumento

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
PDF = b"%PDF-1.4 documento ficticio"
JPG = b"\xff\xd8\xff\xe0 imagen ficticia"
PNG = b"\x89PNG\r\n\x1a\n imagen ficticia"


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia",
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                      tipos_opcionales=[], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def s3():
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        yield AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                               secret_key=SECRETO, segundos_url=60)


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "integrador_ficticio")


def _subir(sesion, s3, folio, nombre="credencial_ficticia.pdf", datos=PDF, tipo="credencial_elector"):
    return ingestar(sesion, s3, folio.folio, nombre, datos, tipo, "integrador_ficticio")


def _codigo(e: pytest.ExceptionInfo) -> tuple[int, str]:
    return e.value.http, e.value.codigo


# --- ingestar ---

def test_subida_valida(sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    fila = sesion.get(Documento, doc.id)
    assert fila.estado_analisis == "pendiente"
    assert fila.nombre_archivo == "credencial_ficticia.pdf"
    assert re.fullmatch(rf"onboarding/{folio.anio}/{folio.secuencia:06d}/{doc.id}\.pdf", fila.ruta_s3)
    assert s3.descargar(fila.ruta_s3) == PDF

    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "documento_subido"))
    assert registro.documento_id == doc.id
    assert registro.detalle == {"hash_sha256": fila.hash_sha256, "tamano_bytes": len(PDF), "duplicado": False}
    assert "credencial_ficticia" not in str(registro.detalle)


def test_folio_inexistente(sesion, s3):
    with pytest.raises(ErrorApi) as e:
        ingestar(sesion, s3, "ONB-2026-999999", "a.pdf", PDF, None, "x")
    assert _codigo(e) == (404, "FOLIO_NO_ENCONTRADO")


def test_folio_cerrado(sesion, s3, folio):
    folio.estado_general = "aprobado"
    sesion.commit()
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio)
    assert _codigo(e) == (409, "FOLIO_CERRADO")


def test_archivo_demasiado_grande(sesion, s3, folio):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, datos=b"x" * (20 * 1024 * 1024 + 1))
    assert _codigo(e) == (413, "ARCHIVO_DEMASIADO_GRANDE")


def test_archivo_vacio(sesion, s3, folio):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, datos=b"")
    assert _codigo(e) == (422, "PETICION_INVALIDA")


@pytest.mark.parametrize("nombre", ["documento.exe", "documento.docx", "sin_extension"])
def test_formato_no_permitido(sesion, s3, folio, nombre):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre)
    assert _codigo(e) == (415, "FORMATO_NO_PERMITIDO")


def test_tipo_declarado_desconocido(sesion, s3, folio):
    with pytest.raises(ErrorApi, match="tipo_declarado no existe") as e:
        _subir(sesion, s3, folio, tipo="tipo_inventado")
    assert _codigo(e) == (422, "PETICION_INVALIDA")


@pytest.mark.parametrize("nombre,datos,tipo_contenido", [
    ("a.pdf", PDF, "application/pdf"),
    ("b.JPG", JPG, "image/jpeg"),
    ("c.png", PNG, "image/png"),
])
def test_sin_tipo_declarado_acepta_formatos_de_todos_los_tipos(sesion, s3, folio, nombre, datos,
                                                               tipo_contenido):
    doc = _subir(sesion, s3, folio, nombre=nombre, datos=datos, tipo=None)
    assert doc.ruta_s3.endswith("." + nombre.rsplit(".", 1)[1].lower())
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=doc.ruta_s3)
    assert cabecera["ContentType"] == tipo_contenido


@pytest.mark.parametrize("nombre,datos", [("a.pdf", PNG), ("b.png", PDF), ("c.jpg", b"texto plano")])
def test_contenido_que_no_corresponde_a_la_extension(sesion, s3, folio, nombre, datos):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre, datos=datos, tipo=None)
    assert _codigo(e) == (415, "FORMATO_NO_PERMITIDO")


def test_nombre_sin_ruta_y_recortado(sesion, s3, folio):
    doc = _subir(sesion, s3, folio, nombre="C:\\carpeta\\sub/" + "n" * 300 + ".pdf")
    assert len(doc.nombre_archivo) == 255
    assert doc.nombre_archivo.endswith(".pdf")
    assert "/" not in doc.nombre_archivo and "\\" not in doc.nombre_archivo


@pytest.mark.parametrize("nombre", ["", "   ", "/"])
def test_nombre_vacio(sesion, s3, folio, nombre):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre)
    assert _codigo(e) == (422, "PETICION_INVALIDA")


def test_duplicado_no_bloquea_y_genera_dup_001(sesion, s3, folio):
    primero = _subir(sesion, s3, folio)
    segundo = _subir(sesion, s3, folio)
    assert primero.id != segundo.id
    assert primero.ruta_s3 != segundo.ruta_s3
    assert s3.descargar(primero.ruta_s3) == s3.descargar(segundo.ruta_s3) == PDF

    # Solo las de documento: el folio nace ademas con sus EXP-001 de expediente
    alertas = sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id.is_not(None))).all()
    assert len(alertas) == 1
    assert sesion.scalar(select(func.count()).select_from(AlertaBD).where(AlertaBD.codigo == "DUP-001")) == 1
    assert (alertas[0].codigo, alertas[0].severidad, alertas[0].documento_id) == ("DUP-001", "critica", segundo.id)
    assert str(primero.id) in alertas[0].mensaje
    detalles = [a.detalle["duplicado"] for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))
                if a.accion == "documento_subido"]
    assert detalles == [False, True]


def test_fallo_al_subir_no_deja_rastro(sesion, folio):
    class AlmacenamientoRoto:
        def subir(self, datos, clave, tipo_contenido):
            raise ErrorAlmacenamiento("No se pudo completar 'subir' en el almacenamiento")

    with pytest.raises(ErrorApi) as e:
        _subir(sesion, AlmacenamientoRoto(), folio)
    assert _codigo(e) == (500, "ERROR_INTERNO")
    assert sesion.scalar(select(func.count()).select_from(Documento)) == 0
    assert sesion.scalar(select(func.count()).select_from(Auditoria)
                         .where(Auditoria.accion == "documento_subido")) == 0


# --- procesar_documento (stub) ---

def test_procesar_documento_con_su_propia_sesion(sesion, s3, folio):
    _subir(sesion, s3, folio)
    doc = _subir(sesion, s3, folio)  # duplicado: lleva DUP-001
    procesar_documento(doc.id)  # sin pasarle sesion

    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "completado"
    fila = sesion.scalar(select(Resultado).where(Resultado.documento_id == doc.id))
    assert fila.version == 1
    resultado = ResultadoDocumento.model_validate(fila.json)
    assert resultado.estado_analisis.value == "completado"
    assert resultado.tipo_documental_detectado == "credencial_elector"
    assert resultado.referencia_archivo_original.hash == doc.hash_sha256
    assert [a.codigo for a in resultado.alertas_encontradas] == ["DUP-001"]
    assert uuid.UUID(resultado.alertas_encontradas[0].id)
    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "documento_procesado"))
    assert (registro.documento_id, registro.modelo, registro.version_prompt) == (doc.id, "stub", "stub@v0")


def test_procesar_dos_veces_crea_version_2(sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    procesar_documento(doc.id)
    procesar_documento(doc.id)
    versiones = sesion.scalars(select(Resultado.version).where(Resultado.documento_id == doc.id)
                               .order_by(Resultado.version)).all()
    assert versiones == [1, 2]


def test_procesar_con_fallo_deja_estado_error(sesion, s3, folio, monkeypatch):
    doc = _subir(sesion, s3, folio)

    def rompe(*args):
        raise RuntimeError("fallo forzado")

    monkeypatch.setattr(procesamiento_stub, "_resultado_ficticio", rompe)
    procesar_documento(doc.id)  # no relanza
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "error"
    assert sesion.scalar(select(func.count()).select_from(Resultado)) == 0
