"""Reanudar al arrancar los analisis que un reinicio dejo a medias (ingesta.servicio.reanudar_pendientes).
SQLite temporal, `procesamiento.procesar` sustituido por uno falso. Datos ficticios."""
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import Documento, Proceso
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import procesamiento
from app.modulos.ingesta import servicio as ingesta

SECRETO = "clave-ficticia-de-test-de-32-caracteres"


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
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=[], tipos_opcionales=[],
                      permitir_antecedentes=False, caducidad_antecedentes_dias=30))
        s.commit()
        yield s
    db.get_engine().dispose()
    db.get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def llamadas(monkeypatch):
    """procesar falso y _lanzar sin hilo: cada relanzamiento queda en la lista, en orden."""
    vistas: list[tuple[uuid.UUID, str | None]] = []
    monkeypatch.setattr(procesamiento, "procesar", lambda d, tipo_confirmado=None: vistas.append((d, tipo_confirmado)))
    monkeypatch.setattr(ingesta, "_lanzar", lambda funcion: funcion())
    return vistas


def _documentos(sesion) -> dict[str, Documento]:
    """Un documento por estado; el procesando tiene un tipo confirmado (reproceso a medias)."""
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    docs = {}
    for estado, confirmado in (("procesando", "pasaporte"), ("pendiente", None), ("completado", None), ("error", None)):
        doc = Documento(id=uuid.uuid4(), folio=folio, nombre_archivo=f"{estado}.pdf", ruta_s3=f"x/{estado}.pdf",
                        hash_sha256=uuid.uuid4().hex * 2, tipo_declarado="credencial_elector",
                        tipo_documental_confirmado=confirmado, estado_analisis=estado)
        sesion.add(doc)
        sesion.flush()  # creado_en distinto y en orden
        docs[estado] = doc
    sesion.commit()
    return docs


def test_relanza_pendiente_y_procesando_con_su_tipo_confirmado(sesion, llamadas, caplog):
    docs = _documentos(sesion)
    with caplog.at_level("INFO", logger="app.modulos.ingesta.servicio"):
        ids = ingesta.reanudar_pendientes(sesion)
    # Orden por creado_en: en SQLite puede empatar (segundos), asi que no se comprueba el orden
    assert sorted(ids) == sorted([docs["procesando"].id, docs["pendiente"].id])
    assert set(llamadas) == {(docs["procesando"].id, "pasaporte"), (docs["pendiente"].id, None)}
    assert "Reanudando 2 analisis interrumpidos" in caplog.text
    assert "procesando.pdf" not in caplog.text and "credencial" not in caplog.text  # solo ids


def test_completado_y_error_no_se_tocan(sesion, llamadas):
    docs = _documentos(sesion)
    ingesta.reanudar_pendientes(sesion)
    relanzados = {d for d, _ in llamadas}
    assert docs["completado"].id not in relanzados and docs["error"].id not in relanzados
    sesion.expire_all()
    assert sesion.get(Documento, docs["completado"].id).estado_analisis == "completado"
    assert sesion.get(Documento, docs["error"].id).estado_analisis == "error"


def test_sin_documentos_a_medias_no_hace_nada(sesion, llamadas):
    assert ingesta.reanudar_pendientes(sesion) == []
    assert llamadas == []


def test_el_arranque_reanuda_con_el_ajuste_activado(sesion, llamadas, monkeypatch):
    docs = _documentos(sesion)
    monkeypatch.setenv("REANUDAR_ANALISIS_AL_ARRANCAR", "true")
    get_settings.cache_clear()
    with TestClient(app):
        pass
    assert {d for d, _ in llamadas} == {docs["procesando"].id, docs["pendiente"].id}


def test_con_el_ajuste_a_false_no_se_relanza_nada(sesion, llamadas, monkeypatch):
    _documentos(sesion)
    monkeypatch.setenv("REANUDAR_ANALISIS_AL_ARRANCAR", "false")
    get_settings.cache_clear()
    with TestClient(app):
        pass
    assert llamadas == []


def test_el_arranque_no_espera_a_que_terminen(sesion, monkeypatch):
    # Hilo de verdad y un procesar que no acaba hasta que el test lo suelta
    _documentos(sesion)
    soltar, empezados = threading.Event(), []

    def procesar_lento(documento_id, tipo_confirmado=None):
        empezados.append(documento_id)
        soltar.wait(10)
    monkeypatch.setattr(procesamiento, "procesar", procesar_lento)
    monkeypatch.setenv("REANUDAR_ANALISIS_AL_ARRANCAR", "true")
    get_settings.cache_clear()
    inicio = time.monotonic()
    try:
        with TestClient(app) as cliente:
            assert cliente.get("/salud").status_code == 200  # la API responde con los analisis en marcha
            assert time.monotonic() - inicio < 5
    finally:
        soltar.set()
    for _ in range(100):  # los hilos daemon arrancan enseguida
        if len(empezados) == 2:
            break
        time.sleep(0.05)
    assert len(empezados) == 2
