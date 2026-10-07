"""Tests de /api/v1/folios/{folio}/documentos y /api/v1/documentos. SQLite temporal y moto."""
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
from app.core.almacenamiento import AlmacenamientoS3, get_almacenamiento
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import AlertaBD, Auditoria, Documento, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import Alerta

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
PDF = b"%PDF-1.4 documento ficticio"
PNG = b"\x89PNG\r\n\x1a\n imagen ficticia"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


@pytest.fixture
def entorno(monkeypatch, tmp_path):
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
        for rol in ("admin", "revisor", "integrador"):
            script.crear_usuario(s, f"{rol}_ficticio", rol, "contrasena-ficticia")
        s.commit()
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        s3 = AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                              secret_key=SECRETO, segundos_url=60)
        app.dependency_overrides[get_almacenamiento] = lambda: s3
        # la BackgroundTask no usa la inyeccion de FastAPI: tambien al S3 de moto
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: s3)
        try:
            yield s3
        finally:
            app.dependency_overrides.clear()
            db.get_engine().dispose()
            get_settings.cache_clear()
            db.get_engine.cache_clear()


@pytest.fixture
def sesion(entorno):
    with Session(db.get_engine()) as s:
        yield s


@pytest.fixture
def cliente(entorno):
    return TestClient(app)


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "integrador_ficticio").folio


def _cab(rol: str) -> dict:
    return {"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"}


def _subir(cliente, folio, nombre="credencial_ficticia.pdf", datos=PDF, tipo_mime="application/pdf",
           rol="integrador", tipo_declarado="credencial_elector"):
    return cliente.post(f"/api/v1/folios/{folio}/documentos", headers=_cab(rol),
                        files={"archivo": (nombre, datos, tipo_mime)},
                        data={"tipo_declarado": tipo_declarado} if tipo_declarado else None)


def test_subir_202_y_procesamiento_en_segundo_plano(cliente, folio):
    r = _subir(cliente, folio)
    assert r.status_code == 202
    cuerpo = r.json()
    assert cuerpo["estado_analisis"] == "pendiente"
    doc_id = cuerpo["identificador_unico_documento"]

    # TestClient ejecuta la BackgroundTask al terminar la respuesta
    r = cliente.get(f"/api/v1/documentos/{doc_id}", headers=_cab("integrador"))
    assert r.status_code == 200
    assert r.json()["estado_analisis"] == "completado"
    assert r.json()["fecha_y_modelo_utilizado"]["version_prompt"] == "stub@v0"


def test_content_type_sale_de_la_extension(cliente, folio, sesion):
    r = _subir(cliente, folio, tipo_mime="text/html")
    doc = sesion.get(Documento, uuid.UUID(r.json()["identificador_unico_documento"]))
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=doc.ruta_s3)
    assert cabecera["ContentType"] == "application/pdf"


def test_pdf_con_bytes_de_png(cliente, folio):
    r = _subir(cliente, folio, datos=PNG)
    assert (r.status_code, r.json()["codigo"]) == (415, "FORMATO_NO_PERMITIDO")


def test_nombre_largo_recortado(cliente, folio, sesion):
    r = _subir(cliente, folio, nombre="n" * 300 + ".pdf")
    doc = sesion.get(Documento, uuid.UUID(r.json()["identificador_unico_documento"]))
    assert len(doc.nombre_archivo) == 255
    assert doc.nombre_archivo.endswith(".pdf")


def test_archivo_demasiado_grande(cliente, folio, sesion):
    r = _subir(cliente, folio, datos=PDF + b"x" * (20 * 1024 * 1024 + 1 - len(PDF)))
    assert (r.status_code, r.json()["codigo"]) == (413, "ARCHIVO_DEMASIADO_GRANDE")
    assert sesion.scalar(select(Documento)) is None


def test_admin_no_sube(cliente, folio):
    assert _subir(cliente, folio, rol="admin").status_code == 403


