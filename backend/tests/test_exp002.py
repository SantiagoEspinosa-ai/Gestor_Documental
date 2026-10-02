"""Tests de EXP-002 (documento de un tipo que el proceso no pide). Proceso de test sin pasaporte, para
no tocar los YAML del repo. SQLite temporal + moto; motor stub. Datos ficticios."""
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
from app.core.modelos import AlertaBD, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.configuracion import servicio as configuracion
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"

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
        s.add(Proceso(nombre="sin_pasaporte", prefijo_folio="SPA",
                      tipos_requeridos=["credencial_elector", "comprobante_domicilio"], tipos_opcionales=[],
                      permitir_antecedentes=False, caducidad_antecedentes_dias=30))
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
def cliente(sesion):
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    return cliente


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "sin_pasaporte", None, "x").folio


def _subir(sesion, s3, folio, tipo):
    doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", f"%PDF-1.4 {tipo}".encode(), tipo, "x")
    procesamiento.procesar(doc.id)
    return doc


def _exp002(sesion, doc_id) -> list[AlertaBD]:
    sesion.expire_all()
    return sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id == doc_id, AlertaBD.codigo == "EXP-002")).all()


def test_documento_de_tipo_no_previsto_lleva_exp002(cliente, sesion, s3, folio):
    pasaporte = _subir(sesion, s3, folio, "pasaporte")
    [alerta] = _exp002(sesion, pasaporte.id)
    assert (alerta.campo, alerta.severidad, alerta.version_resultado, alerta.folio) == \
        ("pasaporte", "informativa", None, folio)
    assert alerta.mensaje == "Tipo de documento no previsto en el proceso: Pasaporte"
    documento = cliente.get(f"/api/v1/documentos/{pasaporte.id}").json()
    assert [a["codigo"] for a in documento["alertas_encontradas"]] == ["EXP-002"]
    assert not [a for a in cliente.get(f"/api/v1/folios/{folio}").json()["alertas_expediente"]
                if a["codigo"] == "EXP-002"]


def test_exp002_no_bloquea_ni_cambia_la_recomendacion(cliente, sesion, s3, folio):
    _subir(sesion, s3, folio, "credencial_elector")
    _subir(sesion, s3, folio, "comprobante_domicilio")
    assert cliente.get(f"/api/v1/folios/{folio}").json()["recomendacion_global"] == "aprobar"
    _subir(sesion, s3, folio, "pasaporte")  # con su EXP-002 informativa
    expediente_api = cliente.get(f"/api/v1/folios/{folio}").json()
    assert expediente_api["recomendacion_global"] == "aprobar"
    assert cliente.get("/api/v1/folios").json()["elementos"][0]["n_bloqueantes_sin_resolver"] == 0
    assert cliente.post(f"/api/v1/folios/{folio}/decision", json={"decision": "aprobar"}).status_code == 200


def test_desaparece_al_confirmar_un_tipo_previsto(cliente, sesion, s3, folio):
    doc = _subir(sesion, s3, folio, "pasaporte")
    assert len(_exp002(sesion, doc.id)) == 1
    r = cliente.post(f"/api/v1/documentos/{doc.id}/confirmar-clasificacion",
                     json={"tipo_documental": "credencial_elector"})
    assert r.status_code == 200  # reproceso en segundo plano (TestClient lo ejecuta)
    assert cliente.get(f"/api/v1/documentos/{doc.id}").json()["estado_analisis"] == "completado"
    assert _exp002(sesion, doc.id) == []


def test_no_se_duplica(sesion, s3, folio):
    doc = _subir(sesion, s3, folio, "pasaporte")
    expediente.recalcular_exp002(sesion, folio)
    expediente.recalcular_exp002(sesion, folio)
    sesion.commit()
    assert len(_exp002(sesion, doc.id)) == 1


def test_falso_positivo_se_conserva(cliente, sesion, s3, folio):
    doc = _subir(sesion, s3, folio, "pasaporte")
    [alerta] = _exp002(sesion, doc.id)
    alerta_id = alerta.id
    assert cliente.post(f"/api/v1/documentos/{doc.id}/alertas/{alerta_id}/resolver",
                        json={"aplica": False}).status_code == 200
    cliente.post(f"/api/v1/documentos/{doc.id}/confirmar-clasificacion", json={"tipo_documental": "credencial_elector"})
    alertas = _exp002(sesion, doc.id)
    assert [(a.id, a.aplica) for a in alertas] == [(alerta_id, False)]


def test_desconocido_sin_declarado_lleva_exp002_no_reconocido_y_no_cubre_requeridos(sesion, s3, folio, monkeypatch):
    # ADR-009, punto 4 (sin tipo declarado ni confirmado): EXP-002 en el documento + EXP-001 de los requeridos
    def analizar(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        return resultado.model_copy(update={"tipo_documental_detectado": configuracion.NOMBRE_RESERVADO,
                                            "datos_extraidos": {}}), datos
    monkeypatch.setattr(procesamiento, "analizar", analizar)
    doc = ingestar(sesion, s3, folio, "documento.pdf", b"%PDF-1.4 sin tipo", None, "x")
    procesamiento.procesar(doc.id)

    [alerta] = _exp002(sesion, doc.id)
    assert (alerta.campo, alerta.mensaje, alerta.severidad) == \
        ("desconocido", "Tipo de documento no reconocido", "informativa")
    exp001 = sesion.scalars(select(AlertaBD.campo).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001"))
    assert sorted(exp001) == ["comprobante_domicilio", "credencial_elector"]  # "desconocido" no cubre ninguno
