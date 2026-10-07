"""Tests de la regeneracion del resumen.md tras cada cambio y de GET /folios/{folio}/resumen.md.
SQLite temporal + moto (S3 simulado), motor stub. Datos ficticios."""
import importlib.util
import logging
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3, ErrorAlmacenamiento
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import AlertaBD, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
BUCKET = "bucket-de-test"
REGION = "us-east-1"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


class Contador:
    """Envuelve el almacenamiento real (moto) y cuenta las regeneraciones."""

    def __init__(self, real):
        self.real, self.subidas = real, 0

    def subir_derivado(self, datos, clave, tipo_contenido):
        self.subidas += 1
        self.real.subir_derivado(datos, clave, tipo_contenido)

    def descargar(self, clave):
        return self.real.descargar(clave)


class Roto:
    def subir_derivado(self, datos, clave, tipo_contenido):
        raise ErrorAlmacenamiento("S3 caido (ficticio)")

    def descargar(self, clave):
        raise ErrorAlmacenamiento("S3 caido (ficticio)")


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
                      tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=30))
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
        real = AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia", secret_key=SECRETO,
                                segundos_url=60)
        contador = Contador(real)
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: real)
        monkeypatch.setattr(expediente, "_almacenamiento", lambda: contador)
        yield contador


def cliente(rol="revisor") -> TestClient:
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"
    return c


def _crear_folio(rol="revisor", referencia="CLI-000901") -> str:
    r = cliente(rol).post("/api/v1/folios", json={"proceso": "onboarding", "referencia_externa": referencia})
    assert r.status_code == 201
    return r.json()["folio"]


def _resumen(folio, rol="revisor"):
    return cliente(rol).get(f"/api/v1/folios/{folio}/resumen.md")


def test_crear_folio_genera_el_resumen_y_get_lo_devuelve_en_markdown(sesion, s3):
    folio = _crear_folio()
    r = _resumen(folio)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert r.text.startswith(f"# Expediente {folio}\n")
    assert "- Referencia: CLI-000901" in r.text
    assert "Sin documentos." in r.text


def test_ruta_resumen_md_en_el_expediente_y_objeto_en_s3(sesion, s3):
    folio = _crear_folio()
    ruta = cliente().get(f"/api/v1/folios/{folio}").json()["ruta_resumen_md"]
    _, anio, secuencia = folio.split("-")
    assert ruta == f"onboarding/{anio}/{secuencia}/resumen.md"  # junto a los originales del folio
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=ruta)
    assert (cabecera["ContentType"], cabecera["ServerSideEncryption"]) == ("text/markdown; charset=utf-8", "AES256")


def test_se_regenera_tras_cada_accion(sesion, s3, monkeypatch):
    avisos = []
    monkeypatch.setattr(expediente, "avisar_reindexar", lambda s, folio, texto: avisos.append((folio, texto)))
    folio = _crear_folio()
    assert s3.subidas == 1

    doc = ingestar(sesion, s3.real, folio, "credencial.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(doc.id)  # al terminar el analisis
    assert s3.subidas == 2
    assert "### Documento 1: Credencial de elector" in _resumen(folio).text

    c = cliente()
    assert c.patch(f"/api/v1/documentos/{doc.id}/datos", json={"nombre_completo": "Ana Ejemplo"}).status_code == 200
    assert s3.subidas == 3
    assert "- Nombre completo: Ana Ejemplo (corregido por revisor)" in _resumen(folio).text

    respuesta = c.post(f"/api/v1/documentos/{doc.id}/confirmar-clasificacion",
                       json={"tipo_documental": "credencial_elector"})  # el mismo tipo: sin reproceso
    assert respuesta.status_code == 200 and s3.subidas == 4

    # (resolver una alerta: test_resolver_una_alerta_del_expediente_regenera)
    assert c.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar", "comentario": "Ficticio"}).status_code == 200
    assert s3.subidas == 5
    texto = _resumen(folio).text
    assert "## Decision" in texto and "- Decision: Rechazado" in texto
    # avisar_reindexar tras cada regeneracion, con el mismo texto que se sube a S3
    assert len(avisos) == s3.subidas and {f for f, _ in avisos} == {folio}
    assert avisos[-1][1] == texto


def test_resolver_una_alerta_del_expediente_regenera(sesion, s3):
    folio = _crear_folio()  # con su EXP-001 de credencial_elector
    sesion.expire_all()
    exp001 = sesion.scalars(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "EXP-001")).one()
    antes = s3.subidas
    assert cliente().post(f"/api/v1/folios/{folio}/alertas/{exp001.id}/resolver", json={"aplica": False}).status_code == 200
    assert s3.subidas == antes + 1
    assert "(falso positivo)" in _resumen(folio).text


def test_un_fallo_de_s3_no_rompe_la_accion(sesion, monkeypatch, caplog):
    monkeypatch.setattr(expediente, "_almacenamiento", lambda: Roto())
    with caplog.at_level(logging.WARNING, logger="app.modulos.expediente.servicio"):
        folio = _crear_folio(referencia="CLI-SECRETA-01")
        r = cliente().post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})
    assert (r.status_code, r.json()["estado_general"]) == (200, "rechazado")
    assert "No se pudo subir el resumen" in caplog.text
    assert "CLI-SECRETA-01" not in caplog.text and "Expediente" not in caplog.text  # sin datos del resumen


def test_404_antes_del_primer_resumen_y_markdown_despues(sesion, s3, monkeypatch):
    monkeypatch.setattr(expediente, "_almacenamiento", lambda: Roto())
    folio = _crear_folio()  # S3 caido al crearlo: no hay resumen
    monkeypatch.setattr(expediente, "_almacenamiento", lambda: s3)
    r = _resumen(folio)
    assert (r.status_code, r.json()["codigo"]) == (404, "RESUMEN_NO_DISPONIBLE")
    cliente().post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})  # el siguiente cambio
    assert _resumen(folio).status_code == 200


def test_folio_inexistente_da_folio_no_encontrado(sesion, s3):
    r = _resumen("ONB-2026-999999")
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")


@pytest.mark.parametrize("rol", ["admin", "revisor", "integrador"])
def test_los_tres_roles_lo_pueden_leer(sesion, s3, rol):
    folio = _crear_folio("integrador")  # ADR-012: el integrador solo lee los suyos; revisor y admin, todos
    assert _resumen(folio, rol).status_code == 200


def test_sin_token_401(sesion, s3):
    folio = _crear_folio()
    assert TestClient(app).get(f"/api/v1/folios/{folio}/resumen.md").status_code == 401
