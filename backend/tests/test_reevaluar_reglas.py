"""Tests de D3: al corregir datos (PATCH /documentos/{id}/datos) se reevaluan las reglas del documento con
validacion.evaluar_reglas real (PERSONA_2). SQLite temporal + moto; motor falso con alertas fijadas por test.
Datos ficticios."""
import importlib.util
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import AlertaBD, Correccion, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.validacion import servicio as validacion
from app.schemas.resultado import Alerta

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
# Credencial ficticia completa y coherente (CURP con la fecha de nacimiento, vigencia futura)
CREDENCIAL = {"nombre_completo": "Ana Ejemplo", "curp": "EJAA900101MDFJNN09", "clave_elector": "EJAANN90010109M100",
              "fecha_nacimiento": "1990-01-01", "domicilio": "Calle Ficticia 123", "vigencia": 2030}
COMPROBANTE = {"nombre_titular": "Ana Ejemplo", "domicilio": "Avenida Inventada 9", "proveedor": "Luz Ficticia",
               "fecha_emision": "2026-09-01"}

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _alerta(codigo, campo=None, severidad="critica"):
    return Alerta(codigo=codigo, mensaje=f"{codigo} ficticia", severidad=severidad, confianza=1.0, campo=campo)


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": SECRETO, "S3_BUCKET": BUCKET,
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
def motor(monkeypatch):
    """Motor falso: por tipo declarado, (datos, confianzas, alertas). Cada test lo ajusta antes de subir."""
    por_tipo = {"credencial_elector": [dict(CREDENCIAL), {c: 0.95 for c in CREDENCIAL}, []],
                "comprobante_domicilio": [dict(COMPROBANTE), {c: 0.95 for c in COMPROBANTE}, []]}

    def analizar(contenido, **kwargs):
        resultado, auditoria = motor_stub.procesar_documento(contenido, **kwargs)
        datos, confianzas, alertas = por_tipo[kwargs["tipo_declarado"]]
        return resultado.model_copy(update={"confianza_clasificacion": 0.99, "datos_extraidos": datos,
                                            "nivel_confianza_por_campo": confianzas,
                                            "alertas_encontradas": list(alertas)}), auditoria
    monkeypatch.setattr(procesamiento, "analizar", analizar)
    return por_tipo


@pytest.fixture
def cliente(sesion):
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {crear_token('revisor_ficticio', 'revisor')[0]}"
    return c


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "x").folio


def _subir(sesion, s3, folio, tipo="credencial_elector", contenido=None):
    doc = ingestar(sesion, s3, folio, f"{tipo}.pdf", contenido or f"%PDF-1.4 {tipo}".encode(), tipo, "x")
    procesamiento.procesar(doc.id)
    return doc


def _patch(cliente, doc_id, cuerpo):
    return cliente.patch(f"/api/v1/documentos/{doc_id}/datos", json=cuerpo)


def _alertas(cliente, doc_id) -> list[tuple]:
    return sorted((a["codigo"], a["campo"], a["aplica"])
                  for a in cliente.get(f"/api/v1/documentos/{doc_id}").json()["alertas_encontradas"])


def _resolver(cliente, doc_id, codigo, campo, aplica):
    alerta = next(a for a in cliente.get(f"/api/v1/documentos/{doc_id}").json()["alertas_encontradas"]
                  if (a["codigo"], a["campo"]) == (codigo, campo))
    r = cliente.post(f"/api/v1/documentos/{doc_id}/alertas/{alerta['id']}/resolver", json={"aplica": aplica})
    assert r.status_code == 200


def test_rellenar_un_obligatorio_vacio_quita_su_val001(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][0]["curp"] = None
    motor["credencial_elector"][2].append(_alerta("VAL-001", "curp"))
    doc = _subir(sesion, s3, folio)
    assert ("VAL-001", "curp", None) in _alertas(cliente, doc.id)
    assert _patch(cliente, doc.id, {"curp": "EJAA900101MDFJNN09"}).status_code == 200
    assert not [a for a in _alertas(cliente, doc.id) if a[0] == "VAL-001"]


