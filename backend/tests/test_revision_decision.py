"""Tests de E2.6c: POST /folios/{folio}/decision y cierre del folio (ADR-006 2.2 y G). Datos ficticios."""
import importlib.util
import os
import threading
import uuid
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3, get_almacenamiento
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Auditoria, Documento, Folio, Proceso, SecuenciaFolio
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import DecisionHumana

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _entorno(monkeypatch, url):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": url,
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


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    _entorno(monkeypatch, f"sqlite:///{tmp_path / 'test.db'}")
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
        app.dependency_overrides[get_almacenamiento] = lambda: almacenamiento
        yield almacenamiento
        app.dependency_overrides.clear()


@pytest.fixture
def cliente(sesion):
    return TestClient(app)


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "x").folio


def _cab(rol="revisor") -> dict:
    return {"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"}


def _subir(sesion, s3, folio, tipo="credencial_elector", procesar=True, contenido=None):
    doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", contenido or f"%PDF-1.4 {tipo}".encode(), tipo, "x")
    if procesar:
        procesamiento.procesar(doc.id)
    return doc


def _completo(sesion, s3, folio):
    """Credencial y comprobante procesados (stub): sin EXP-001 ni bloqueantes."""
    _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, tipo="comprobante_domicilio")


def _decidir(cliente, folio, cuerpo, rol="revisor"):
    return cliente.post(f"/api/v1/folios/{folio}/decision", json=cuerpo, headers=_cab(rol))


def test_aprobar_sin_bloqueantes(cliente, sesion, s3, folio):
    _completo(sesion, s3, folio)
    r = _decidir(cliente, folio, {"decision": "aprobar", "comentario": "Todo correcto (ficticio)"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["estado_general"], cuerpo["decision_humana"]) == ("aprobado", "aprobar")
    assert (cuerpo["comentario_decision"], cuerpo["usuario_decision"]) == ("Todo correcto (ficticio)", "revisor_ficticio")
    assert cuerpo["fecha_decision"] is not None
    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "decision_tomada"))
    assert (registro.usuario, registro.folio, registro.detalle) == ("revisor_ficticio", folio, {"decision": "aprobar"})
    assert "correcto" not in str(registro.detalle)


def test_rechazar_con_bloqueante_sin_revisar(cliente, sesion, folio):
    r = _decidir(cliente, folio, {"decision": "rechazar"})  # folio nuevo: 2 EXP-001 sin revisar
    assert r.status_code == 200
    assert r.json()["estado_general"] == "rechazado"


