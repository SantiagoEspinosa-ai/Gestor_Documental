"""POST /documentos/{id}/retirar y /restaurar (ADR-013): roles, 409, efecto en el folio (EXP-001, CMP-001,
recomendacion, bloqueantes, DUP-001), motivo tapado, resumen.md y auditoria. SQLite temporal + moto con un
motor falso que devuelve los datos que diga cada test. Datos ficticios."""
import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
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
from app.core.modelos import AlertaBD, Auditoria, Documento, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.rag import memoria
from app.schemas.resultado import Alerta, Severidad

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
BUCKET = "bucket-de-test"
CURP = "XEXX010101HNEXXXA9"        # ficticia, la del documento
CURP_AJENA = "XAXX020202MDFYYYA5"  # ficticia, de nadie del folio

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

# Lo que devuelve el motor falso por nombre de fichero: (datos, alertas); "roto" lanza (documento en error)
SALIDAS: dict[str, tuple[dict, list[Alerta]]] = {}


def _analizar(contenido, **kwargs):
    if kwargs["nombre_archivo"].startswith("roto"):
        raise RuntimeError("motor caido (ficticio)")
    resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
    extraidos, alertas = SALIDAS.get(kwargs["nombre_archivo"], ({}, []))
    return resultado.model_copy(update={"datos_extraidos": extraidos, "alertas_encontradas": alertas,
                                        "nivel_confianza_por_campo": {c: 0.99 for c in extraidos}}), datos


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": SECRETO, "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO, "APP_ENV": "dev",
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    SALIDAS.clear()
    monkeypatch.setattr(procesamiento, "analizar", _analizar)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        s3 = AlmacenamientoS3(bucket=BUCKET, region="us-east-1", access_key="clave-ficticia", secret_key=SECRETO,
                              segundos_url=300)
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: s3)
        monkeypatch.setattr(expediente, "_almacenamiento", lambda: s3)
        Base.metadata.create_all(db.get_engine())
        with Session(db.get_engine()) as sesion:
            sesion.add(Proceso(nombre="onboarding", prefijo_folio="ONB",
                               tipos_requeridos=["credencial_elector", "comprobante_domicilio"],
                               tipos_opcionales=["pasaporte"], permitir_antecedentes=True,
                               caducidad_antecedentes_dias=365, webhook_url=None))
            for rol in ("admin", "revisor", "integrador"):
                script.crear_usuario(sesion, f"{rol}_ficticio", rol, "contrasena-ficticia")
            sesion.commit()
            yield sesion, s3
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


def _cliente(rol: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"})


def _subir(entorno, folio, nombre, tipo, datos=None, alertas=(), contenido=None):
    sesion, s3 = entorno
    SALIDAS[nombre] = (datos or {}, list(alertas))
    doc = ingestar(sesion, s3, folio, nombre, contenido or f"%PDF-1.4 {uuid.uuid4()}".encode(), tipo, "x")
    # Un segundo distinto por subida: SQLite guarda creado_en con resolucion de segundos y el orden importa (DUP)
    doc.creado_en = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc) + timedelta(seconds=len(SALIDAS))
    sesion.commit()
    procesamiento.procesar(doc.id)
    sesion.expire_all()
    return str(doc.id)


def _folio(entorno, domicilio_comprobante="Calle Ficticia 1"):
    """Folio con los dos requeridos completados; el domicilio coincide salvo que se diga otro."""
    folio = expediente.crear_folio(entorno[0], "onboarding", "CLI-000900", "x").folio
    credencial = _subir(entorno, folio, "credencial.pdf", "credencial_elector",
                        {"nombre_completo": "Ana Ejemplo", "curp": CURP, "domicilio": "Calle Ficticia 1"})
    comprobante = _subir(entorno, folio, "comprobante.pdf", "comprobante_domicilio",
                         {"nombre_titular": "Ana Ejemplo", "domicilio": domicilio_comprobante})
    return folio, credencial, comprobante


def _retirar(doc_id, motivo="Subido por error", rol="revisor"):
    return _cliente(rol).post(f"/api/v1/documentos/{doc_id}/retirar", json={"motivo": motivo})