def test_un_val001_marcado_falso_positivo_se_conserva(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][0]["vigencia"] = None
    motor["credencial_elector"][2].append(_alerta("VAL-001", "vigencia"))
    doc = _subir(sesion, s3, folio)
    _resolver(cliente, doc.id, "VAL-001", "vigencia", False)
    assert _patch(cliente, doc.id, {"nombre_completo": "Ana Maria Ejemplo"}).status_code == 200
    val001 = [a for a in _alertas(cliente, doc.id) if a[0] == "VAL-001"]
    assert val001 == [("VAL-001", "vigencia", False)]  # se conserva y no se duplica


def test_una_correccion_que_incumple_una_regla_anade_su_reg(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, "comprobante_domicilio")
    assert not [a for a in _alertas(cliente, doc.id) if a[0].startswith("REG-")]
    assert _patch(cliente, doc.id, {"vigencia": 2020}).status_code == 200  # credencial vencida
    assert ("REG-vigencia_documento", "vigencia", None) in _alertas(cliente, doc.id)
    documento = cliente.get(f"/api/v1/documentos/{doc.id}").json()
    assert "vigencia_documento" in documento["reglas_cumplidas_e_incumplidas"]["incumplidas"]
    assert "vigencia_documento" not in documento["reglas_cumplidas_e_incumplidas"]["cumplidas"]


def test_bloqueantes_y_recomendacion_se_recalculan(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, "comprobante_domicilio")
    _resolver_cmp = [a for a in cliente.get(f"/api/v1/folios/{folio}").json()["alertas_expediente"]]
    for a in _resolver_cmp:  # domicilios distintos (CMP-001): falso positivo para que no frene
        cliente.post(f"/api/v1/folios/{folio}/alertas/{a['id']}/resolver", json={"aplica": False})

    def resumen():
        elemento = next(e for e in cliente.get("/api/v1/folios").json()["elementos"] if e["folio"] == folio)
        return elemento["n_bloqueantes_sin_resolver"], elemento["recomendacion_global"]

    assert resumen() == (0, "aprobar")
    _patch(cliente, doc.id, {"vigencia": 2020})  # REG-vigencia_documento es bloqueante
    assert resumen() == (1, "revision_manual")
    _patch(cliente, doc.id, {"vigencia": 2031})  # vuelve a cumplirse: la REG sin revisar desaparece
    assert resumen() == (0, "aprobar")


def test_corregir_un_campo_con_val003_sin_revisar_la_borra_y_la_revisada_se_conserva(cliente, sesion, s3, folio,
                                                                                    motor):
    motor["credencial_elector"][2].extend([_alerta("VAL-003", "nombre_completo", "informativa"),
                                           _alerta("VAL-003", "domicilio", "informativa")])
    doc = _subir(sesion, s3, folio)
    _resolver(cliente, doc.id, "VAL-003", "domicilio", True)  # revisada
    assert _patch(cliente, doc.id, {"nombre_completo": "Ana Maria Ejemplo", "domicilio": "Calle Ficticia 124"}
                  ).status_code == 200
    val003 = [a for a in _alertas(cliente, doc.id) if a[0] == "VAL-003"]
    assert val003 == [("VAL-003", "domicilio", True)]


def test_val002_desaparece_en_un_campo_corregido(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][1]["nombre_completo"] = 0.5
    motor["credencial_elector"][2].append(_alerta("VAL-002", "nombre_completo", "preventiva"))
    doc = _subir(sesion, s3, folio)
    assert _patch(cliente, doc.id, {"nombre_completo": "Ana Ejemplo"}).status_code == 200
    assert not [a for a in _alertas(cliente, doc.id) if a[0] == "VAL-002"]


def test_cls_dup_exp_y_cmp_intactas(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][2].append(_alerta("CLS-001", None))
    doc = _subir(sesion, s3, folio)
    _subir(sesion, s3, folio, contenido=b"%PDF-1.4 credencial_elector")  # mismo SHA-256: DUP-001 en el segundo
    otro = _subir(sesion, s3, folio, "comprobante_domicilio")  # domicilio distinto: CMP-001
    sesion.expire_all()
    antes = sorted(sesion.scalars(select(AlertaBD.id).where(
        AlertaBD.folio == folio, AlertaBD.codigo.in_(["CLS-001", "DUP-001", "EXP-001", "CMP-001"]))))
    assert antes
    assert _patch(cliente, doc.id, {"nombre_completo": "Ana Maria Ejemplo"}).status_code == 200
    assert _patch(cliente, otro.id, {"proveedor": "Agua Ficticia"}).status_code == 200
    sesion.expire_all()
    despues = sorted(sesion.scalars(select(AlertaBD.id).where(
        AlertaBD.folio == folio, AlertaBD.codigo.in_(["CLS-001", "DUP-001", "EXP-001", "CMP-001"]))))
    assert despues == antes


