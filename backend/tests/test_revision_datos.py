"""Tests de E2.6b (1): PATCH /documentos/{id}/datos (ADR-006 2.4). Datos INVENTADOS, nunca reales."""
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
from app.core.modelos import AlertaBD, Auditoria, Correccion, Documento, Folio, Proceso
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

# Lo que "extrae" el motor falso para cada tipo (inventado)
DATOS = {
    "credencial_elector": ({"nombre_completo": "Ana Ejemplo", "domicilio": "Calle Ficticia 123"},
                           {"nombre_completo": 0.95, "domicilio": 0.95}),
    "comprobante_domicilio": ({"domicilio": "Calle Ficticia 123"}, {"domicilio": 0.95}),
}


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
def motor(monkeypatch):
    """Motor falso: datos y confianzas de DATOS (modificable por test), clasificacion 0.99."""
    datos = {k: (dict(v[0]), dict(v[1])) for k, v in DATOS.items()}

    def analizar(contenido, **kwargs):
        resultado, auditoria = motor_stub.procesar_documento(contenido, **kwargs)
        extraidos, confianzas = datos.get(kwargs["tipo_confirmado"] or kwargs["tipo_declarado"], ({}, {}))
        return resultado.model_copy(update={"confianza_clasificacion": 0.99, "datos_extraidos": extraidos,
                                            "nivel_confianza_por_campo": confianzas}), auditoria

    monkeypatch.setattr(procesamiento, "analizar", analizar)
    return datos


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


def _patch(cliente, doc_id, cuerpo, rol="revisor"):
    return cliente.patch(f"/api/v1/documentos/{doc_id}/datos", json=cuerpo, headers=_cab(rol))


