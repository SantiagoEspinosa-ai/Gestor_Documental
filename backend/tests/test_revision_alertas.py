"""Tests de E2.6a: resolver alertas de documento y de expediente (api/revision.py). Datos ficticios."""
import importlib.util
import uuid
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
from app.core.modelos import AlertaBD, Auditoria, Documento, Folio, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import Alerta

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
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB",
                      tipos_requeridos=["credencial_elector", "comprobante_domicilio"],
                      tipos_opcionales=["pasaporte"], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        for rol in ("admin", "revisor", "integrador"):
            script.crear_usuario(s, f"{rol}_ficticio", rol, "contrasena-ficticia")
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
    return TestClient(app)


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "x").folio


def _cab(rol="revisor") -> dict:
    return {"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"}


def _subir(sesion, s3, folio, tipo="credencial_elector", contenido=b"%PDF-1.4 ficticio", procesar=True):
    doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", contenido, tipo, "x")
    if procesar:
        procesamiento.procesar(doc.id)
    return doc


def _duplicado(sesion, s3, folio):
    """Documento procesado con su DUP-001 (de plataforma)."""
    _subir(sesion, s3, folio)
    doc = _subir(sesion, s3, folio)
    alerta = sesion.scalar(select(AlertaBD).where(AlertaBD.documento_id == doc.id, AlertaBD.codigo == "DUP-001"))
    return doc, alerta


def _exp001(sesion, folio, campo="credencial_elector") -> AlertaBD:
    sesion.expire_all()
    return sesion.scalar(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001",
                                                AlertaBD.campo == campo))


def _resolver_doc(cliente, doc_id, alerta_id, cuerpo=None, rol="revisor"):
    return cliente.post(f"/api/v1/documentos/{doc_id}/alertas/{alerta_id}/resolver",
                        json=cuerpo if cuerpo is not None else {"aplica": False}, headers=_cab(rol))


def _resolver_exp(cliente, folio, alerta_id, cuerpo=None, rol="revisor"):
    return cliente.post(f"/api/v1/folios/{folio}/alertas/{alerta_id}/resolver",
                        json=cuerpo if cuerpo is not None else {"aplica": False}, headers=_cab(rol))


# --- resolver ---

def test_resolver_dup_001_de_documento(cliente, sesion, s3, folio):
    doc, alerta = _duplicado(sesion, s3, folio)
    r = _resolver_doc(cliente, doc.id, alerta.id, {"aplica": False, "comentario": "Se subio dos veces por error"})
    assert r.status_code == 200
    dup = next(a for a in r.json()["alertas_encontradas"] if a["id"] == str(alerta.id))
    assert (dup["aplica"], dup["comentario_revisor"], dup["resuelta_por"]) == \
        (False, "Se subio dos veces por error", "revisor_ficticio")
    assert dup["resuelta_por_revisor"] is True and dup["resuelta_en"] is not None

    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "alerta_resuelta"))
    assert (registro.usuario, registro.folio, registro.documento_id) == ("revisor_ficticio", folio, doc.id)
    assert registro.detalle == {"alerta_id": str(alerta.id), "codigo": "DUP-001", "aplica": False}
    assert "dos veces" not in str(registro.detalle)


def test_resolver_exp_001_cambia_la_recomendacion(cliente, sesion, s3, folio):
    # Credencial procesada (stub: clasificacion 1.0): solo frena la EXP-001 de comprobante_domicilio
    _subir(sesion, s3, folio)
    assert cliente.get(f"/api/v1/folios/{folio}", headers=_cab()).json()["recomendacion_global"] == "revision_manual"
    exp = _exp001(sesion, folio, "comprobante_domicilio")
    r = _resolver_exp(cliente, folio, exp.id, {"aplica": False})
    assert r.status_code == 200
    assert r.json()["recomendacion_global"] == "aprobar"
    resuelta = next(a for a in r.json()["alertas_expediente"] if a["id"] == str(exp.id))
    assert (resuelta["aplica"], resuelta["resuelta_por"]) == (False, "revisor_ficticio")
    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "alerta_resuelta"))
    assert registro.documento_id is None and registro.detalle["codigo"] == "EXP-001"


def test_volver_a_resolver_sobrescribe(cliente, sesion, s3, folio):
    doc, alerta = _duplicado(sesion, s3, folio)
    _resolver_doc(cliente, doc.id, alerta.id, {"aplica": True, "comentario": "primero"})
    r = _resolver_doc(cliente, doc.id, alerta.id, {"aplica": False})
    dup = next(a for a in r.json()["alertas_encontradas"] if a["id"] == str(alerta.id))
    assert (dup["aplica"], dup["comentario_revisor"]) == (False, None)
    assert sesion.query(Auditoria).filter_by(accion="alerta_resuelta").count() == 2


# --- 404 ---

