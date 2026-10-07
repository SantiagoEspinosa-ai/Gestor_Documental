"""ADR-012 (propuesto): el integrador solo accede a los folios que ha creado; el resto da 404, como si no existiera.
Mismo entorno que test_enmascaramiento_api (SQLite temporal + moto, motor falso). Datos ficticios."""
import importlib.util
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.almacenamiento import get_almacenamiento
from app.core.modelos import Folio
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar
from tests.test_enmascaramiento_api import entorno  # noqa: F401

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _cliente(usuario: str, rol: str) -> TestClient:
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token(usuario, rol)[0]}"
    return cliente


@pytest.fixture
def escenario(entorno):  # noqa: F811
    """integrador_ficticio (A) e integrador_b_ficticio (B), cada uno con un folio con un documento analizado,
    y un folio antiguo sin creador."""
    sesion, s3, _ = entorno
    script.crear_usuario(sesion, "integrador_b_ficticio", "integrador", "contrasena-ficticia")
    app.dependency_overrides[get_almacenamiento] = lambda: s3
    a, b = _cliente("integrador_ficticio", "integrador"), _cliente("integrador_b_ficticio", "integrador")
    folios, docs = {}, {}
    for nombre, cliente in (("a", a), ("b", b)):
        r = cliente.post("/api/v1/folios", json={"proceso": "onboarding", "referencia_externa": f"CLI-{nombre}"})
        assert r.status_code == 201
        folios[nombre] = r.json()["folio"]
        doc = ingestar(sesion, s3, folios[nombre], "c.pdf", f"%PDF-1.4 {uuid.uuid4()}".encode(), "credencial_elector",
                       "x")
        procesamiento.procesar(doc.id)
        docs[nombre] = str(doc.id)
    antiguo = expediente.crear_folio(sesion, "onboarding", "CLI-antiguo", "integrador_ficticio")
    sesion.get(Folio, antiguo.folio).creado_por = None  # como un folio de antes de la migracion 0007
    sesion.commit()
    yield {"sesion": sesion, "a": a, "b": b, "folios": folios, "docs": docs, "antiguo": antiguo.folio}
    app.dependency_overrides.pop(get_almacenamiento, None)


def test_post_folios_guarda_el_creador(escenario):
    sesion = escenario["sesion"]
    sesion.expire_all()
    assert sesion.get(Folio, escenario["folios"]["a"]).creado_por == "integrador_ficticio"
    assert sesion.get(Folio, escenario["folios"]["b"]).creado_por == "integrador_b_ficticio"


def test_el_integrador_accede_a_lo_suyo(escenario):
    a, folio, doc = escenario["a"], escenario["folios"]["a"], escenario["docs"]["a"]
    assert a.get(f"/api/v1/folios/{folio}").status_code == 200
    assert a.get(f"/api/v1/documentos/{doc}").status_code == 200
    assert a.get(f"/api/v1/folios/{folio}/resumen.md").status_code == 200
    r = a.post(f"/api/v1/folios/{folio}/documentos", files={"archivo": ("p.pdf", b"%PDF-1.4 propio", "application/pdf")},
               data={"tipo_declarado": "pasaporte"})
    assert r.status_code == 202


def test_el_integrador_a_no_ve_lee_ni_sube_al_folio_de_b(escenario):
    a, folio_b, doc_b = escenario["a"], escenario["folios"]["b"], escenario["docs"]["b"]
    inexistente = "ONB-2026-999999"
    for ruta in (f"/api/v1/folios/{folio_b}", f"/api/v1/folios/{folio_b}/resumen.md"):
        r = a.get(ruta)
        assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO"), ruta
        # Misma respuesta que un folio que no existe (el mensaje solo repite el folio pedido): no revela nada
        otro = a.get(ruta.replace(folio_b, inexistente)).json()
        assert r.json() == {k: v.replace(inexistente, folio_b) for k, v in otro.items()}
    r = a.get(f"/api/v1/documentos/{doc_b}")
    assert (r.status_code, r.json()["codigo"]) == (404, "DOCUMENTO_NO_ENCONTRADO")
    assert r.json() == a.get(f"/api/v1/documentos/{uuid.uuid4()}").json()
    r = a.post(f"/api/v1/folios/{folio_b}/documentos", files={"archivo": ("x.pdf", b"%PDF-1.4 ajeno", "application/pdf")},
               data={"tipo_declarado": "pasaporte"})
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")
    sesion = escenario["sesion"]
    sesion.expire_all()
    assert len(expediente.obtener_expediente(sesion, folio_b).documentos) == 1  # no se subio nada


def test_el_listado_sigue_cerrado_al_integrador(escenario):
    r = escenario["a"].get("/api/v1/folios")
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")


def test_folio_antiguo_sin_creador_no_lo_ve_el_integrador(escenario):
    r = escenario["a"].get(f"/api/v1/folios/{escenario['antiguo']}")
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")


@pytest.mark.parametrize("rol", ["revisor", "admin"])
def test_revisor_y_admin_ven_todo(escenario, rol):
    cliente = _cliente(f"{rol}_ficticio", rol)
    for folio in (*escenario["folios"].values(), escenario["antiguo"]):
        assert cliente.get(f"/api/v1/folios/{folio}").status_code == 200
        assert cliente.get(f"/api/v1/folios/{folio}/resumen.md").status_code == 200
    for doc in escenario["docs"].values():
        assert cliente.get(f"/api/v1/documentos/{doc}").status_code == 200
    if rol == "revisor":
        assert cliente.get("/api/v1/folios").json()["total"] == 3
