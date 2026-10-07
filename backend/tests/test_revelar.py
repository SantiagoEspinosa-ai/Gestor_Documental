"""POST /documentos/{id}/revelar (ADR-010 A4): roles, errores, auditoria sin el valor y Cache-Control.
Mismo entorno que test_enmascaramiento_api (SQLite temporal + moto, motor falso). Datos ficticios."""
import json
import uuid

import pytest
from sqlalchemy import select

from app.core.modelos import Auditoria, Documento
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar
from tests.test_enmascaramiento_api import CLAVE_ELECTOR, CURP, CURP_LEIDA, PASAPORTE, _cliente, entorno  # noqa: F401


def _credencial(entorno, procesar=True, folio=None):
    sesion, s3, _ = entorno
    folio = folio or expediente.crear_folio(sesion, "onboarding", None, "x").folio
    doc = ingestar(sesion, s3, folio, f"{uuid.uuid4()}.pdf", f"%PDF-1.4 {uuid.uuid4()}".encode(),
                   "credencial_elector", "x")
    if procesar:
        procesamiento.procesar(doc.id)
    return folio, doc


def _revelar(rol, doc_id, cuerpo):
    return _cliente(rol).post(f"/api/v1/documentos/{doc_id}/revelar", json=cuerpo)


def _entradas(sesion):
    sesion.expire_all()
    return sesion.scalars(select(Auditoria).where(Auditoria.accion == "dato_revelado")).all()


def test_revisor_y_admin_ven_el_valor_con_no_store_y_auditoria_sin_el_valor(entorno):
    sesion = entorno[0]
    folio, doc = _credencial(entorno)
    for rol in ("revisor", "admin"):
        respuesta = _revelar(rol, doc.id, {"campo": "curp"})
        assert respuesta.status_code == 200
        assert respuesta.json() == {"campo": "curp", "valor": CURP_LEIDA}
        assert respuesta.headers["Cache-Control"] == "no-store"
    entradas = _entradas(sesion)
    assert [(e.usuario, e.folio, e.documento_id, e.detalle) for e in entradas] == [
        ("revisor_ficticio", folio, doc.id, {"campo": "curp"}), ("admin_ficticio", folio, doc.id, {"campo": "curp"})]
    texto = json.dumps([e.detalle for e in entradas])
    assert CURP_LEIDA not in texto
    # Tampoco por GET /auditoria
    auditoria = _cliente("admin").get("/api/v1/auditoria")
    assert auditoria.status_code == 200 and CURP_LEIDA not in auditoria.text
    assert any(e["accion"] == "dato_revelado" for e in auditoria.json()["elementos"])


def test_el_valor_es_el_corregido(entorno):
    _, doc = _credencial(entorno)
    assert _cliente("revisor").patch(f"/api/v1/documentos/{doc.id}/datos", json={"curp": CURP}).status_code == 200
    assert _revelar("revisor", doc.id, {"campo": "curp"}).json() == {"campo": "curp", "valor": CURP}


def test_otro_campo_sensible_y_valor_nulo(entorno):
    _, doc = _credencial(entorno)
    assert _revelar("admin", doc.id, {"campo": "clave_elector"}).json()["valor"] == CLAVE_ELECTOR
    assert _cliente("revisor").patch(f"/api/v1/documentos/{doc.id}/datos",
                                     json={"clave_elector": None}).status_code == 200
    assert _revelar("admin", doc.id, {"campo": "clave_elector"}).json() == {"campo": "clave_elector", "valor": None}


def test_integrador_403_sin_auditoria(entorno):
    _, doc = _credencial(entorno)
    respuesta = _revelar("integrador", doc.id, {"campo": "curp"})
    assert (respuesta.status_code, respuesta.json()["codigo"]) == (403, "SIN_PERMISO")
    assert CURP_LEIDA not in respuesta.text
    assert _entradas(entorno[0]) == []


def test_sin_token_401(entorno):
    _, doc = _credencial(entorno)
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).post(f"/api/v1/documentos/{doc.id}/revelar", json={"campo": "curp"}).status_code == 401


def test_campo_inexistente_o_no_sensible_422(entorno):
    _, doc = _credencial(entorno)
    for campo in ("no_existe", "nombre_completo", "numero_pasaporte"):  # el ultimo es de otra ficha
        respuesta = _revelar("revisor", doc.id, {"campo": campo})
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (422, "PETICION_INVALIDA"), campo
    assert _entradas(entorno[0]) == []


def test_cuerpo_invalido_422(entorno):
    _, doc = _credencial(entorno)
    for cuerpo in ({}, {"campo": ""}, {"campo": "curp", "extra": 1}, {"campo": 5}):
        respuesta = _revelar("revisor", doc.id, cuerpo)
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (422, "PETICION_INVALIDA"), cuerpo


