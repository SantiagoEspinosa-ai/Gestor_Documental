"""Tests de core/webhooks.py y de su disparo desde el procesamiento y la decision. Receptor falso con
httpx.MockTransport (sin red), SQLite temporal + moto, motor stub o falso. Datos ficticios."""
import hashlib
import hmac
import importlib.util
import json
import logging
from pathlib import Path

import boto3
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from moto import mock_aws
from sqlalchemy.orm import Session

from app.core import db, webhooks
from app.core.almacenamiento import AlmacenamientoS3
from app.core.config import Settings, get_settings
from app.core.db import Base
from app.core.modelos import Documento, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import EstadoAnalisis, ReferenciaArchivoOriginal, ResultadoDocumento

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
URL = "https://receptor.ejemplo.test/hooks/ruta-secreta?token=abc"
CLAVES_DOCUMENTO = {"evento", "fecha", "folio", "identificador_unico_documento", "datos"}
CLAVES_FOLIO = {"evento", "fecha", "folio", "datos"}

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


class Receptor:
    """Responde con los estados de `respuestas` en orden (el ultimo se repite) y guarda cada peticion."""

    def __init__(self, *respuestas: int):
        self.respuestas = list(respuestas) or [200]
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        estado = self.respuestas[min(len(self.peticiones), len(self.respuestas)) - 1]
        cabeceras = {"Location": "https://otro.ejemplo.test/destino"} if 300 <= estado < 400 else {}
        return httpx.Response(estado, headers=cabeceras)

    def cuerpos(self) -> list[dict]:
        return [json.loads(p.content) for p in self.peticiones]


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia",
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO,
        "APP_ENV": "dev",
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    esperas: list[float] = []
    monkeypatch.setattr(webhooks, "_esperar", esperas.append)  # sin esperar de verdad
    monkeypatch.setattr(webhooks, "_lanzar", lambda funcion: funcion())  # sin hilo: deterministico
    yield esperas
    get_settings.cache_clear()


def receptor(monkeypatch, *respuestas: int) -> Receptor:
    r = Receptor(*respuestas)
    monkeypatch.setattr(webhooks, "_transporte", httpx.MockTransport(r))
    return r


def resultado_ficticio():
    resultado, _ = motor_stub.procesar_documento(
        b"%PDF-1.4", identificador="00000000-0000-4000-8000-000000000001", nombre_archivo="ficticio.pdf",
        tipo_declarado="pasaporte", folio="TST-2026-000001",
        referencia=ReferenciaArchivoOriginal(nombre_archivo="ficticio.pdf", ruta="x/y.pdf", hash="0" * 64))
    return resultado


def entregar(evento="documento.completado"):
    return webhooks.entregar(URL, evento, "TST-2026-000001", resultado_ficticio(),
                             identificador="00000000-0000-4000-8000-000000000001")


# --- core/webhooks.py ---

def test_firma_sobre_los_mismos_bytes_y_cuerpo_del_contrato(entorno, monkeypatch):
    r = receptor(monkeypatch, 200)
    assert entregar() is True
    [peticion] = r.peticiones
    esperada = "sha256=" + hmac.new(SECRETO.encode(), peticion.content, hashlib.sha256).hexdigest()
    assert peticion.headers["X-Firma"] == esperada
    assert peticion.headers["Content-Type"] == "application/json"
    assert str(peticion.url) == URL
    cuerpo = json.loads(peticion.content)
    assert set(cuerpo) == CLAVES_DOCUMENTO
    assert (cuerpo["evento"], cuerpo["folio"]) == ("documento.completado", "TST-2026-000001")
    assert set(cuerpo["datos"]) == set(ResultadoDocumento.model_fields)  # serializado como en la API
    assert entorno == []  # primer intento inmediato: sin espera


def test_folio_estado_cambiado_sin_identificador(entorno, monkeypatch):
    r = receptor(monkeypatch, 200)
    assert entregar("folio.estado_cambiado") is True
    assert set(r.cuerpos()[0]) == CLAVES_FOLIO


def test_500_500_200_son_3_llamadas_y_exito(entorno, monkeypatch):
    r = receptor(monkeypatch, 500, 500, 200)
    assert entregar() is True
    assert len(r.peticiones) == 3
    assert entorno == [1, 5]