def _restaurar(doc_id, rol="revisor"):
    return _cliente(rol).post(f"/api/v1/documentos/{doc_id}/restaurar")


def _expediente(folio):
    return _cliente("revisor").get(f"/api/v1/folios/{folio}").json()


def _codigos_expediente(folio):
    return sorted(a["codigo"] for a in _expediente(folio)["alertas_expediente"])


# --- retirar y restaurar ---

def test_retirar_y_restaurar_revisor(entorno):
    _, credencial, _ = _folio(entorno)
    r = _retirar(credencial)
    assert r.status_code == 200
    retirado = r.json()["retirado"]
    assert (retirado["por"], retirado["motivo"]) == ("revisor_ficticio", "Subido por error")
    for rol in ("revisor", "admin"):  # el admin consulta (el integrador solo ve sus folios, ADR-012)
        assert _cliente(rol).get(f"/api/v1/documentos/{credencial}").json()["retirado"] == retirado
    r = _restaurar(credencial)
    assert r.status_code == 200 and r.json()["retirado"] is None
    # Nada se borra: el documento y su original siguen
    sesion, s3 = entorno
    doc = sesion.get(Documento, uuid.UUID(credencial))
    assert doc is not None and s3.descargar(doc.ruta_s3)


@pytest.mark.parametrize("rol", ["admin", "integrador"])
def test_admin_e_integrador_403(entorno, rol):
    _, credencial, _ = _folio(entorno)
    for respuesta in (_retirar(credencial, rol=rol), _restaurar(credencial, rol=rol)):
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (403, "SIN_PERMISO")
    assert _retirar(credencial).status_code == 200
    respuesta = _restaurar(credencial, rol=rol)  # tampoco restaura uno retirado
    assert (respuesta.status_code, respuesta.json()["codigo"]) == (403, "SIN_PERMISO")


def test_409_ya_retirado_no_retirado_y_folio_cerrado(entorno):
    folio, credencial, comprobante = _folio(entorno)
    assert (_restaurar(credencial).json()["codigo"]) == "DOCUMENTO_NO_RETIRADO"
    assert _retirar(credencial).status_code == 200
    r = _retirar(credencial)
    assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_RETIRADO")
    assert _cliente("revisor").post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"}).status_code == 200
    for respuesta in (_retirar(comprobante), _restaurar(credencial)):
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (409, "FOLIO_CERRADO")