def _vistos(sesion) -> list[Auditoria]:
    sesion.expire_all()
    return list(sesion.scalars(select(Auditoria).where(Auditoria.accion == "original_visto")))


def test_integrador_no_pide_el_original(cliente, folio, sesion):
    doc_id = _subir(cliente, folio).json()["identificador_unico_documento"]
    r = cliente.get(f"/api/v1/documentos/{doc_id}/original", headers=_cab("integrador"))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
    assert _vistos(sesion) == []  # sin permiso no deja registro


def test_sin_token(cliente, folio):
    assert cliente.post(f"/api/v1/folios/{folio}/documentos",
                        files={"archivo": ("a.pdf", PDF, "application/pdf")}).status_code == 401
    assert cliente.get(f"/api/v1/documentos/{uuid.uuid4()}").status_code == 401
    assert cliente.get(f"/api/v1/documentos/{uuid.uuid4()}/original").status_code == 401


@pytest.mark.parametrize("doc_id", ["no-es-un-uuid", str(uuid.uuid4())])
def test_documento_invalido_o_inexistente(cliente, doc_id):
    for ruta in (f"/api/v1/documentos/{doc_id}", f"/api/v1/documentos/{doc_id}/original"):
        r = cliente.get(ruta, headers=_cab("revisor"))
        assert (r.status_code, r.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")


def test_documento_sin_resultado_da_pendiente_con_dup(cliente, folio, sesion, entorno):
    ingestar(sesion, entorno, folio, "a.pdf", PDF, "credencial_elector", "x")
    duplicado = ingestar(sesion, entorno, folio, "a.pdf", PDF, "credencial_elector", "x")  # sin BackgroundTask

    r = cliente.get(f"/api/v1/documentos/{duplicado.id}", headers=_cab("integrador")).json()
    assert r["estado_analisis"] == "pendiente"
    assert r["tipo_documental_declarado"] == "credencial_elector"
    assert r["referencia_archivo_original"]["ruta"] == duplicado.ruta_s3
    assert [a["codigo"] for a in r["alertas_encontradas"]] == ["DUP-001"]
    assert uuid.UUID(r["alertas_encontradas"][0]["id"])


def test_original_devuelve_url_firmada(cliente, folio, sesion):
    doc_id = _subir(cliente, folio).json()["identificador_unico_documento"]
    r = cliente.get(f"/api/v1/documentos/{doc_id}/original", headers=_cab("revisor"))
    assert r.status_code == 200
    url = r.json()["url"]
    ruta = sesion.get(Documento, uuid.UUID(doc_id)).ruta_s3
    assert BUCKET in url and ruta in url
    assert "X-Amz-Signature=" in url or "Signature=" in url


def test_pedir_el_original_deja_original_visto(cliente, folio, sesion):
    doc_id = _subir(cliente, folio).json()["identificador_unico_documento"]
    for rol in ("revisor", "admin"):
        assert cliente.get(f"/api/v1/documentos/{doc_id}/original", headers=_cab(rol)).status_code == 200
    # usuario, folio y documento en sus columnas; nada del contenido en el detalle
    assert [(e.usuario, e.folio, e.documento_id, e.detalle) for e in _vistos(sesion)] == [
        ("revisor_ficticio", folio, uuid.UUID(doc_id), {}), ("admin_ficticio", folio, uuid.UUID(doc_id), {})]
    entradas = cliente.get("/api/v1/auditoria", headers=_cab("admin")).json()["elementos"]
    assert sum(e["accion"] == "original_visto" for e in entradas) == 2


def test_original_inexistente_no_deja_registro(cliente, sesion):
    assert cliente.get(f"/api/v1/documentos/{uuid.uuid4()}/original", headers=_cab("revisor")).status_code == 404
    assert _vistos(sesion) == []


# --- mismo armado en GET /documentos/{id} y en GET /folios/{folio} (BD como fuente de verdad) ---

def _en_expediente(cliente, folio, doc_id) -> dict:
    r = cliente.get(f"/api/v1/folios/{folio}", headers=_cab("revisor")).json()
    return next(d for d in r["documentos"] if d["identificador_unico_documento"] == str(doc_id))


def test_expediente_incluye_documentos_sin_procesar(cliente, folio, sesion, entorno):
    ingestar(sesion, entorno, folio, "a.pdf", PDF, "credencial_elector", "x")
    duplicado = ingestar(sesion, entorno, folio, "a.pdf", PDF, "credencial_elector", "x")  # sin BackgroundTask

    expediente = cliente.get(f"/api/v1/folios/{folio}", headers=_cab("revisor")).json()
    lista = cliente.get("/api/v1/folios", headers=_cab("revisor")).json()["elementos"]
    assert len(expediente["documentos"]) == lista[0]["n_documentos"] == 2
    doc = _en_expediente(cliente, folio, duplicado.id)
    assert doc["estado_analisis"] == "pendiente"
    assert [a["codigo"] for a in doc["alertas_encontradas"]] == ["DUP-001"]
    assert doc == cliente.get(f"/api/v1/documentos/{duplicado.id}", headers=_cab("revisor")).json()


def test_cambio_de_aplica_en_bd_se_ve_en_los_dos(cliente, folio, sesion):
    _subir(cliente, folio)
    doc_id = uuid.UUID(_subir(cliente, folio).json()["identificador_unico_documento"])  # procesado, con DUP-001
    alerta = sesion.scalar(select(AlertaBD).where(AlertaBD.documento_id == doc_id))
    alerta.aplica = False
    alerta.comentario = "Falso positivo (ficticio)"
    sesion.commit()

    directo = cliente.get(f"/api/v1/documentos/{doc_id}", headers=_cab("revisor")).json()
    for doc in (directo, _en_expediente(cliente, folio, doc_id)):
        assert doc["estado_analisis"] == "completado"
        assert [(a["id"], a["aplica"], a["comentario_revisor"]) for a in doc["alertas_encontradas"]] == \
            [(str(alerta.id), False, "Falso positivo (ficticio)")]


def test_cambio_de_estado_y_tipo_confirmado_en_bd_se_ve_en_los_dos(cliente, folio, sesion):
    doc_id = uuid.UUID(_subir(cliente, folio).json()["identificador_unico_documento"])  # procesado (v1)
    fila = sesion.get(Documento, doc_id)
    fila.estado_analisis = "error"
    fila.tipo_documental_confirmado = "pasaporte"
    sesion.commit()

    directo = cliente.get(f"/api/v1/documentos/{doc_id}", headers=_cab("revisor")).json()
    for doc in (directo, _en_expediente(cliente, folio, doc_id)):
        assert (doc["estado_analisis"], doc["tipo_documental_confirmado"]) == ("error", "pasaporte")
        assert doc["fecha_y_modelo_utilizado"]["version_prompt"] == "stub@v0"  # el resto sale del resultado


def test_get_documento_muestra_las_alertas_del_motor(cliente, folio, monkeypatch):
    def analizar(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        alerta = Alerta(codigo="VAL-001", mensaje="Falta un campo obligatorio (ficticio)",
                        severidad="critica", confianza=1.0, campo="nombre_completo")
        return resultado.model_copy(update={"alertas_encontradas": [alerta]}), datos

    monkeypatch.setattr(procesamiento, "analizar", analizar)
    doc_id = _subir(cliente, folio).json()["identificador_unico_documento"]
    r = cliente.get(f"/api/v1/documentos/{doc_id}", headers=_cab("revisor")).json()
    assert r["estado_analisis"] == "completado"
    assert [(a["codigo"], a["campo"]) for a in r["alertas_encontradas"]] == [("VAL-001", "nombre_completo")]
    assert uuid.UUID(r["alertas_encontradas"][0]["id"])
