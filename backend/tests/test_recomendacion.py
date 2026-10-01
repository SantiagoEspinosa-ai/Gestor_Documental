"""Tests de la recomendacion global (expediente.recomendacion y su uso en la API). Datos ficticios."""
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
from app.modulos.expediente.recomendacion import DocumentoParaRecomendar, calcular_recomendacion_global
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.schemas.resultado import Alerta, EstadoAnalisis, Recomendacion

FICHAS = {"credencial_elector": {"confianza_minima_clasificacion": 0.85, "confianza_minima_campo": 0.80}}
APROBAR, REVISION = Recomendacion.aprobar, Recomendacion.revision_manual


def _doc(estado=EstadoAnalisis.completado, tipo="credencial_elector", clasificacion=0.95, campos=None):
    return DocumentoParaRecomendar(estado=estado, tipo=tipo, confianza_clasificacion=clasificacion,
                                   confianza_por_campo=campos if campos is not None else {"nombre_completo": 0.9})


def _alerta(severidad: str, aplica: bool | None = None) -> Alerta:
    return Alerta(codigo="X-001", mensaje="ficticia", severidad=severidad, confianza=1.0, aplica=aplica)


# --- funcion pura ---

@pytest.mark.parametrize("documentos", [
    [],                                                      # a) sin documentos
    [_doc(), _doc(estado=EstadoAnalisis.pendiente)],         # a) uno pendiente
    [_doc(estado=EstadoAnalisis.procesando)],                # a) uno procesando
    [_doc(estado=EstadoAnalisis.error)],                     # a) uno en error
])
def test_regla_a_documentos_no_completados(documentos):
    assert calcular_recomendacion_global(documentos, [], FICHAS) == REVISION


@pytest.mark.parametrize("severidad,aplica,esperado", [
    ("bloqueante", None, REVISION),   # b) sin revisar
    ("bloqueante", True, REVISION),   # b) confirmada
    ("critica", None, REVISION),
    ("critica", True, REVISION),
    ("critica", False, APROBAR),      # decision del usuario: falso positivo no cuenta
    ("bloqueante", False, APROBAR),
    ("preventiva", None, APROBAR),    # no cuentan nunca
    ("informativa", True, APROBAR),
])
def test_regla_b_alertas(severidad, aplica, esperado):
    assert calcular_recomendacion_global([_doc()], [_alerta(severidad, aplica)], FICHAS) == esperado


@pytest.mark.parametrize("documento", [
    _doc(clasificacion=0.80),                       # c) clasificacion bajo el minimo (0.85)
    _doc(clasificacion=None),                       # c) sin confianza de clasificacion
    _doc(campos={"nombre_completo": 0.79}),         # c) un campo bajo el minimo (0.80)
    _doc(tipo="tipo_sin_ficha"),                    # c) sin ficha para su tipo
    _doc(tipo=None),
])
def test_regla_c_confianzas_y_ficha(documento):
    assert calcular_recomendacion_global([documento], [], FICHAS) == REVISION


def test_regla_d_aprobar_y_campo_corregido_vale():
    assert calcular_recomendacion_global([_doc(clasificacion=0.85, campos={"a": 0.80, "corregido": 1.0})],
                                         [_alerta("preventiva")], FICHAS) == APROBAR


@pytest.mark.parametrize("documentos,alertas", [
    ([], [_alerta("bloqueante", True)]),
    ([_doc(estado=EstadoAnalisis.error)], [_alerta("critica")]),
    ([_doc(clasificacion=0.1)], [_alerta("bloqueante", True), _alerta("critica", True)]),
    ([_doc()], []),
])
def test_nunca_rechazar(documentos, alertas):
    assert calcular_recomendacion_global(documentos, alertas, FICHAS) != Recomendacion.rechazar


# --- en la API ---

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


def _recomendaciones(cliente, folio) -> tuple[str, str]:
    expediente_api = cliente.get(f"/api/v1/folios/{folio}").json()
    elemento = next(e for e in cliente.get("/api/v1/folios").json()["elementos"] if e["folio"] == folio)
    return expediente_api["recomendacion_global"], elemento["recomendacion_global"]


def _motor_seguro(monkeypatch, alertas=()):
    """Motor falso: confianzas altas y el mismo domicilio (inventado) en credencial y comprobante."""
    def analizar(contenido, **kwargs):
        resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
        return resultado.model_copy(update={
            "confianza_clasificacion": 0.99, "datos_extraidos": {"domicilio": "Calle Ficticia 123"},
            "nivel_confianza_por_campo": {"domicilio": 0.95}, "alertas_encontradas": list(alertas)}), datos
    monkeypatch.setattr(procesamiento, "analizar", analizar)


def _folio_completo(sesion, s3):
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    for tipo in ("credencial_elector", "comprobante_domicilio"):
        doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", f"%PDF-1.4 {tipo}".encode(), tipo, "x")
        procesamiento.procesar(doc.id)
    return folio


def test_folio_nuevo_da_revision_manual(cliente, sesion):
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio  # con EXP-001 y sin documentos
    assert _recomendaciones(cliente, folio) == ("revision_manual", "revision_manual")


def test_folio_completo_y_limpio_da_aprobar(cliente, sesion, s3, monkeypatch):
    _motor_seguro(monkeypatch)
    folio = _folio_completo(sesion, s3)
    assert _recomendaciones(cliente, folio) == ("aprobar", "aprobar")


def test_critica_marcada_como_falso_positivo_sigue_aprobar(cliente, sesion, s3, monkeypatch):
    critica = Alerta(codigo="VAL-001", mensaje="ficticia", severidad="critica", confianza=1.0,
                     campo="domicilio")
    _motor_seguro(monkeypatch, alertas=[critica])
    folio = _folio_completo(sesion, s3)
    assert _recomendaciones(cliente, folio) == ("revision_manual", "revision_manual")

    for alerta in sesion.scalars(select(AlertaBD).where(AlertaBD.folio == folio, AlertaBD.codigo == "VAL-001")):
        alerta.aplica = False
    sesion.commit()
    assert _recomendaciones(cliente, folio) == ("aprobar", "aprobar")
