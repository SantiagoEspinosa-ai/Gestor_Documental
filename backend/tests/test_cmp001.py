"""Tests de las comparaciones entre documentos (validacion) y de CMP-001 (expediente.recalcular_cmp001).

SQLite temporal + moto; motor falso con datos_extraidos INVENTADOS (nunca personas reales).
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
from app.core.modelos import AlertaBD, Proceso, Resultado
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.validacion import servicio as validacion
from app.modulos.validacion.comparaciones import DocumentoComparable, normalizar_texto

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
        script.crear_usuario(s, "revisor_ficticio", "revisor", "contrasena-ficticia")
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def datos(monkeypatch):
    """Motor falso: devuelve como datos_extraidos lo que diga este diccionario para el tipo declarado."""
    por_tipo: dict[str, dict] = {}

    def analizar(contenido, **kwargs):
        resultado, auditoria = motor_stub.procesar_documento(contenido, **kwargs)
        extraidos = por_tipo.get(kwargs["tipo_confirmado"] or kwargs["tipo_declarado"], {})
        return resultado.model_copy(update={"datos_extraidos": extraidos}), auditoria

    monkeypatch.setattr(procesamiento, "analizar", analizar)
    return por_tipo


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


def _subir_y_procesar(sesion, s3, folio, tipo, procesar=True):
    doc = ingestar(sesion, s3, folio, f"{tipo}_ficticio.pdf", f"%PDF-1.4 {tipo}".encode(), tipo, "x")
    if procesar:
        procesamiento.procesar(doc.id)
    return doc


def _cmp001(sesion, folio) -> list[AlertaBD]:
    sesion.expire_all()
    return sesion.scalars(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "CMP-001")
                          .order_by(AlertaBD.campo)).all()


def _por_campo(sesion, folio) -> dict:
    return {c.campo: c for c in expediente.comparaciones_actuales(sesion, folio)}


# --- normalizacion (logica pura) ---

def test_normalizacion_de_texto():
    assert normalizar_texto("  José   Pérez\tñandú ") == "JOSE PEREZ NANDU"


def test_comparar_une_los_dos_sentidos_y_compara_fechas():
    fichas = {"a": {"comparaciones": {"b": ["nombre"]}, "campos": {"fecha": {"tipo": "fecha"}}},
              "b": {"comparaciones": {"a": ["fecha"]}, "campos": {"fecha": {"tipo": "fecha"}}}}
    docs = [DocumentoComparable("1", "a", {"nombre": "Ana", "fecha": "1990-01-15"}),
            DocumentoComparable("2", "b", {"nombre": "ANA", "fecha": "15/01/1990"})]
    resultado = {c.campo: c.coincide for c in validacion.comparar(docs, fichas)}
    assert resultado == {"fecha": True, "nombre": True}


# --- en el folio ---

def test_mismo_nombre_con_otra_mayuscula_y_acento_coincide(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"nombre_completo": "Ana María Ejemplo", "fecha_nacimiento": "1990-01-15"}
    datos["pasaporte"] = {"nombre_completo": "ANA MARIA  EJEMPLO", "fecha_nacimiento": "1990-01-15"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    _subir_y_procesar(sesion, s3, folio, "pasaporte")
    comparaciones = _por_campo(sesion, folio)
    assert comparaciones["nombre_completo"].coincide is True
    assert comparaciones["fecha_nacimiento"].coincide is True
    assert _cmp001(sesion, folio) == []


def test_domicilio_distinto_genera_cmp001_sin_valores(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"domicilio": "Calle Ficticia 123, Ciudad Ejemplo"}
    datos["comprobante_domicilio"] = {"domicilio": "Avenida Inventada 456, Ciudad Ejemplo"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    _subir_y_procesar(sesion, s3, folio, "comprobante_domicilio")

    alertas = _cmp001(sesion, folio)
    assert [(a.campo, a.severidad, a.documento_id) for a in alertas] == [("domicilio", "critica", None)]
    assert alertas[0].mensaje == "Los documentos no coinciden en domicilio"
    assert "Ficticia" not in alertas[0].mensaje and "Inventada" not in alertas[0].mensaje

    token = crear_token("revisor_ficticio", "revisor")[0]
    cliente = TestClient(app)
    expediente_api = cliente.get(f"/api/v1/folios/{folio}", headers={"Authorization": f"Bearer {token}"}).json()
    assert {a["codigo"] for a in expediente_api["alertas_expediente"]} == {"CMP-001"}  # EXP-001 ya resueltas
    comparacion = next(c for c in expediente_api["comparaciones"] if c["campo"] == "domicilio")
    assert comparacion["coincide"] is False and len(comparacion["valores"]) == 2
    # CMP-001 es critica, no bloqueante: no cuenta en n_bloqueantes_sin_resolver
    lista = cliente.get("/api/v1/folios", headers={"Authorization": f"Bearer {token}"}).json()
    assert lista["elementos"][0]["n_bloqueantes_sin_resolver"] == 0


def test_cmp001_revisada_se_conserva_sin_duplicar(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"domicilio": "Calle Ficticia 123"}
    datos["comprobante_domicilio"] = {"domicilio": "Avenida Inventada 456"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    _subir_y_procesar(sesion, s3, folio, "comprobante_domicilio")
    alerta = _cmp001(sesion, folio)[0]
    alerta.aplica = False
    sesion.commit()

    expediente.recalcular_cmp001(sesion, folio)
    expediente.recalcular_cmp001(sesion, folio)
    sesion.commit()
    alertas = _cmp001(sesion, folio)
    assert [(a.id, a.aplica) for a in alertas] == [(alerta.id, False)]


def test_corregir_el_dato_quita_la_cmp001_sin_revisar(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"domicilio": "Calle Ficticia 123"}
    datos["comprobante_domicilio"] = {"domicilio": "Avenida Inventada 456"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    comprobante = _subir_y_procesar(sesion, s3, folio, "comprobante_domicilio")
    assert len(_cmp001(sesion, folio)) == 1

    fila = sesion.scalar(select(Resultado).where(Resultado.documento_id == comprobante.id))
    fila.json = {**fila.json, "datos_extraidos": {"domicilio": "calle ficticia  123"}}
    expediente.recalcular_cmp001(sesion, folio)
    sesion.commit()
    assert _cmp001(sesion, folio) == []


def test_los_vacios_no_participan(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"nombre_completo": "Ana Ejemplo", "domicilio": None}
    datos["pasaporte"] = {"nombre_completo": None}
    datos["comprobante_domicilio"] = {"domicilio": ""}
    for tipo in ("credencial_elector", "pasaporte", "comprobante_domicilio"):
        _subir_y_procesar(sesion, s3, folio, tipo)
    assert _por_campo(sesion, folio) == {}
    assert _cmp001(sesion, folio) == []


def test_un_documento_pendiente_no_cuenta(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"domicilio": "Calle Ficticia 123"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    _subir_y_procesar(sesion, s3, folio, "comprobante_domicilio", procesar=False)  # pendiente
    expediente.recalcular_cmp001(sesion, folio)
    sesion.commit()
    assert "domicilio" not in _por_campo(sesion, folio)
    assert _cmp001(sesion, folio) == []


def test_fechas_en_dos_formatos_coinciden(sesion, s3, folio, datos):
    datos["credencial_elector"] = {"fecha_nacimiento": "1990-01-15"}
    datos["pasaporte"] = {"fecha_nacimiento": "15/01/1990"}
    _subir_y_procesar(sesion, s3, folio, "credencial_elector")
    _subir_y_procesar(sesion, s3, folio, "pasaporte")
    assert _por_campo(sesion, folio)["fecha_nacimiento"].coincide is True
    assert _cmp001(sesion, folio) == []
