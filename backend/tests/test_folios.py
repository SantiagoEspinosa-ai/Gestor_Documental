"""Tests de modulos/expediente/servicio.py y de /api/v1/folios. SQLite temporal y datos ficticios.

La concurrencia real solo se prueba contra PostgreSQL (TEST_POSTGRES_URL); sin ella se salta.
"""
import importlib.util
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Auditoria, Documento, Folio, Proceso, Resultado, SecuenciaFolio
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio
from app.schemas.resultado import DecisionHumana, EstadoGeneral, ResultadoExpediente

SECRETO = "clave-ficticia-de-test"
URL = "/api/v1/folios"
UTC = timezone.utc
ANIO = datetime.now(UTC).astimezone(ZoneInfo("America/Mexico_City")).year

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _entorno(monkeypatch, url: str) -> None:
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": url,
        "AWS_ACCESS_KEY_ID": SECRETO,
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.delenv("ZONA_HORARIA", raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    _entorno(monkeypatch, f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        # onboarding como en config/procesos.yaml: 2 requeridos y pasaporte opcional
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB",
                      tipos_requeridos=["credencial_elector", "comprobante_domicilio"],
                      tipos_opcionales=["pasaporte"], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        s.add(Proceso(nombre="otro", prefijo_folio="OTR", tipos_requeridos=["credencial_elector"],
                      tipos_opcionales=[], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        for rol in ("admin", "revisor", "integrador"):
            script.crear_usuario(s, f"{rol}_ficticio", rol, "contrasena-ficticia")
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def cliente(sesion):
    return TestClient(app)


def _cab(rol: str) -> dict:
    return {"Authorization": f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"}


def _resultado_json(folio: str, doc_id: uuid.UUID, confianza: float) -> dict:
    return {
        "folio_solicitud": folio,
        "identificador_unico_documento": str(doc_id),
        "tipo_documental_declarado": "credencial_elector",
        "tipo_documental_detectado": "credencial_elector",
        "confianza_clasificacion": confianza,
        "estado_analisis": "completado",
        "referencia_archivo_original": {"nombre_archivo": "credencial_ficticia.pdf",
                                        "ruta": f"onboarding/{doc_id}.pdf", "hash": "0" * 64},
    }


# --- numeracion ---

def test_primer_y_segundo_folio(sesion):
    assert servicio.crear_folio(sesion, "onboarding", None, "revisor_ficticio").folio == f"ONB-{ANIO}-000001"
    assert servicio.crear_folio(sesion, "onboarding", None, "revisor_ficticio").folio == f"ONB-{ANIO}-000002"
    assert servicio.crear_folio(sesion, "otro", None, "revisor_ficticio").folio == f"OTR-{ANIO}-000001"


def test_cambiar_de_anio_reinicia_la_secuencia(sesion):
    en_2026 = datetime(2026, 6, 1, 12, tzinfo=UTC)
    assert servicio.crear_folio(sesion, "onboarding", None, "x", ahora=en_2026).folio == "ONB-2026-000001"
    assert servicio.crear_folio(sesion, "onboarding", None, "x", ahora=en_2026).folio == "ONB-2026-000002"
    en_2027 = datetime(2027, 6, 1, 12, tzinfo=UTC)
    assert servicio.crear_folio(sesion, "onboarding", None, "x", ahora=en_2027).folio == "ONB-2027-000001"


def test_el_anio_es_el_de_la_zona_del_negocio(sesion):
    # 2027-01-01 03:00 UTC = 2026-12-31 21:00 en Ciudad de Mexico
    ahora = datetime(2027, 1, 1, 3, tzinfo=UTC)
    assert servicio.crear_folio(sesion, "onboarding", None, "x", ahora=ahora).folio == "ONB-2026-000001"


def test_zona_horaria_invalida(monkeypatch, sesion):
    monkeypatch.setenv("ZONA_HORARIA", "Marte/Olympus")
    get_settings.cache_clear()
    with pytest.raises(Exception, match="zona horaria desconocida"):
        get_settings()


def test_secuencia_agotada(cliente, sesion):
    sesion.add(SecuenciaFolio(proceso="onboarding", anio=ANIO, ultimo=999_999))
    sesion.commit()
    r = cliente.post(URL, json={"proceso": "onboarding"}, headers=_cab("revisor"))
    assert (r.status_code, r.json()["codigo"]) == (409, "SECUENCIA_AGOTADA")
    assert sesion.scalar(select(Folio)) is None


# --- POST /folios ---

def test_crear_por_api_y_auditoria(cliente, sesion):
    r = cliente.post(URL, json={"proceso": "onboarding", "referencia_externa": "CLI-000123"},
                     headers=_cab("integrador"))
    assert r.status_code == 201
    assert r.json() == {"folio": f"ONB-{ANIO}-000001", "estado_general": "en_revision"}
    assert sesion.get(Folio, f"ONB-{ANIO}-000001").referencia_externa == "CLI-000123"
    fila = sesion.scalar(select(Auditoria).where(Auditoria.accion == "folio_creado"))
    assert (fila.usuario, fila.folio) == ("integrador_ficticio", f"ONB-{ANIO}-000001")


def test_proceso_inexistente(cliente):
    r = cliente.post(URL, json={"proceso": "no_existe"}, headers=_cab("revisor"))
    assert (r.status_code, r.json()["codigo"]) == (404, "PROCESO_NO_ENCONTRADO")


@pytest.mark.parametrize("rol,esperado", [("integrador", 201), ("revisor", 201), ("admin", 403)])
def test_roles_que_crean(cliente, rol, esperado):
    assert cliente.post(URL, json={"proceso": "onboarding"}, headers=_cab(rol)).status_code == esperado


def test_sin_token(cliente):
    assert cliente.post(URL, json={"proceso": "onboarding"}).status_code == 401
    assert cliente.get(URL).status_code == 401
    assert cliente.get(f"{URL}/ONB-2026-000001").status_code == 401


def test_referencia_externa_demasiado_larga(cliente):
    r = cliente.post(URL, json={"proceso": "onboarding", "referencia_externa": "x" * 101},
                     headers=_cab("revisor"))
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")


# --- EXP-001 al crear el folio ---

def test_folio_nuevo_nace_con_una_exp_001_por_tipo_requerido(sesion):
    folio = servicio.crear_folio(sesion, "onboarding", None, "x").folio
    alertas = sesion.scalars(select(AlertaBD).where(AlertaBD.folio == folio).order_by(AlertaBD.campo)).all()
    assert [(a.codigo, a.campo) for a in alertas] == [("EXP-001", "comprobante_domicilio"),
                                                      ("EXP-001", "credencial_elector")]
    for a in alertas:
        assert (a.documento_id, a.severidad, a.confianza, a.aplica) == (None, "bloqueante", 1.0, None)
    # nombre_visible de las fichas YAML; el opcional (pasaporte) no genera ninguna
    assert {a.mensaje for a in alertas} == {"Falta el documento requerido: Comprobante de domicilio",
                                            "Falta el documento requerido: Credencial de elector"}


def test_exp_001_con_tipo_sin_ficha_usa_el_nombre_tecnico(sesion):
    sesion.get(Proceso, "otro").tipos_requeridos = ["tipo_sin_ficha"]
    sesion.commit()
    folio = servicio.crear_folio(sesion, "otro", None, "x").folio
    alerta = sesion.scalar(select(AlertaBD).where(AlertaBD.folio == folio))
    assert alerta.mensaje == "Falta el documento requerido: tipo_sin_ficha"


def test_exp_001_en_alertas_expediente(cliente, sesion):
    folio = servicio.crear_folio(sesion, "onboarding", None, "x").folio
    r = cliente.get(f"{URL}/{folio}", headers=_cab("revisor")).json()
    alertas = r["alertas_expediente"]
    assert sorted(a["campo"] for a in alertas) == ["comprobante_domicilio", "credencial_elector"]
    for a in alertas:
        assert a["codigo"] == "EXP-001" and a["severidad"] == "bloqueante"
        assert uuid.UUID(a["id"])
        assert a["aplica"] is None
    # las alertas de documento no aparecen como alertas de expediente
    doc = Documento(folio=folio, nombre_archivo="a.pdf", ruta_s3="a", hash_sha256="1" * 64)
    sesion.add(doc)
    sesion.flush()
    sesion.add(AlertaBD(folio=folio, documento_id=doc.id, codigo="DUP-001", severidad="critica",
                        mensaje="ficticia", confianza=1.0))
    sesion.commit()
    r = cliente.get(f"{URL}/{folio}", headers=_cab("revisor")).json()
    assert {a["codigo"] for a in r["alertas_expediente"]} == {"EXP-001"}


# --- GET /folios/{folio} ---

def test_folio_inexistente(cliente):
    r = cliente.get(f"{URL}/ONB-2026-999999", headers=_cab("integrador"))
    assert (r.status_code, r.json()["codigo"]) == (404, "FOLIO_NO_ENCONTRADO")


def test_expediente_con_la_version_mayor(cliente, sesion):
    folio = servicio.crear_folio(sesion, "onboarding", None, "x").folio
    con_resultado = Documento(folio=folio, nombre_archivo="a.pdf", ruta_s3="a", hash_sha256="1" * 64)
    sin_resultado = Documento(folio=folio, nombre_archivo="b.pdf", ruta_s3="b", hash_sha256="2" * 64)
    sesion.add_all([con_resultado, sin_resultado])
    sesion.flush()
    sesion.add_all([Resultado(documento_id=con_resultado.id, version=1,
                              json=_resultado_json(folio, con_resultado.id, 0.5)),
                    Resultado(documento_id=con_resultado.id, version=2,
                              json=_resultado_json(folio, con_resultado.id, 0.9))])
    sesion.commit()

    r = cliente.get(f"{URL}/{folio}", headers=_cab("integrador"))
    assert r.status_code == 200
    expediente = ResultadoExpediente.model_validate(r.json())
    assert (expediente.folio, expediente.proceso, expediente.estado_general) == (folio, "onboarding",
                                                                                 "en_revision")
    # Todos los documentos del folio aparecen; el que tiene resultado, con su version mayor
    por_id = {d.identificador_unico_documento: d for d in expediente.documentos}
    assert set(por_id) == {str(con_resultado.id), str(sin_resultado.id)}
    assert por_id[str(con_resultado.id)].confianza_clasificacion == 0.9
    assert por_id[str(sin_resultado.id)].estado_analisis.value == "pendiente"
    assert por_id[str(sin_resultado.id)].confianza_clasificacion is None
    assert expediente.decision_humana is None


def test_expediente_con_referencia_y_fecha_de_solicitud(cliente, sesion):
    folio = servicio.crear_folio(sesion, "onboarding", "CLI-000123", "x")
    r = cliente.get(f"{URL}/{folio.folio}", headers=_cab("integrador")).json()
    assert r["referencia_externa"] == "CLI-000123"
    assert r["fecha_solicitud"] is not None
    assert datetime.fromisoformat(r["fecha_solicitud"]).replace(tzinfo=None) == \
        folio.creado_en.replace(tzinfo=None)


def test_expediente_con_decision_guardada(cliente, sesion):
    folio = servicio.crear_folio(sesion, "onboarding", None, "x")
    folio.estado_general = "rechazado"
    folio.decision = "rechazar"
    folio.decision_comentario = "Domicilio distinto en los documentos (ficticio)"
    folio.decision_usuario = "revisor_ficticio"
    folio.decision_fecha = datetime(2026, 9, 30, 12, tzinfo=UTC)
    sesion.commit()

    expediente = ResultadoExpediente.model_validate(
        cliente.get(f"{URL}/{folio.folio}", headers=_cab("revisor")).json())
    assert expediente.estado_general == EstadoGeneral.rechazado
    assert expediente.decision_humana == DecisionHumana.rechazar
    assert expediente.comentario_decision == "Domicilio distinto en los documentos (ficticio)"
    assert expediente.usuario_decision == "revisor_ficticio"
    assert expediente.fecha_decision.replace(tzinfo=None) == datetime(2026, 9, 30, 12)


# --- GET /folios ---

def test_integrador_no_puede_listar(cliente):
    assert cliente.get(URL, headers=_cab("integrador")).status_code == 403


def test_lista_paginacion_total_filtros_y_orden(cliente, sesion):
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i in range(5):
        f = servicio.crear_folio(sesion, "onboarding", None, "x")
        f.creado_en = base + timedelta(days=i)
    otro = servicio.crear_folio(sesion, "otro", None, "x")
    otro.creado_en = base + timedelta(days=10)
    otro.estado_general = "aprobado"
    sesion.commit()

    r = cliente.get(URL, params={"pagina": 1, "tamano_pagina": 2}, headers=_cab("revisor")).json()
    assert (r["total"], r["pagina"], r["tamano_pagina"]) == (6, 1, 2)
    assert [e["folio"] for e in r["elementos"]] == [f"OTR-{ANIO}-000001", f"ONB-{ANIO}-000005"]

    r = cliente.get(URL, params={"pagina": 3, "tamano_pagina": 2}, headers=_cab("admin")).json()
    assert [e["folio"] for e in r["elementos"]] == [f"ONB-{ANIO}-000002", f"ONB-{ANIO}-000001"]

    r = cliente.get(URL, params={"proceso": "onboarding"}, headers=_cab("revisor")).json()
    assert r["total"] == 5
    r = cliente.get(URL, params={"estado_general": "aprobado"}, headers=_cab("revisor")).json()
    assert [e["folio"] for e in r["elementos"]] == [f"OTR-{ANIO}-000001"]
    assert set(r["elementos"][0]) == {"folio", "proceso", "estado_general", "recomendacion_global",
                                      "n_documentos", "n_bloqueantes_sin_resolver", "fecha_solicitud",
                                      "referencia_externa"}  # ADR-008


def test_lista_con_referencia_externa(cliente, sesion):  # ADR-008
    servicio.crear_folio(sesion, "onboarding", "CLI-000123", "x")
    servicio.crear_folio(sesion, "otro", None, "x")
    elementos = cliente.get(URL, headers=_cab("revisor")).json()["elementos"]
    por_proceso = {e["proceso"]: e["referencia_externa"] for e in elementos}
    assert por_proceso == {"onboarding": "CLI-000123", "otro": None}


@pytest.mark.parametrize("params", [{"estado_general": "cerrado"}, {"pagina": 0},
                                    {"tamano_pagina": 101}])
def test_lista_parametros_invalidos(cliente, params):
    r = cliente.get(URL, params=params, headers=_cab("revisor"))
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")


def test_folio_nuevo_tiene_2_bloqueantes_sin_resolver(cliente, sesion):
    servicio.crear_folio(sesion, "onboarding", None, "x")
    elemento = cliente.get(URL, headers=_cab("revisor")).json()["elementos"][0]
    assert (elemento["n_documentos"], elemento["n_bloqueantes_sin_resolver"]) == (0, 2)


def test_bloqueantes_sin_resolver_cuenta_null_y_true(cliente, sesion):
    folio = servicio.crear_folio(sesion, "onboarding", None, "x").folio
    # Las 2 EXP-001 del folio nuevo se marcan como falso positivo: aplica=false no cuenta
    for exp in sesion.scalars(select(AlertaBD).where(AlertaBD.folio == folio)):
        exp.aplica = False
    doc = Documento(folio=folio, nombre_archivo="a.pdf", ruta_s3="a", hash_sha256="1" * 64)
    sesion.add(doc)
    sesion.flush()
    for aplica, severidad, documento_id in [(None, "bloqueante", doc.id), (True, "bloqueante", None),
                                            (False, "bloqueante", doc.id), (None, "critica", doc.id)]:
        sesion.add(AlertaBD(folio=folio, documento_id=documento_id, codigo="X", severidad=severidad,
                            mensaje="ficticia", confianza=1.0, aplica=aplica))
    sesion.commit()

    elemento = cliente.get(URL, headers=_cab("revisor")).json()["elementos"][0]
    assert (elemento["n_documentos"], elemento["n_bloqueantes_sin_resolver"]) == (1, 2)


# --- concurrencia real (solo PostgreSQL) ---

@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requiere TEST_POSTGRES_URL")
def test_folios_concurrencia_postgres(monkeypatch):
    url = os.environ["TEST_POSTGRES_URL"]
    _entorno(monkeypatch, url)
    engine = create_engine(url, pool_size=20)
    Base.metadata.create_all(engine)

    def limpiar():
        with Session(engine) as s:
            s.execute(delete(Auditoria).where(Auditoria.folio.like("CCT-%")))
            s.execute(delete(AlertaBD).where(AlertaBD.folio.like("CCT-%")))
            s.execute(delete(Folio).where(Folio.proceso == "concurrencia_test"))
            s.execute(delete(SecuenciaFolio).where(SecuenciaFolio.proceso == "concurrencia_test"))
            s.execute(delete(Proceso).where(Proceso.nombre == "concurrencia_test"))
            s.commit()

    limpiar()
    with Session(engine) as s:
        s.add(Proceso(nombre="concurrencia_test", prefijo_folio="CCT", tipos_requeridos=["x"],
                      tipos_opcionales=[], permitir_antecedentes=False, caducidad_antecedentes_dias=1))
        s.commit()

    folios, errores, salida = [], [], threading.Barrier(20)

    def crear():
        try:
            salida.wait()
            with Session(engine) as s:
                folios.append(servicio.crear_folio(s, "concurrencia_test", None, "x").secuencia)
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=crear) for _ in range(20)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    try:
        assert not errores
        assert sorted(folios) == list(range(1, 21))
    finally:
        limpiar()
        engine.dispose()
        get_settings.cache_clear()
        db.get_engine.cache_clear()