def test_documento_no_encontrado_404(entorno):
    for documento_id in (uuid.uuid4(), "no-es-un-uuid"):
        respuesta = _revelar("revisor", documento_id, {"campo": "curp"})
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")


def test_documento_en_proceso_409(entorno):
    sesion = entorno[0]
    _, doc = _credencial(entorno, procesar=False)
    for estado in ("pendiente", "procesando"):
        sesion.get(Documento, doc.id).estado_analisis = estado
        sesion.commit()
        respuesta = _revelar("revisor", doc.id, {"campo": "curp"})
        assert (respuesta.status_code, respuesta.json()["codigo"]) == (409, "DOCUMENTO_EN_PROCESO")


def test_documento_con_error_409(entorno, monkeypatch):
    def caido(contenido, **kwargs):
        raise RuntimeError("motor caido (ficticio)")
    monkeypatch.setattr(procesamiento, "analizar", caido)
    _, doc = _credencial(entorno)
    respuesta = _revelar("revisor", doc.id, {"campo": "curp"})
    assert (respuesta.status_code, respuesta.json()["codigo"]) == (409, "DOCUMENTO_CON_ERROR")


def test_funciona_con_el_folio_cerrado(entorno):
    folio, doc = _credencial(entorno)
    assert _cliente("revisor").post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"}).status_code == 200
    respuesta = _revelar("revisor", doc.id, {"campo": "curp"})
    assert respuesta.status_code == 200 and respuesta.json()["valor"] == CURP_LEIDA


def test_pasaporte(entorno):
    sesion, s3, _ = entorno
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    doc = ingestar(sesion, s3, folio, "p.pdf", b"%PDF-1.4 pasaporte", "pasaporte", "x")
    procesamiento.procesar(doc.id)
    assert _revelar("revisor", doc.id, {"campo": "numero_pasaporte"}).json()["valor"] == PASAPORTE
    assert _revelar("revisor", doc.id, {"campo": "curp"}).status_code == 422  # no esta en la ficha del pasaporte


# --- motivo opcional (ADR-010 A4c): se guarda tapado con la misma barrera que los logs (A5) ---

CURP_AJENA = "XAXX020202MDFYYYA5"  # ficticia, de nadie del documento


def _motivo(entorno, motivo):
    _, doc = _credencial(entorno)
    respuesta = _revelar("revisor", doc.id, {"campo": "curp", "motivo": motivo})
    assert respuesta.status_code == 200 and respuesta.json()["valor"] == CURP_LEIDA
    [entrada] = _entradas(entorno[0])
    return entrada.detalle


def test_motivo_null_es_como_sin_motivo(entorno):
    _, doc = _credencial(entorno)
    assert _revelar("revisor", doc.id, {"campo": "curp", "motivo": None}).status_code == 200
    assert [e.detalle for e in _entradas(entorno[0])] == [{"campo": "curp"}]


@pytest.mark.parametrize("motivo", ["Verificar con el cliente por telefono", "URGENTE: lo pide auditoria",
                                    "urgente: lo pide auditoria"])
def test_motivo_normal_intacto(entorno, motivo):
    assert _motivo(entorno, motivo) == {"campo": "curp", "motivo": motivo}


@pytest.mark.parametrize("sensible", [CURP_AJENA, CURP_LEIDA, CLAVE_ELECTOR, CURP_AJENA.lower(), CURP_LEIDA.lower()],
                         ids=["curp-ajena", "curp-del-documento", "clave-elector-del-documento",
                              "curp-ajena-en-minusculas", "curp-del-documento-en-minusculas"])
def test_motivo_con_un_dato_sensible_sale_tapado(entorno, sensible):
    detalle = _motivo(entorno, f"El cliente dicta {sensible} por telefono")
    assert sensible not in json.dumps(detalle) and "****" in detalle["motivo"]
    assert detalle["motivo"].startswith("El cliente dicta ****") and detalle["motivo"].endswith(" por telefono")
    auditoria = _cliente("admin").get("/api/v1/auditoria")
    assert sensible not in auditoria.text


@pytest.mark.parametrize("motivo", ["ab", "x" * 201, 5])
def test_motivo_invalido_422_sin_auditoria(entorno, motivo):
    _, doc = _credencial(entorno)
    respuesta = _revelar("revisor", doc.id, {"campo": "curp", "motivo": motivo})
    assert (respuesta.status_code, respuesta.json()["codigo"]) == (422, "PETICION_INVALIDA")
    assert _entradas(entorno[0]) == []