def test_campo_corregido(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    r = _patch(cliente, doc.id, {"nombre_completo": "Ana Maria Ejemplo"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["datos_extraidos"]["nombre_completo"] == "Ana Maria Ejemplo"
    assert cuerpo["nivel_confianza_por_campo"]["nombre_completo"] == 1.0
    assert cuerpo["evidencia_por_campo"]["nombre_completo"] == "correccion_revisor"
    assert cuerpo["datos_extraidos"]["domicilio"] == "Calle Ficticia 123"  # el resto no cambia
    [correccion] = cuerpo["correcciones"]
    assert (correccion["campo"], correccion["valor_anterior"], correccion["valor_nuevo"], correccion["usuario"]) == \
        ("nombre_completo", "Ana Ejemplo", "Ana Maria Ejemplo", "revisor_ficticio")
    # el expediente lo ve igual
    en_expediente = cliente.get(f"/api/v1/folios/{folio}", headers=_cab()).json()["documentos"][0]
    assert en_expediente["datos_extraidos"]["nombre_completo"] == "Ana Maria Ejemplo"
    assert sesion.scalar(select(Correccion.version_resultado)) == 1


def test_dos_correcciones_del_mismo_campo(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    _patch(cliente, doc.id, {"nombre_completo": "Primer Valor"})
    cuerpo = _patch(cliente, doc.id, {"nombre_completo": "Segundo Valor"}).json()
    assert cuerpo["datos_extraidos"]["nombre_completo"] == "Segundo Valor"
    assert [(c["valor_anterior"], c["valor_nuevo"]) for c in cuerpo["correcciones"]] == \
        [("Ana Ejemplo", "Primer Valor"), ("Primer Valor", "Segundo Valor")]


def test_la_auditoria_no_lleva_valores(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    _patch(cliente, doc.id, {"nombre_completo": "Valor Secreto Ficticio", "domicilio": "Otra Calle 9"})
    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "dato_corregido"))
    assert (registro.usuario, registro.folio, registro.documento_id) == ("revisor_ficticio", folio, doc.id)
    assert registro.detalle == {"campos": ["domicilio", "nombre_completo"]}
    assert "Secreto" not in str(registro.detalle) and "Otra Calle" not in str(registro.detalle)


def test_corregir_el_domicilio_quita_la_cmp001(cliente, sesion, s3, folio, motor):
    motor["comprobante_domicilio"][0]["domicilio"] = "Avenida Inventada 456"
    _subir(sesion, s3, folio)
    comprobante = _subir(sesion, s3, folio, tipo="comprobante_domicilio")
    assert sesion.scalar(select(AlertaBD).where(AlertaBD.codigo == "CMP-001")) is not None
    assert _patch(cliente, comprobante.id, {"domicilio": "calle ficticia  123"}).status_code == 200
    sesion.expire_all()
    assert sesion.scalar(select(AlertaBD).where(AlertaBD.codigo == "CMP-001")) is None
    comparacion = cliente.get(f"/api/v1/folios/{folio}", headers=_cab()).json()["comparaciones"]
    assert [(c["campo"], c["coincide"]) for c in comparacion] == [("domicilio", True)]


def test_corregir_una_confianza_baja_lleva_a_aprobar(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][1]["nombre_completo"] = 0.5  # por debajo del minimo (0.80)
    doc = _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, tipo="comprobante_domicilio")
    assert cliente.get(f"/api/v1/folios/{folio}", headers=_cab()).json()["recomendacion_global"] == "revision_manual"
    _patch(cliente, doc.id, {"nombre_completo": "Ana Ejemplo"})
    assert cliente.get(f"/api/v1/folios/{folio}", headers=_cab()).json()["recomendacion_global"] == "aprobar"


@pytest.mark.parametrize("cuerpo,mensaje", [
    ({"campo_inventado": "x"}, "campo desconocido: campo_inventado"),
    ({"fecha_nacimiento": "31/12/1990"}, "fecha_nacimiento"),
    ({"curp": "NO-CUMPLE-PATRON"}, "curp"),
    ({"vigencia": "20X9"}, "vigencia"),
    ({"nombre_completo": "   "}, "nombre_completo"),
    ({"nombre_completo": 12345}, "nombre_completo"),
    ({}, "No hay campos"),
])
def test_422_sin_el_valor_en_el_mensaje(cliente, sesion, s3, folio, motor, cuerpo, mensaje):
    doc = _subir(sesion, s3, folio)
    r = _patch(cliente, doc.id, cuerpo)
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")
    assert mensaje in r.json()["mensaje"]
    for valor in cuerpo.values():
        if str(valor).strip():
            assert str(valor) not in r.json()["mensaje"]
    assert sesion.scalar(select(Correccion)) is None


def test_409(cliente, sesion, s3, folio, motor):
    pendiente = _subir(sesion, s3, folio, tipo="comprobante_domicilio", procesar=False)
    r = _patch(cliente, pendiente.id, {"domicilio": "Calle 1"})
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")

    sesion.get(Documento, pendiente.id).estado_analisis = "error"
    sesion.commit()
    r = _patch(cliente, pendiente.id, {"domicilio": "Calle 1"})
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_CON_ERROR")
    assert r.json()["mensaje"] == "El documento no se pudo procesar; vuelve a subirlo"

    completado = _subir(sesion, s3, folio)
    sesion.get(Folio, folio).estado_general = "rechazado"
    sesion.commit()
    r = _patch(cliente, completado.id, {"nombre_completo": "Ana"})
    assert (r.status_code, r.json()["codigo"]) == (409, "FOLIO_CERRADO")


def test_404_403_401(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    r = _patch(cliente, uuid.uuid4(), {"nombre_completo": "Ana"})
    assert (r.status_code, r.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")
    for rol in ("admin", "integrador"):
        assert _patch(cliente, doc.id, {"nombre_completo": "Ana"}, rol=rol).status_code == 403
    assert cliente.patch(f"/api/v1/documentos/{doc.id}/datos", json={"nombre_completo": "Ana"}).status_code == 401


def test_se_valida_con_la_ficha_usada_para_extraer(cliente, sesion, s3, folio, monkeypatch):
    # Declarado pasaporte, detectado credencial_elector (CLS-001 pendiente): se extrajo con la ficha
    # del declarado (ADR-006 2.5), asi que se corrigen campos de pasaporte, no de credencial
    def detecta_credencial(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        cls = Alerta(codigo="CLS-001", mensaje="ficticia", severidad="critica", confianza=0.9)
        return resultado.model_copy(update={"tipo_documental_detectado": "credencial_elector",
                                            "confianza_clasificacion": 0.99,
                                            "alertas_encontradas": [cls]}), datos

    monkeypatch.setattr(procesamiento, "analizar", detecta_credencial)
    doc = _subir(sesion, s3, folio, tipo="pasaporte")
    assert _patch(cliente, doc.id, {"numero_pasaporte": "ZX0000001"}).status_code == 200
    r = _patch(cliente, doc.id, {"curp": "AEPA900101MDFXXX01"})
    assert (r.status_code, r.json()["mensaje"]) == (422, "campo desconocido: curp")


@pytest.mark.parametrize("aplica,sigue", [(True, False), (None, False), (False, True)])
def test_cmp001_al_corregir_solo_sobrevive_el_falso_positivo(cliente, sesion, s3, folio, motor, aplica, sigue):
    motor["comprobante_domicilio"][0]["domicilio"] = "Avenida Inventada 456"
    _subir(sesion, s3, folio)
    comprobante = _subir(sesion, s3, folio, tipo="comprobante_domicilio")
    cmp_id = sesion.scalar(select(AlertaBD.id).where(AlertaBD.codigo == "CMP-001"))
    if aplica is not None:
        assert cliente.post(f"/api/v1/folios/{folio}/alertas/{cmp_id}/resolver", json={"aplica": aplica},
                            headers=_cab()).status_code == 200
    _patch(cliente, comprobante.id, {"domicilio": "Calle Ficticia 123"})
    sesion.expire_all()
    assert (sesion.get(AlertaBD, cmp_id) is not None) is sigue
