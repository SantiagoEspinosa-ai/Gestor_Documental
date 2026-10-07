"""Tests de E2.6b (2): POST /documentos/{id}/confirmar-clasificacion (ADR-006 2.5). Datos ficticios."""
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
from app.core.modelos import AlertaBD, Auditoria, Correccion, Documento, Folio, Proceso, Resultado
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import Alerta

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
URL = "/api/v1/documentos/{}/confirmar-clasificacion"

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


def _subir(sesion, s3, folio, tipo="credencial_elector", procesar=True):
    doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", f"%PDF-1.4 {tipo}".encode(), tipo, "x")
    if procesar:
        procesamiento.procesar(doc.id)
    return doc


def _confirmar(cliente, doc_id, tipo, rol="revisor"):
    return cliente.post(URL.format(doc_id), json={"tipo_documental": tipo}, headers=_cab(rol))


def _exp001(sesion, folio) -> list[str]:
    sesion.expire_all()
    return sorted(sesion.scalars(select(AlertaBD.campo).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001")))


def _auditoria(sesion) -> dict:
    sesion.expire_all()
    return sesion.scalar(select(Auditoria).where(Auditoria.accion == "clasificacion_confirmada")).detalle


def test_confirmar_el_mismo_tipo_resuelve_cls001_sin_reproceso(cliente, sesion, s3, folio, monkeypatch):
    def con_cls001(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        cls = Alerta(codigo="CLS-001", mensaje="El tipo detectado no coincide (ficticia)", severidad="critica",
                     confianza=0.9)
        return resultado.model_copy(update={"alertas_encontradas": [cls]}), datos

    monkeypatch.setattr(procesamiento, "analizar", con_cls001)
    doc = _subir(sesion, s3, folio)
    r = _confirmar(cliente, doc.id, "credencial_elector")
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["estado_analisis"], cuerpo["tipo_documental_confirmado"]) == ("completado", "credencial_elector")
    cls = next(a for a in cuerpo["alertas_encontradas"] if a["codigo"] == "CLS-001")
    assert (cls["aplica"], cls["resuelta_por"], cls["comentario_revisor"]) == \
        (False, "revisor_ficticio", "Resuelta al confirmar la clasificacion")
    assert sesion.query(Resultado).filter_by(documento_id=doc.id).count() == 1
    assert _auditoria(sesion) == {"tipo": "credencial_elector", "reproceso": False}


def test_confirmar_otro_tipo_reprocesa(cliente, sesion, s3, folio):
    doc = _subir(sesion, s3, folio)  # credencial: su EXP-001 desaparece
    assert _exp001(sesion, folio) == ["comprobante_domicilio"]
    _ = cliente.patch(f"/api/v1/documentos/{doc.id}/datos", json={"nombre_completo": "Ana Ejemplo"},
                      headers=_cab())
    assert sesion.scalar(select(Correccion.version_resultado)) == 1

    r = _confirmar(cliente, doc.id, "comprobante_domicilio")
    assert r.status_code == 200
    assert r.json()["estado_analisis"] == "pendiente"  # la respuesta sale antes de la BackgroundTask
    assert _auditoria(sesion) == {"tipo": "comprobante_domicilio", "reproceso": True}

    # TestClient ya ha ejecutado la BackgroundTask: version 2 con el tipo confirmado
    despues = cliente.get(f"/api/v1/documentos/{doc.id}", headers=_cab()).json()
    assert despues["estado_analisis"] == "completado"
    assert despues["tipo_documental_confirmado"] == "comprobante_domicilio"
    assert despues["tipo_documental_detectado"] is None  # ADR-009: con tipo confirmado no se clasifica
    assert despues["correcciones"] == []  # las de la v1 no se aplican sobre la v2
    assert sorted(sesion.scalars(select(Resultado.version).where(Resultado.documento_id == doc.id))) == [1, 2]
    assert _exp001(sesion, folio) == ["credencial_elector"]  # la del tipo anterior reaparece

    # una correccion nueva se guarda sobre la version 2
    r = cliente.patch(f"/api/v1/documentos/{doc.id}/datos", json={"domicilio": "Calle Ficticia 1"}, headers=_cab())
    assert r.status_code == 200
    sesion.expire_all()
    assert sorted(sesion.scalars(select(Correccion.version_resultado))) == [1, 2]


def test_422_tipo_inexistente_o_cuerpo_invalido(cliente, sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    for cuerpo in ({"tipo_documental": "tipo_inventado"}, {}, {"tipo_documental": "pasaporte", "extra": 1}):
        r = cliente.post(URL.format(doc.id), json=cuerpo, headers=_cab())
        assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).tipo_documental_confirmado is None


def test_409(cliente, sesion, s3, folio):
    pendiente = _subir(sesion, s3, folio, tipo="comprobante_domicilio", procesar=False)
    r = _confirmar(cliente, pendiente.id, "comprobante_domicilio")
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")
    sesion.get(Documento, pendiente.id).estado_analisis = "error"
    sesion.commit()
    r = _confirmar(cliente, pendiente.id, "comprobante_domicilio")
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_CON_ERROR")

    doc = _subir(sesion, s3, folio)
    sesion.get(Folio, folio).estado_general = "aprobado"
    sesion.commit()
    r = _confirmar(cliente, doc.id, "credencial_elector")
    assert (r.status_code, r.json()["codigo"]) == (409, "FOLIO_CERRADO")


def test_404_403_401(cliente, sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    r = _confirmar(cliente, uuid.uuid4(), "pasaporte")
    assert (r.status_code, r.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")
    for rol in ("admin", "integrador"):
        assert _confirmar(cliente, doc.id, "pasaporte", rol=rol).status_code == 403
    assert cliente.post(URL.format(doc.id), json={"tipo_documental": "pasaporte"}).status_code == 401