@pytest.mark.parametrize("aplica,esperado", [(None, 409), (True, 409), (False, 200)])
def test_aprobar_con_exp001(cliente, sesion, s3, folio, aplica, esperado):
    _subir(sesion, s3, folio)  # queda la EXP-001 de comprobante_domicilio
    exp = sesion.scalar(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001"))
    exp.aplica = aplica
    sesion.commit()
    r = _decidir(cliente, folio, {"decision": "aprobar"})
    assert r.status_code == esperado
    if esperado == 409:
        assert r.json()["codigo"] == "DECISION_BLOQUEADA"
        sesion.expire_all()
        assert sesion.get(Folio, folio).estado_general == "en_revision"


@pytest.mark.parametrize("estado", ["pendiente", "procesando"])
@pytest.mark.parametrize("decision", ["aprobar", "rechazar"])
def test_documento_en_proceso_bloquea(cliente, sesion, s3, folio, estado, decision):
    doc = _subir(sesion, s3, folio, procesar=False)
    sesion.get(Documento, doc.id).estado_analisis = estado
    sesion.commit()
    r = _decidir(cliente, folio, {"decision": decision})
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")


def test_documento_en_error_no_bloquea(cliente, sesion, s3, folio):
    _completo(sesion, s3, folio)
    otro = _subir(sesion, s3, folio, tipo="pasaporte", procesar=False)
    sesion.get(Documento, otro.id).estado_analisis = "error"
    sesion.commit()
    assert _decidir(cliente, folio, {"decision": "aprobar"}).status_code == 200


def test_decidir_dos_veces(cliente, sesion, folio):
    assert _decidir(cliente, folio, {"decision": "rechazar"}).status_code == 200
    r = _decidir(cliente, folio, {"decision": "aprobar"})
    assert (r.status_code, r.json()["codigo"]) == (409, "FOLIO_CERRADO")
    assert sesion.query(Auditoria).filter_by(accion="decision_tomada").count() == 1


def test_tras_decidir_todas_las_acciones_dan_folio_cerrado(cliente, sesion, s3, folio):
    _subir(sesion, s3, folio)
    doc = _subir(sesion, s3, folio)  # duplicado procesado: tiene DUP-001
    dup = sesion.scalar(select(AlertaBD).where(AlertaBD.documento_id == doc.id, AlertaBD.codigo == "DUP-001"))
    exp = sesion.scalar(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001"))
    assert _decidir(cliente, folio, {"decision": "rechazar"}).status_code == 200

    acciones = {
        "subir documento": cliente.post(f"/api/v1/folios/{folio}/documentos", headers=_cab(),
                                        files={"archivo": ("otro.pdf", b"%PDF-1.4 otro", "application/pdf")}),
        "resolver alerta de documento": cliente.post(f"/api/v1/documentos/{doc.id}/alertas/{dup.id}/resolver",
                                                     json={"aplica": False}, headers=_cab()),
        "resolver alerta de expediente": cliente.post(f"/api/v1/folios/{folio}/alertas/{exp.id}/resolver",
                                                      json={"aplica": False}, headers=_cab()),
        "corregir datos": cliente.patch(f"/api/v1/documentos/{doc.id}/datos", json={"nombre_completo": "Ana"},
                                        headers=_cab()),
        "confirmar clasificacion": cliente.post(f"/api/v1/documentos/{doc.id}/confirmar-clasificacion",
                                                json={"tipo_documental": "pasaporte"}, headers=_cab()),
    }
    for nombre, r in acciones.items():
        assert (r.status_code, r.json()["codigo"]) == (409, "FOLIO_CERRADO"), nombre


@pytest.mark.parametrize("cuerpo", [{"decision": "cancelar"}, {}, {"decision": "aprobar", "extra": 1},
                                    {"decision": "rechazar", "comentario": "x" * 1001}])
def test_422(cliente, folio, cuerpo):
    r = _decidir(cliente, folio, cuerpo)
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")


def test_404_403_401(cliente, folio):
    r = _decidir(cliente, "ONB-2026-999999", {"decision": "rechazar"})
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")
    for rol in ("admin", "integrador"):
        assert _decidir(cliente, folio, {"decision": "rechazar"}, rol=rol).status_code == 403
    assert cliente.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"}).status_code == 401


# --- concurrencia real (solo PostgreSQL) ---

@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requiere TEST_POSTGRES_URL")
def test_decision_concurrente_postgres(monkeypatch):
    url = os.environ["TEST_POSTGRES_URL"]
    _entorno(monkeypatch, url)
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    proceso = "decision_concurrente_test"

    def limpiar():
        with Session(engine) as s:
            s.execute(delete(Auditoria).where(Auditoria.folio.like("DCT-%")))
            s.execute(delete(AlertaBD).where(AlertaBD.folio.like("DCT-%")))
            s.execute(delete(Folio).where(Folio.proceso == proceso))
            s.execute(delete(SecuenciaFolio).where(SecuenciaFolio.proceso == proceso))
            s.execute(delete(Proceso).where(Proceso.nombre == proceso))
            s.commit()

    limpiar()
    with Session(engine) as s:
        s.add(Proceso(nombre=proceso, prefijo_folio="DCT", tipos_requeridos=[], tipos_opcionales=[],
                      permitir_antecedentes=False, caducidad_antecedentes_dias=1))
        s.commit()
        folio = expediente.crear_folio(s, proceso, None, "x").folio

    resultados, salida = [], threading.Barrier(2)

    def decidir(usuario):
        with Session(engine) as s:
            salida.wait()
            try:
                expediente.decidir_folio(s, folio, DecisionHumana.aprobar, None, usuario)
                resultados.append(200)
            except ErrorApi as e:
                resultados.append((e.http, e.codigo))

    hilos = [threading.Thread(target=decidir, args=(f"revisor_{i}",)) for i in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    try:
        assert sorted(resultados, key=str) == sorted([200, (409, "FOLIO_CERRADO")], key=str)
        with Session(engine) as s:
            assert s.query(Auditoria).filter_by(accion="decision_tomada", folio=folio).count() == 1
    finally:
        limpiar()
        engine.dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()
