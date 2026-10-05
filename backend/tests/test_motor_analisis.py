"""Tests de H10: MOTOR_ANALISIS elige el motor de ingesta/procesamiento.py (real = orquestador de PERSONA_2,
stub = motor_stub). Sin Ollama: el orquestador se sustituye por uno falso. SQLite temporal + moto. Datos ficticios."""
import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3
from app.core.config import Settings, get_settings
from app.core.db import Base
from app.core.modelos import Auditoria, Documento, Proceso
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.orquestador import servicio as orquestador

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
# Forma real de datos_auditoria del orquestador (orquestador/procesamiento.py), con valores ficticios
DATOS_REALES = {
    "modelo": "gemma4:e2b", "proveedor": "ollama", "version_prompt": "extraccion_credencial_elector@v3",
    "version_prompt_clasificacion": "clasificacion@v2", "respaldo_usado": False,
    "confianzas_modelo": {"nombre_completo": 0.95}, "tiempos": {"segundos_modelo": 37.5},
    "tokens": {"entrada": 1200, "salida": 150},
    "llamadas": [{"proveedor": "ollama", "modelo": "gemma4:e2b", "entrada": "texto", "motivo": None, "segundos": 37.5,
                  "tokens_entrada": 1200, "tokens_salida": 150, "peticiones": 1, "reintentos": 0, "lotes": 1}],
    "modalidad": "pdf_digital", "paginas": 1,
}


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": SECRETO, "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _motor(monkeypatch, valor: str):
    monkeypatch.setenv("MOTOR_ANALISIS", valor)
    get_settings.cache_clear()


_STUB_ORIGINAL = motor_stub.procesar_documento  # antes de cualquier parche: el falso lo usa para el resultado


def _registrar(monkeypatch, modulo, nombre, llamadas, datos):
    def falso(contenido, **kwargs):
        llamadas.append(nombre)
        resultado, _ = _STUB_ORIGINAL(contenido, **kwargs)
        return resultado, datos
    monkeypatch.setattr(modulo, "procesar_documento", falso)


def test_por_defecto_el_motor_real(entorno):
    entorno.delenv("MOTOR_ANALISIS", raising=False)
    assert Settings(_env_file=None).motor_analisis == "real"


def test_un_valor_invalido_no_arranca(entorno):
    _motor(entorno, "ollama")
    with pytest.raises(ValidationError, match="motor_analisis"):
        with TestClient(app):
            pass


@pytest.mark.parametrize("valor,esperado", [("real", "orquestador"), ("stub", "stub")])
def test_analizar_usa_el_motor_configurado(entorno, valor, esperado):
    llamadas = []
    _registrar(entorno, orquestador, "orquestador", llamadas, {"modelo": "x"})
    _registrar(entorno, motor_stub, "stub", llamadas, {"modelo": "x"})
    _motor(entorno, valor)
    procesamiento.analizar(b"%PDF-1.4", identificador="00000000-0000-4000-8000-000000000001",
                           nombre_archivo="ficticio.pdf", tipo_declarado="pasaporte", folio="ONB-2026-000001",
                           referencia=motor_stub.ReferenciaArchivoOriginal(nombre_archivo="ficticio.pdf", ruta="x",
                                                                           hash="0" * 64))
    assert llamadas == [esperado]


@pytest.fixture
def sesion(entorno):
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                      tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=30))
        s.commit()
        yield s
    db.get_engine().dispose()
    db.get_engine.cache_clear()


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        almacenamiento = AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                                          secret_key=SECRETO, segundos_url=60)
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: almacenamiento)
        yield almacenamiento


def test_flujo_con_el_motor_real_guarda_su_auditoria(sesion, s3, entorno):
    llamadas = []
    _registrar(entorno, orquestador, "orquestador", llamadas, DATOS_REALES)
    _motor(entorno, "real")
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    doc = ingestar(sesion, s3, folio, "credencial.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(doc.id)

    assert llamadas == ["orquestador"]
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "completado"
    entrada = sesion.scalars(select(Auditoria).where(Auditoria.accion == "documento_procesado")).one()
    assert (entrada.modelo, entrada.version_prompt) == ("gemma4:e2b", "extraccion_credencial_elector@v3")
    # El resto de datos_auditoria va a `detalle` tal cual (sin modelo ni version_prompt, que van en columnas)
    assert entrada.detalle == {k: v for k, v in DATOS_REALES.items() if k not in ("modelo", "version_prompt")}


def test_una_excepcion_del_motor_real_deja_el_documento_en_error(sesion, s3, entorno):
    def caido(contenido, **kwargs):
        raise RuntimeError("Ollama no responde (ficticio)")
    entorno.setattr(orquestador, "procesar_documento", caido)
    _motor(entorno, "real")
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    doc = ingestar(sesion, s3, folio, "credencial.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(doc.id)
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "error"