def test_409_en_proceso_y_en_error_si_se_puede_retirar(entorno):
    sesion, _ = entorno
    folio, credencial, _ = _folio(entorno)
    for estado in ("pendiente", "procesando"):
        sesion.get(Documento, uuid.UUID(credencial)).estado_analisis = estado
        sesion.commit()
        r = _retirar(credencial)
        assert (r.status_code, r.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")
    roto = _subir(entorno, folio, "roto.pdf", "pasaporte")
    assert _cliente("revisor").get(f"/api/v1/documentos/{roto}").json()["estado_analisis"] == "error"
    assert _retirar(roto).status_code == 200


@pytest.mark.parametrize("cuerpo", [{}, {"motivo": "ab"}, {"motivo": "x" * 201}, {"motivo": "valido", "extra": 1}])
def test_motivo_obligatorio_de_3_a_200_422(entorno, cuerpo):
    _, credencial, _ = _folio(entorno)
    r = _cliente("revisor").post(f"/api/v1/documentos/{credencial}/retirar", json=cuerpo)
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")


def test_404(entorno):
    for doc_id in (uuid.uuid4(), "no-es-un-uuid"):
        assert _retirar(doc_id).json()["codigo"] == "DOCUMENTO_NO_ENCONTRADO"
        assert _restaurar(doc_id).json()["codigo"] == "DOCUMENTO_NO_ENCONTRADO"


def test_sobre_un_retirado_no_se_revisa(entorno):
    sesion, _ = entorno
    _, credencial, _ = _folio(entorno)
    alerta = AlertaBD(folio=sesion.get(Documento, uuid.UUID(credencial)).folio, documento_id=uuid.UUID(credencial),
                      codigo="VAL-002", severidad="preventiva", confianza=0.5, mensaje="Confianza baja (ficticia)")
    sesion.add(alerta)
    sesion.commit()
    assert _retirar(credencial).status_code == 200
    revisor = _cliente("revisor")
    for respuesta in (
            revisor.patch(f"/api/v1/documentos/{credencial}/datos", json={"nombre_completo": "Otra Ejemplo"}),
            revisor.post(f"/api/v1/documentos/{credencial}/confirmar-clasificacion",
                         json={"tipo_documental": "credencial_elector"}),
            revisor.post(f"/api/v1/documentos/{credencial}/alertas/{alerta.id}/resolver", json={"aplica": False})):
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (409, "DOCUMENTO_RETIRADO")
    # Consultar si
    assert revisor.get(f"/api/v1/documentos/{credencial}").status_code == 200
    assert revisor.post(f"/api/v1/documentos/{credencial}/revelar", json={"campo": "curp"}).status_code == 200


# --- efecto en el folio ---

def test_exp001_reaparece_al_retirar_el_unico_requerido_y_se_va_al_restaurar(entorno):
    folio, _, comprobante = _folio(entorno)
    assert "EXP-001" not in _codigos_expediente(folio)
    _retirar(comprobante)
    exp001 = [a for a in _expediente(folio)["alertas_expediente"] if a["codigo"] == "EXP-001"]
    assert [a["campo"] for a in exp001] == ["comprobante_domicilio"]
    _restaurar(comprobante)
    assert "EXP-001" not in _codigos_expediente(folio)


def test_cmp001_desaparece_al_retirar_el_que_no_coincidia(entorno):
    folio, _, comprobante = _folio(entorno, domicilio_comprobante="Avenida Inventada 99")
    assert "CMP-001" in _codigos_expediente(folio)
    _retirar(comprobante)
    expediente_ = _expediente(folio)
    assert "CMP-001" not in [a["codigo"] for a in expediente_["alertas_expediente"]]
    assert expediente_["comparaciones"] == []  # el retirado no se compara
    _restaurar(comprobante)
    assert "CMP-001" in _codigos_expediente(folio)


def test_recomendacion_global_y_bloqueantes_sin_el_retirado(entorno):
    folio, _, _ = _folio(entorno)
    assert _expediente(folio)["recomendacion_global"] == "aprobar"
    bloqueante = Alerta(codigo="REG-vigencia_documento", severidad=Severidad.bloqueante, mensaje="Vencida (ficticia)",
                        campo="vigencia", confianza=1.0)
    otra = _subir(entorno, folio, "otra.pdf", "credencial_elector",
                  {"nombre_completo": "Ana Ejemplo", "domicilio": "Calle Ficticia 1"}, [bloqueante])
    roto = _subir(entorno, folio, "roto.pdf", "pasaporte")

    def resumen_de_la_lista():
        [elemento] = _cliente("revisor").get("/api/v1/folios").json()["elementos"]
        return elemento["recomendacion_global"], elemento["n_bloqueantes_sin_resolver"], elemento["n_documentos"]

    assert _expediente(folio)["recomendacion_global"] == "revision_manual"
    assert resumen_de_la_lista() == ("revision_manual", 1, 4)
    _retirar(roto)
    assert resumen_de_la_lista() == ("revision_manual", 1, 4)  # sigue la bloqueante
    _retirar(otra)
    assert resumen_de_la_lista() == ("aprobar", 0, 4)  # n_documentos cuenta tambien los retirados
    assert _expediente(folio)["recomendacion_global"] == "aprobar"
    # Y se puede aprobar: la bloqueante del retirado no cuenta
    r = _cliente("revisor").post(f"/api/v1/folios/{folio}/decision", json={"decision": "aprobar"})
    assert r.status_code == 200


def test_dup001_un_retirado_no_hace_duplicado_a_otro(entorno):
    folio, _, _ = _folio(entorno)
    mismo = b"%PDF-1.4 mismo contenido ficticio"
    primero = _subir(entorno, folio, "p1.pdf", "pasaporte", contenido=mismo)
    segundo = _subir(entorno, folio, "p2.pdf", "pasaporte", contenido=mismo)

    def dups(doc_id):
        return [a for a in _cliente("revisor").get(f"/api/v1/documentos/{doc_id}").json()["alertas_encontradas"]
                if a["codigo"] == "DUP-001"]

    assert dups(primero) == [] and len(dups(segundo)) == 1
    _retirar(primero)
    assert dups(segundo) == []  # el original retirado ya no lo hace duplicado
    tercero = _subir(entorno, folio, "p3.pdf", "pasaporte", contenido=mismo)
    assert len(dups(tercero)) == 1 and primero not in dups(tercero)[0]["mensaje"]  # duplicado del segundo
    _restaurar(primero)
    assert dups(primero) == [] and len(dups(segundo)) == 1 and len(dups(tercero)) == 1


def test_dup001_al_subir_no_cuenta_el_retirado(entorno):
    folio, _, _ = _folio(entorno)
    mismo = b"%PDF-1.4 otro contenido ficticio"
    primero = _subir(entorno, folio, "p1.pdf", "pasaporte", contenido=mismo)
    _retirar(primero)
    segundo = _subir(entorno, folio, "p2.pdf", "pasaporte", contenido=mismo)
    alertas = _cliente("revisor").get(f"/api/v1/documentos/{segundo}").json()["alertas_encontradas"]
    assert "DUP-001" not in [a["codigo"] for a in alertas]


# --- motivo tapado, resumen y auditoria ---

@pytest.mark.parametrize("sensible", [CURP, CURP_AJENA, CURP.lower()], ids=["del-documento", "ajena", "minusculas"])
def test_motivo_con_una_curp_sale_tapado(entorno, sensible):
    sesion, _ = entorno
    folio, credencial, _ = _folio(entorno)
    r = _retirar(credencial, f"Es de otra persona: {sensible}")
    motivo = r.json()["retirado"]["motivo"]
    assert sensible not in motivo and motivo.startswith("Es de otra persona: ****")
    assert sesion.get(Documento, uuid.UUID(credencial)).motivo_retirada == motivo  # tapado ya en la BD
    textos = [_cliente("admin").get("/api/v1/auditoria").text, _expediente(folio).__repr__(),
              _cliente("revisor").get(f"/api/v1/folios/{folio}/resumen.md").text]
    for texto in textos:
        assert sensible not in texto


def test_resumen_lista_los_retirados_al_final_y_el_fragmento_no_los_copia(entorno):
    folio, credencial, comprobante = _folio(entorno)
    _retirar(comprobante, "Comprobante equivocado del cliente")
    resumen = _cliente("revisor").get(f"/api/v1/folios/{folio}/resumen.md").text
    documentos, retirados = resumen.split("## Documentos retirados")
    assert "### Documento 1: " in documentos and "### Documento 2" not in documentos  # solo el que cuenta
    assert documentos.index("## Alertas del expediente") < documentos.index("## Comparaciones")
    assert "Comprobante de domicilio: retirado el" in retirados and "por revisor\\_ficticio" in retirados
    assert "Motivo: Comprobante equivocado del cliente" in retirados
    # La memoria de folios (rag, PERSONA_2) no se rompe y no copia el motivo ni mezcla el retirado
    fragmento = memoria.extraer_fragmento(resumen)
    assert fragmento and "equivocado" not in fragmento and "retirad" not in fragmento.lower()
    assert fragmento.count("### Documento") == 1
    _restaurar(comprobante)
    resumen = _cliente("revisor").get(f"/api/v1/folios/{folio}/resumen.md").text
    assert "Documentos retirados" not in resumen and "### Documento 2" in resumen


def test_auditoria_retirado_con_motivo_tapado_y_restaurado_sin_detalle(entorno):
    sesion, _ = entorno
    folio, credencial, _ = _folio(entorno)
    _retirar(credencial, f"Duplicado {CURP_AJENA}")
    _restaurar(credencial)
    sesion.expire_all()
    entradas = sesion.scalars(select(Auditoria).where(
        Auditoria.accion.in_(["documento_retirado", "documento_restaurado"])).order_by(Auditoria.id)).all()
    assert [(e.accion, e.usuario, e.folio, str(e.documento_id), e.detalle) for e in entradas] == [
        ("documento_retirado", "revisor_ficticio", folio, credencial, {"motivo": "Duplicado ****"}),
        ("documento_restaurado", "revisor_ficticio", folio, credencial, {})]