def test_404_documento_y_folio(cliente, sesion, s3, folio):
    _, alerta = _duplicado(sesion, s3, folio)
    for doc_id in (uuid.uuid4(), "no-es-uuid"):
        r = _resolver_doc(cliente, doc_id, alerta.id)
        assert (r.status_code, r.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")
    r = _resolver_exp(cliente, "ONB-2026-999999", _exp001(sesion, folio, "comprobante_domicilio").id)
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")


def test_404_alertas(cliente, sesion, s3, folio):
    doc, dup = _duplicado(sesion, s3, folio)
    otro_doc = _subir(sesion, s3, folio, tipo="pasaporte", contenido=b"%PDF-1.4 otro")
    otro_folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    exp = _exp001(sesion, folio, "comprobante_domicilio")
    exp_otro_folio = _exp001(sesion, otro_folio)
    casos = [
        _resolver_doc(cliente, doc.id, uuid.uuid4()),          # inexistente
        _resolver_doc(cliente, doc.id, "no-es-uuid"),           # no es UUID
        _resolver_doc(cliente, otro_doc.id, dup.id),            # de otro documento
        _resolver_doc(cliente, doc.id, exp.id),                 # de expediente por la ruta de documento
        _resolver_exp(cliente, folio, dup.id),                  # de documento por la ruta de expediente
        _resolver_exp(cliente, folio, exp_otro_folio.id),       # de otro folio
        _resolver_exp(cliente, folio, "no-es-uuid"),
    ]
    for r in casos:
        assert (r.status_code, r.json()["codigo"]) == (404, "ALERTA_NO_ENCONTRADA")


def test_404_alerta_del_motor_de_una_version_anterior(cliente, sesion, s3, folio, monkeypatch):
    def con_val001(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        alerta = Alerta(codigo="VAL-001", mensaje="ficticia", severidad="critica", confianza=1.0)
        return resultado.model_copy(update={"alertas_encontradas": [alerta]}), datos

    monkeypatch.setattr(procesamiento, "analizar", con_val001)
    doc = _subir(sesion, s3, folio)
    vieja = sesion.scalar(select(AlertaBD).where(AlertaBD.codigo == "VAL-001"))
    assert _resolver_doc(cliente, doc.id, vieja.id).status_code == 200  # vigente (v1)
    procesamiento.procesar(doc.id)  # v2: la de v1 deja de ser visible
    r = _resolver_doc(cliente, doc.id, vieja.id)
    assert (r.status_code, r.json()["codigo"]) == (404, "ALERTA_NO_ENCONTRADA")


# --- 409 ---

def test_409_folio_cerrado(cliente, sesion, s3, folio):
    doc, dup = _duplicado(sesion, s3, folio)
    exp = _exp001(sesion, folio, "comprobante_domicilio")
    sesion.get(Folio, folio).estado_general = "aprobado"
    sesion.commit()
    for r in (_resolver_doc(cliente, doc.id, dup.id), _resolver_exp(cliente, folio, exp.id)):
        assert (r.status_code, r.json()["codigo"]) == (409, "FOLIO_CERRADO")


def test_409_documento_en_proceso_y_en_error_si(cliente, sesion, s3, folio):
    _subir(sesion, s3, folio, procesar=False)
    pendiente = _subir(sesion, s3, folio, procesar=False)  # duplicado sin procesar
    dup = sesion.scalar(select(AlertaBD).where(AlertaBD.documento_id == pendiente.id))
    r = _resolver_doc(cliente, pendiente.id, dup.id)
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")

    sesion.get(Documento, pendiente.id).estado_analisis = "error"
    sesion.commit()
    assert _resolver_doc(cliente, pendiente.id, dup.id).status_code == 200


# --- 422, roles, token ---

@pytest.mark.parametrize("cuerpo", [{}, {"comentario": "sin aplica"}, {"aplica": False, "extra": 1},
                                    {"aplica": False, "comentario": "x" * 1001}, {"aplica": "si"}])
def test_422(cliente, sesion, s3, folio, cuerpo):
    doc, dup = _duplicado(sesion, s3, folio)
    r = _resolver_doc(cliente, doc.id, dup.id, cuerpo)
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")


@pytest.mark.parametrize("rol", ["admin", "integrador"])
def test_403_otros_roles(cliente, sesion, s3, folio, rol):
    doc, dup = _duplicado(sesion, s3, folio)
    assert _resolver_doc(cliente, doc.id, dup.id, rol=rol).status_code == 403
    assert _resolver_exp(cliente, folio, _exp001(sesion, folio, "comprobante_domicilio").id, rol=rol).status_code == 403


def test_401_sin_token(cliente, folio):
    for ruta in (f"/api/v1/documentos/{uuid.uuid4()}/alertas/{uuid.uuid4()}/resolver",
                 f"/api/v1/folios/{folio}/alertas/{uuid.uuid4()}/resolver"):
        assert cliente.post(ruta, json={"aplica": False}).status_code == 401


# --- las resueltas sobreviven a los recalculos ---

def test_exp_001_resuelta_sobrevive_al_recalculo(cliente, sesion, s3, folio):
    exp = _exp001(sesion, folio)
    assert _resolver_exp(cliente, folio, exp.id, {"aplica": False}).status_code == 200
    _subir(sesion, s3, folio)  # llega la credencial: el recalculo conserva la revisada
    sesion.expire_all()
    assert sesion.get(AlertaBD, exp.id).aplica is False


def test_cmp_001_resuelta_sobrevive_al_recalculo(cliente, sesion, s3, folio, monkeypatch):
    domicilios = {"credencial_elector": "Calle Ficticia 123", "comprobante_domicilio": "Avenida Inventada 456"}

    def analizar(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        return resultado.model_copy(update={"datos_extraidos": {"domicilio": domicilios[kwargs["tipo_declarado"]]}}), datos

    monkeypatch.setattr(procesamiento, "analizar", analizar)
    _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, tipo="comprobante_domicilio", contenido=b"%PDF-1.4 comprobante")
    cmp = sesion.scalar(select(AlertaBD).where(AlertaBD.codigo == "CMP-001"))
    assert _resolver_exp(cliente, folio, cmp.id, {"aplica": False}).status_code == 200
    expediente.recalcular_cmp001(sesion, folio)
    sesion.commit()
    sesion.expire_all()
    assert [(a.id, a.aplica) for a in sesion.scalars(select(AlertaBD).where(AlertaBD.codigo == "CMP-001"))] == \
        [(cmp.id, False)]
