"""H16: antecedentes de un folio (ADR-010 C). expediente.listar_antecedentes y motivo_sin_antecedentes, y
GET /api/v1/folios/{folio}/antecedentes. SQLite temporal; folios creados directamente en la BD. Datos ficticios."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import Folio, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta.servicio import ingestar
from app.modulos.rag import servicio as rag
from tests import test_enmascaramiento_api as base
from tests.test_enmascaramiento_api import entorno  # noqa: F401

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
AHORA = datetime.now(timezone.utc)
REFERENCIA = "CLI-000101"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": SECRETO, "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        for nombre, prefijo, permitir in (("onboarding", "ONB", True), ("otro", "OTR", True), ("cerrado", "CRR", False)):
            s.add(Proceso(nombre=nombre, prefijo_folio=prefijo, tipos_requeridos=[], tipos_opcionales=[],
                          permitir_antecedentes=permitir, caducidad_antecedentes_dias=30))
        for rol in ("admin", "revisor", "integrador"):
            script.crear_usuario(s, f"{rol}_ficticio", rol, "contrasena-ficticia")
        s.commit()
        yield s
    db.get_engine().dispose()
    db.get_engine.cache_clear()
    get_settings.cache_clear()


_secuencia = iter(range(1, 1000))


def _folio(s: Session, proceso="onboarding", referencia=REFERENCIA, dias_desde_decision: float | None = 1,
           decision="aprobar") -> str:
    """Folio en la BD; cerrado hace `dias_desde_decision` dias, o abierto si es None."""
    n = next(_secuencia)
    prefijo = s.get(Proceso, proceso).prefijo_folio
    fila = Folio(folio=f"{prefijo}-2026-{n:06d}", proceso=proceso, anio=2026, secuencia=n, referencia_externa=referencia)
    if dias_desde_decision is not None:
        fila.estado_general = "aprobado" if decision == "aprobar" else "rechazado"
        fila.decision, fila.decision_usuario = decision, "revisor_ficticio"
        fila.decision_fecha = AHORA - timedelta(days=dias_desde_decision)
    s.add(fila)
    s.commit()
    return fila.folio


def _get(rol: str, folio: str):
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"
    return cliente.get(f"/api/v1/folios/{folio}/antecedentes")


def test_filtros_del_servicio(sesion):
    actual = _folio(sesion, dias_desde_decision=None)
    valido = _folio(sesion, dias_desde_decision=2)
    _folio(sesion, referencia="CLI-OTRA")                 # otra persona
    _folio(sesion, proceso="otro")                        # otro proceso, misma referencia
    _folio(sesion, dias_desde_decision=None)              # abierto
    _folio(sesion, dias_desde_decision=31)                # caducado (30 dias)
    rechazado = _folio(sesion, dias_desde_decision=29, decision="rechazar")
    assert [f.folio for f in expediente.listar_antecedentes(sesion, actual, ahora=AHORA)] == [valido, rechazado]


def test_excluye_el_actual_aunque_este_cerrado(sesion):
    actual = _folio(sesion, dias_desde_decision=1)
    otro = _folio(sesion, dias_desde_decision=3)
    assert [f.folio for f in expediente.listar_antecedentes(sesion, actual)] == [otro]


def test_orden_y_limite_de_10(sesion):
    actual = _folio(sesion, dias_desde_decision=None)
    folios = [_folio(sesion, dias_desde_decision=d) for d in (5, 1, 12, 3, 8, 2, 9, 4, 11, 7, 6, 10)]
    resultado = [f.folio for f in expediente.listar_antecedentes(sesion, actual)]
    por_fecha = [f for _, f in sorted(zip((5, 1, 12, 3, 8, 2, 9, 4, 11, 7, 6, 10), folios))]
    assert resultado == por_fecha[:10] and len(resultado) == expediente.MAX_ANTECEDENTES


def test_folio_inexistente_404(sesion):
    for funcion in (expediente.listar_antecedentes, expediente.motivo_sin_antecedentes):
        with pytest.raises(Exception, match="FOLIO_NO_ENCONTRADO"):
            funcion(sesion, "ONB-2026-999999")
    r = _get("revisor", "ONB-2026-999999")
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")


def test_respuesta_con_antecedentes_y_fragmento(sesion):
    actual = _folio(sesion, dias_desde_decision=None)
    previo = _folio(sesion, dias_desde_decision=2, decision="rechazar")
    sin_memoria = _folio(sesion, dias_desde_decision=4)
    rag.indexar_resumen(previo, "# Expediente X\n\n- Referencia: CLI-000101\n\n## Decision\n\n- Decision: Rechazado\n",
                        sesion=sesion)
    r = _get("revisor", actual)
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["permitido"], cuerpo["motivo"]) == (True, None)
    assert [e["folio"] for e in cuerpo["elementos"]] == [previo, sin_memoria]
    primero = cuerpo["elementos"][0]
    assert set(primero) == {"folio", "fecha_solicitud", "estado_general", "decision_humana", "fecha_decision",
                            "fragmento_resumen"}
    assert (primero["estado_general"], primero["decision_humana"]) == ("rechazado", "rechazar")
    assert "Decision: Rechazado" in primero["fragmento_resumen"]
    assert cuerpo["elementos"][1]["fragmento_resumen"] is None


def test_permitido_sin_coincidencias(sesion):
    r = _get("admin", _folio(sesion, dias_desde_decision=None))
    assert (r.status_code, r.json()) == (200, {"permitido": True, "motivo": None, "elementos": []})


def test_proceso_sin_antecedentes(sesion):
    actual = _folio(sesion, proceso="cerrado", dias_desde_decision=None)
    _folio(sesion, proceso="cerrado", dias_desde_decision=1)
    r = _get("revisor", actual)
    assert (r.status_code, r.json()) == (200, {"permitido": False, "motivo": "proceso_sin_antecedentes", "elementos": []})


def test_folio_sin_referencia(sesion):
    actual = _folio(sesion, referencia=None, dias_desde_decision=None)
    _folio(sesion, referencia=None, dias_desde_decision=1)  # sin referencia no se relacionan
    r = _get("revisor", actual)
    assert (r.status_code, r.json()) == (200, {"permitido": False, "motivo": "folio_sin_referencia", "elementos": []})
    assert expediente.listar_antecedentes(sesion, actual) == []


def test_proceso_sin_antecedentes_manda_sobre_sin_referencia(sesion):
    actual = _folio(sesion, proceso="cerrado", referencia=None, dias_desde_decision=None)
    assert _get("revisor", actual).json()["motivo"] == "proceso_sin_antecedentes"


def test_roles(sesion):
    actual = _folio(sesion, dias_desde_decision=None)
    assert _get("revisor", actual).status_code == 200
    assert _get("admin", actual).status_code == 200
    r = _get("integrador", actual)
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")
    assert TestClient(app).get(f"/api/v1/folios/{actual}/antecedentes").status_code == 401


def test_el_fragmento_sale_enmascarado(entorno):
    """Flujo real con datos sensibles ficticios (credencial y pasaporte): el folio previo se decide, su
    resumen.md (el mismo texto que da la API, ya enmascarado) se indexa en la memoria y sale como
    antecedente de otro folio de la misma referencia sin ningun valor sensible completo."""
    sesion, s3, _ = entorno
    sesion.get(Proceso, "onboarding").permitir_antecedentes = True
    sesion.commit()
    previo = expediente.crear_folio(sesion, "onboarding", REFERENCIA, "x").folio
    for nombre, tipo in (("c.pdf", "credencial_elector"), ("p.pdf", "pasaporte")):
        doc = ingestar(sesion, s3, previo, nombre, f"%PDF-1.4 {nombre}".encode(), tipo, "x")
        procesamiento.procesar(doc.id)
    revisor = base._cliente("revisor")
    assert revisor.post(f"/api/v1/folios/{previo}/decision", json={"decision": "rechazar"}).status_code == 200
    rag.indexar_resumen(previo, revisor.get(f"/api/v1/folios/{previo}/resumen.md").text, sesion=sesion)

    actual = expediente.crear_folio(sesion, "onboarding", REFERENCIA, "x").folio
    r = revisor.get(f"/api/v1/folios/{actual}/antecedentes")
    assert r.status_code == 200
    [elemento] = r.json()["elementos"]
    assert elemento["folio"] == previo and "Decision: Rechazado" in elemento["fragmento_resumen"]
    for valor in base.SENSIBLES:
        assert valor not in r.text
