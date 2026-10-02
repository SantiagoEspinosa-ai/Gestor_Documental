"""Tests del recalculo de EXP-001 (expediente.recalcular_exp001) al procesar documentos.

SQLite temporal + moto; motor stub (detectado = confirmado o declarado) o falso. Datos ficticios.
"""
import importlib.util
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import AlertaBD, Documento, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
PDF = b"%PDF-1.4 documento ficticio"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


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
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB",
                      tipos_requeridos=["credencial_elector", "comprobante_domicilio"],
                      tipos_opcionales=["pasaporte"], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        s.add(Proceso(nombre="sin_requeridos", prefijo_folio="SRQ", tipos_requeridos=[],
                      tipos_opcionales=["pasaporte"], permitir_antecedentes=False, caducidad_antecedentes_dias=30))
        script.crear_usuario(s, "revisor_ficticio", "revisor", "contrasena-ficticia")
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        almacenamiento = AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                                          secret_key=SECRETO, segundos_url=60)
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: almacenamiento)
        yield almacenamiento


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "x").folio


def _subir(sesion, s3, folio, tipo="credencial_elector", datos=PDF) -> Documento:
    return ingestar(sesion, s3, folio, "documento_ficticio.pdf", datos, tipo, "x")


def _exp001(sesion, folio) -> list[str]:
    sesion.expire_all()
    return sorted(sesion.scalars(select(AlertaBD.campo).where(
        AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001", AlertaBD.documento_id.is_(None))))


def test_procesar_una_credencial_quita_su_exp001(sesion, s3, folio):
    assert _exp001(sesion, folio) == ["comprobante_domicilio", "credencial_elector"]
    procesamiento.procesar(_subir(sesion, s3, folio).id)
    assert _exp001(sesion, folio) == ["comprobante_domicilio"]

    token = crear_token("revisor_ficticio", "revisor")[0]
    elemento = TestClient(app).get("/api/v1/folios", headers={"Authorization": f"Bearer {token}"}).json()
    assert elemento["elementos"][0]["n_bloqueantes_sin_resolver"] == 1


def test_exp001_revisada_se_conserva(sesion, s3, folio):
    alerta = sesion.scalar(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.campo == "credencial_elector"))
    alerta.aplica = False
    sesion.commit()
    procesamiento.procesar(_subir(sesion, s3, folio).id)
    assert _exp001(sesion, folio) == ["comprobante_domicilio", "credencial_elector"]
    sesion.expire_all()
    assert sesion.get(AlertaBD, alerta.id).aplica is False


def test_documento_en_error_o_pendiente_no_cuenta(sesion, s3, folio, monkeypatch):
    _subir(sesion, s3, folio, datos=PDF + b" pendiente")  # sin procesar: pendiente

    def rompe(contenido, **kwargs):
        raise RuntimeError("fallo forzado")

    monkeypatch.setattr(procesamiento, "analizar", rompe)
    procesamiento.procesar(_subir(sesion, s3, folio).id)  # queda en error
    expediente.recalcular_exp001(sesion, folio)
    sesion.commit()
    assert _exp001(sesion, folio) == ["comprobante_domicilio", "credencial_elector"]


def test_cuenta_el_tipo_detectado(sesion, s3, folio, monkeypatch):
    def detecta_comprobante(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        return resultado.model_copy(update={"tipo_documental_detectado": "comprobante_domicilio"}), datos

    monkeypatch.setattr(procesamiento, "analizar", detecta_comprobante)
    procesamiento.procesar(_subir(sesion, s3, folio, tipo="credencial_elector").id)
    assert _exp001(sesion, folio) == ["credencial_elector"]


def test_reprocesar_con_otro_tipo_vuelve_a_faltar(sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    procesamiento.procesar(doc.id)
    assert _exp001(sesion, folio) == ["comprobante_domicilio"]
    # Como confirmar-clasificacion: el confirmado se guarda y se reprocesa con el (el stub, como el motor
    # real, deja detectado a null; manda el confirmado de la BD, ADR-009)
    fila = sesion.get(Documento, doc.id)
    fila.tipo_documental_confirmado = "pasaporte"
    fila.estado_analisis = "pendiente"
    sesion.commit()
    procesamiento.procesar(doc.id, tipo_confirmado="pasaporte")
    sesion.expire_all()
    assert _exp001(sesion, folio) == ["comprobante_domicilio", "credencial_elector"]


def test_cuenta_el_confirmado_de_la_bd(sesion, s3, folio):
    doc = _subir(sesion, s3, folio, tipo="credencial_elector")
    procesamiento.procesar(doc.id)
    fila = sesion.get(Documento, doc.id)
    fila.tipo_documental_confirmado = "comprobante_domicilio"  # manda sobre el detectado
    expediente.recalcular_exp001(sesion, folio)
    sesion.commit()
    # credencial_elector ya no esta presente, pero su EXP-001 se borro al procesar: se vuelve a crear
    assert _exp001(sesion, folio) == ["credencial_elector"]


def test_dos_recalculos_no_duplican(sesion, s3, folio):
    procesamiento.procesar(_subir(sesion, s3, folio).id)
    expediente.recalcular_exp001(sesion, folio)
    expediente.recalcular_exp001(sesion, folio)
    sesion.commit()
    assert _exp001(sesion, folio) == ["comprobante_domicilio"]


def test_proceso_sin_requeridos_no_crea_nada(sesion, s3):
    folio = expediente.crear_folio(sesion, "sin_requeridos", None, "x").folio
    assert _exp001(sesion, folio) == []
    procesamiento.procesar(_subir(sesion, s3, folio, tipo="pasaporte").id)
    expediente.recalcular_exp001(sesion, folio)
    sesion.commit()
    assert _exp001(sesion, folio) == []