def test_si_evaluar_reglas_falla_no_se_aplica_nada(cliente, sesion, s3, folio, motor, monkeypatch, caplog):
    motor["credencial_elector"][2].append(_alerta("VAL-002", "nombre_completo", "preventiva"))
    doc = _subir(sesion, s3, folio)
    antes = _alertas(cliente, doc.id)

    def rota(*args, **kwargs):
        raise ValueError("ficha invalida (ficticia)")
    monkeypatch.setattr(validacion, "evaluar_reglas", rota)
    r = _patch(cliente, doc.id, {"nombre_completo": "Nombre Que No Debe Salir"})
    assert (r.status_code, r.json()["codigo"]) == (500, "ERROR_INTERNO")
    sesion.expire_all()
    assert sesion.scalar(select(func.count()).select_from(Correccion)) == 0  # ni la correccion
    assert _alertas(cliente, doc.id) == antes  # ni las alertas
    assert cliente.get(f"/api/v1/documentos/{doc.id}").json()["datos_extraidos"]["nombre_completo"] == "Ana Ejemplo"
    assert "Nombre Que No Debe Salir" not in caplog.text


# --- D3: recomendacion DEL DOCUMENTO recalculada tras corregir (sugerido por PERSONA_2) ---

def _recomendacion(cliente, doc_id) -> str:
    return cliente.get(f"/api/v1/documentos/{doc_id}").json()["recomendacion"]


def test_rellenar_el_unico_obligatorio_vacio_pasa_el_documento_a_aprobar(cliente, sesion, s3, folio, motor):
    motor["credencial_elector"][0]["curp"] = None
    motor["credencial_elector"][2].append(_alerta("VAL-001", "curp"))
    doc = _subir(sesion, s3, folio)
    assert _recomendacion(cliente, doc.id) == "revision_manual"
    assert _patch(cliente, doc.id, {"curp": "EJAA900101MDFJNN09"}).status_code == 200
    assert _recomendacion(cliente, doc.id) == "aprobar"


def test_una_correccion_que_anade_una_reg_critica_lo_deja_en_revision(cliente, sesion, s3, folio, motor):
    doc = _subir(sesion, s3, folio)
    _patch(cliente, doc.id, {"nombre_completo": "Ana Maria Ejemplo"})
    assert _recomendacion(cliente, doc.id) == "aprobar"
    # CURP con formato valido pero que no coincide con la fecha de nacimiento: REG critica
    assert _patch(cliente, doc.id, {"curp": "EJAA910101MDFJNN09"}).status_code == 200
    assert ("REG-curp_coincide_nacimiento", "curp", None) in _alertas(cliente, doc.id)
    assert _recomendacion(cliente, doc.id) == "revision_manual"


@pytest.mark.parametrize("cuerpo", [{"vigencia": 2020}, {"curp": "EJAA910101MDFJNN09"}, {"nombre_completo": "Ana E"},
                                    {"fecha_nacimiento": "1991-01-01"}])
def test_nunca_recomienda_rechazar(cliente, sesion, s3, folio, motor, cuerpo):
    doc = _subir(sesion, s3, folio)
    assert _patch(cliente, doc.id, cuerpo).status_code == 200
    assert _recomendacion(cliente, doc.id) in ("aprobar", "revision_manual")


def test_si_recomendar_documento_falla_no_se_aplica_nada(cliente, sesion, s3, folio, motor, monkeypatch):
    doc = _subir(sesion, s3, folio)
    antes = cliente.get(f"/api/v1/documentos/{doc.id}").json()

    def rota(*args, **kwargs):
        raise ValueError("fallo ficticio")
    monkeypatch.setattr(validacion, "recomendar_documento", rota)
    r = _patch(cliente, doc.id, {"vigencia": 2020})
    assert (r.status_code, r.json()["codigo"]) == (500, "ERROR_INTERNO")
    despues = cliente.get(f"/api/v1/documentos/{doc.id}").json()
    assert (despues["datos_extraidos"], despues["alertas_encontradas"], despues["recomendacion"]) == \
        (antes["datos_extraidos"], antes["alertas_encontradas"], antes["recomendacion"])