def test_siempre_500_son_4_intentos_y_nada_mas(entorno, monkeypatch):
    r = receptor(monkeypatch, 500)
    assert entregar() is False
    assert len(r.peticiones) == 4  # el primero y 3 reintentos
    assert entorno == [1, 5, 25]


def test_sin_respuesta_cuenta_como_fallo_4_intentos(entorno, monkeypatch):
    llamadas = []

    def caido(peticion):
        llamadas.append(peticion)
        raise httpx.ConnectTimeout("sin respuesta")
    monkeypatch.setattr(webhooks, "_transporte", httpx.MockTransport(caido))
    assert entregar() is False
    assert len(llamadas) == 4


def test_un_302_no_se_sigue_y_es_un_fallo(entorno, monkeypatch):
    r = receptor(monkeypatch, 302)
    assert entregar() is False
    assert len(r.peticiones) == 4
    assert {p.url.host for p in r.peticiones} == {"receptor.ejemplo.test"}  # nunca va a la Location


def test_fuera_de_dev_solo_https(entorno, monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    r = receptor(monkeypatch, 200)
    with caplog.at_level(logging.WARNING):
        assert webhooks.entregar("http://receptor.ejemplo.test/hooks/ruta-secreta?token=abc", "documento.completado",
                                 "TST-2026-000001", resultado_ficticio(), "id") is False
    assert r.peticiones == []
    assert "solo se admite https" in caplog.text
    assert "ruta-secreta" not in caplog.text and "token" not in caplog.text


def test_en_dev_se_admite_http(entorno, monkeypatch):
    r = receptor(monkeypatch, 200)
    assert webhooks.entregar("http://localhost:9000/hook", "documento.completado", "TST-2026-000001",
                             resultado_ficticio(), "id") is True
    assert len(r.peticiones) == 1


def test_secreto_de_ejemplo_fuera_de_dev_no_envia(entorno, monkeypatch):
    # Settings ya no arranca en prod con el valor de ejemplo; aqui se comprueba la defensa del propio modulo
    falsos = Settings.model_construct(app_env="prod", webhook_secret_hmac=SecretStr("CAMBIA_ESTO"))
    monkeypatch.setattr(webhooks, "get_settings", lambda: falsos)
    r = receptor(monkeypatch, 200)
    assert entregar() is False
    assert r.peticiones == []


def test_secreto_vacio_no_envia(entorno, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_HMAC", "")
    get_settings.cache_clear()
    r = receptor(monkeypatch, 200)
    assert entregar() is False
    assert r.peticiones == []


def test_el_log_no_lleva_cuerpo_firma_ni_ruta(entorno, monkeypatch, caplog):
    r = receptor(monkeypatch, 500, 200)
    with caplog.at_level(logging.DEBUG, logger="app.core.webhooks"):
        assert entregar() is True
    firma = r.peticiones[0].headers["X-Firma"]
    texto = caplog.text
    assert "receptor.ejemplo.test" in texto  # el host si
    for prohibido in ("ruta-secreta", "token=abc", firma, firma.removeprefix("sha256="), SECRETO,
                      "ficticio.pdf", "folio_solicitud"):
        assert prohibido not in texto


def test_los_datos_se_envian_tal_cual_llegan(entorno, monkeypatch):
    # ADR-010 A5: quien llama los pasa ya enmascarados; core/webhooks no tiene mascara propia
    assert not hasattr(webhooks, "enmascarar_para_webhook")
    r = receptor(monkeypatch, 200)
    datos = resultado_ficticio()
    assert webhooks.entregar(URL, "documento.completado", "TST-2026-000001", datos) is True
    assert r.cuerpos()[0]["datos"] == datos.model_dump(mode="json")


# --- disparo desde el flujo real ---

@pytest.fixture
def sesion(entorno):
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add_all([
            Proceso(nombre="con_webhook", prefijo_folio="WHK", tipos_requeridos=["credencial_elector"],
                    tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=30, webhook_url=URL),
            Proceso(nombre="sin_webhook", prefijo_folio="SWH", tipos_requeridos=["credencial_elector"],
                    tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=30, webhook_url=None),
        ])
        script.crear_usuario(s, "revisor_ficticio", "revisor", "contrasena-ficticia")
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


def _subir_y_procesar(sesion, s3, proceso="con_webhook"):
    folio = expediente.crear_folio(sesion, proceso, None, "x").folio
    doc = ingestar(sesion, s3, folio, "credencial.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(doc.id)
    return folio, doc


def test_documento_completado_desde_el_procesamiento(sesion, s3, monkeypatch):
    r = receptor(monkeypatch, 200)
    folio, doc = _subir_y_procesar(sesion, s3)
    [cuerpo] = r.cuerpos()
    assert set(cuerpo) == CLAVES_DOCUMENTO
    assert (cuerpo["evento"], cuerpo["folio"], cuerpo["identificador_unico_documento"]) == \
        ("documento.completado", folio, str(doc.id))
    assert cuerpo["datos"]["estado_analisis"] == "completado"  # el mismo armado que GET /documentos/{id}
    assert cuerpo["datos"]["identificador_unico_documento"] == str(doc.id)


def test_documento_error_cuando_el_motor_devuelve_error(sesion, s3, monkeypatch):
    def analizar(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        return resultado.model_copy(update={"estado_analisis": EstadoAnalisis.error}), datos
    monkeypatch.setattr(procesamiento, "analizar", analizar)
    r = receptor(monkeypatch, 200)
    _subir_y_procesar(sesion, s3)
    assert [c["evento"] for c in r.cuerpos()] == ["documento.error"]


def test_documento_error_cuando_el_motor_falla(sesion, s3, monkeypatch):
    def analizar(contenido, **kwargs):
        raise RuntimeError("motor caido (ficticio)")
    monkeypatch.setattr(procesamiento, "analizar", analizar)
    r = receptor(monkeypatch, 200)
    _, doc = _subir_y_procesar(sesion, s3)
    [cuerpo] = r.cuerpos()
    assert (cuerpo["evento"], cuerpo["datos"]["estado_analisis"]) == ("documento.error", "error")


def test_fallos_del_webhook_no_cambian_el_documento(sesion, s3, monkeypatch):
    r = receptor(monkeypatch, 500)
    _, doc = _subir_y_procesar(sesion, s3)
    assert len(r.peticiones) == 4
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "completado"


def test_reproceso_al_confirmar_otro_tipo_tambien_avisa(sesion, s3, monkeypatch):
    r = receptor(monkeypatch, 200)
    _, doc = _subir_y_procesar(sesion, s3)
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    respuesta = cliente.post(f"/api/v1/documentos/{doc.id}/confirmar-clasificacion",
                             json={"tipo_documental": "pasaporte"})
    assert respuesta.status_code == 200
    assert [c["evento"] for c in r.cuerpos()] == ["documento.completado", "documento.completado"]


def test_folio_estado_cambiado_al_decidir(sesion, s3, monkeypatch):
    r = receptor(monkeypatch, 200)
    folio = expediente.crear_folio(sesion, "con_webhook", None, "x").folio
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    respuesta = cliente.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})
    assert respuesta.status_code == 200
    [cuerpo] = r.cuerpos()
    assert set(cuerpo) == CLAVES_FOLIO
    assert (cuerpo["evento"], cuerpo["folio"], cuerpo["datos"]["estado_general"]) == \
        ("folio.estado_cambiado", folio, "rechazado")


def test_un_fallo_del_webhook_no_cambia_la_decision(sesion, s3, monkeypatch):
    receptor(monkeypatch, 500)
    folio = expediente.crear_folio(sesion, "con_webhook", None, "x").folio
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    respuesta = cliente.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"})
    assert (respuesta.status_code, respuesta.json()["estado_general"]) == (200, "rechazado")


def test_sin_webhook_url_no_se_envia_nada(sesion, s3, monkeypatch):
    r = receptor(monkeypatch, 200)
    folio, _ = _subir_y_procesar(sesion, s3, proceso="sin_webhook")
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    assert cliente.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"}).status_code == 200
    assert r.peticiones == []
