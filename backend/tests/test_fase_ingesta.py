"""Fase del analisis (ADR-014): registro en memoria de la ingesta, construir_resultado y webhooks. Motor falso:
sin red ni modelo. Datos inventados."""
import threading
import uuid

import pytest
from sqlalchemy import update

from app.core import webhooks
from app.core.modelos import Documento, Proceso
from app.modulos.ingesta import procesamiento as ingesta_procesamiento
from app.modulos.ingesta.servicio import construir_resultado
from app.schemas.resultado import EstadoAnalisis, FaseAnalisis
from tests.test_ingesta import (  # noqa: F401  (fixtures)
    _motor_falso,
    _subir,
    folio,
    s3,
    s3_en_procesamiento,
    sesion,
)

F = FaseAnalisis


# --- Registro en memoria ---

def _motor_con_fases(monkeypatch, vistas: list, fases=(F.preparando, F.ocr, F.clasificando, F.extrayendo),
                     falla=None):
    """Motor falso que avisa las fases y, en cada una, apunta lo que ve la plataforma (leer_fase)."""
    def analizar(contenido, **kwargs):
        vistas.append(ingesta_procesamiento.leer_fase(_id(kwargs)))  # al entrar: ya no esta en cola
        for fase in fases:
            kwargs["al_avanzar"](fase)
            vistas.append(ingesta_procesamiento.leer_fase(_id(kwargs)))
        if falla:
            raise falla
        return original(contenido, **kwargs)
    _motor_falso(monkeypatch)
    original = ingesta_procesamiento.analizar
    monkeypatch.setattr(ingesta_procesamiento, "analizar", analizar)


def _id(kwargs):
    return uuid.UUID(kwargs["identificador"])


def test_registro_fijar_leer_y_borrar():
    i = uuid.uuid4()
    assert ingesta_procesamiento.leer_fase(i) is None
    ingesta_procesamiento.fijar_fase(i, F.ocr)
    assert ingesta_procesamiento.leer_fase(i) is F.ocr
    ingesta_procesamiento.borrar_fase(i)
    ingesta_procesamiento.borrar_fase(i)  # dos veces no falla
    assert ingesta_procesamiento.leer_fase(i) is None


def test_en_cola_antes_del_semaforo_y_despues_las_fases(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    en_cola = []

    class SemaforoQueMira:
        def __enter__(self):
            en_cola.append(ingesta_procesamiento.leer_fase(doc.id))
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(ingesta_procesamiento, "_semaforo", lambda tamano: SemaforoQueMira())
    vistas: list = []
    _motor_con_fases(monkeypatch, vistas)
    ingesta_procesamiento.procesar(doc.id)
    assert en_cola == [F.en_cola]
    assert vistas == [F.en_cola, F.preparando, F.ocr, F.clasificando, F.extrayendo]
    assert ingesta_procesamiento.leer_fase(doc.id) is None  # borrada al terminar


def test_construir_resultado_da_la_fase_mientras_procesa(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    vistas_api: list = []

    def analizar(contenido, **kwargs):
        kwargs["al_avanzar"](F.vision)
        with ingesta_procesamiento.SesionLocal(bind=ingesta_procesamiento.get_engine()) as otra:
            fila = otra.get(Documento, doc.id)
            vistas_api.append((fila.estado_analisis, construir_resultado(otra, fila).fase_analisis))
        return original(contenido, **kwargs)
    _motor_falso(monkeypatch)
    original = ingesta_procesamiento.analizar
    monkeypatch.setattr(ingesta_procesamiento, "analizar", analizar)
    ingesta_procesamiento.procesar(doc.id)
    assert vistas_api == [("procesando", F.vision)]
    sesion.expire_all()
    final = construir_resultado(sesion, doc)
    assert final.estado_analisis is EstadoAnalisis.completado and final.fase_analisis is None


def test_se_borra_al_fallar_el_motor(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    vistas: list = []
    _motor_con_fases(monkeypatch, vistas, fases=(F.preparando,), falla=RuntimeError("motor caido (ficticio)"))
    ingesta_procesamiento.procesar(doc.id)
    sesion.expire_all()
    assert vistas == [F.en_cola, F.preparando]
    assert ingesta_procesamiento.leer_fase(doc.id) is None
    resultado = construir_resultado(sesion, doc)
    assert resultado.estado_analisis is EstadoAnalisis.error and resultado.fase_analisis is None


def test_se_borra_aunque_falle_algo_fuera_del_motor(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    ingesta_procesamiento.fijar_fase(doc.id, F.ocr)

    def revienta(documento_id, tipo_confirmado):
        raise RuntimeError("fallo ficticio antes de terminar")
    monkeypatch.setattr(ingesta_procesamiento, "_procesar", revienta)
    with pytest.raises(RuntimeError):
        ingesta_procesamiento.procesar(doc.id)
    assert ingesta_procesamiento.leer_fase(doc.id) is None


def test_completado_y_error_nunca_llevan_fase_aunque_quede_en_el_registro(sesion, s3_en_procesamiento, folio):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    ingesta_procesamiento.fijar_fase(doc.id, F.extrayendo)
    try:
        for estado in (EstadoAnalisis.completado, EstadoAnalisis.error):
            doc.estado_analisis = estado.value
            sesion.commit()
            assert construir_resultado(sesion, doc).fase_analisis is None
        doc.estado_analisis = EstadoAnalisis.pendiente.value
        sesion.commit()
        assert construir_resultado(sesion, doc).fase_analisis is F.extrayendo
    finally:
        ingesta_procesamiento.borrar_fase(doc.id)


def test_pendiente_sin_entrada_en_el_registro_da_none(sesion, s3_en_procesamiento, folio):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    assert doc.estado_analisis == EstadoAnalisis.pendiente.value
    assert construir_resultado(sesion, doc).fase_analisis is None


def test_el_webhook_no_lleva_fase(sesion, s3_en_procesamiento, folio, monkeypatch):
    sesion.execute(update(Proceso).where(Proceso.nombre == "onboarding")
                   .values(webhook_url="https://integrador.ficticio.example/webhook"))
    sesion.commit()
    doc = _subir(sesion, s3_en_procesamiento, folio)
    enviados = []
    monkeypatch.setattr(webhooks, "enviar_en_segundo_plano",
                        lambda url, evento, folio, datos, **k: enviados.append((evento, datos)))
    vistas: list = []
    _motor_con_fases(monkeypatch, vistas)
    ingesta_procesamiento.procesar(doc.id)
    assert [e for e, _ in enviados] == ["documento.completado"]
    datos = enviados[0][1]
    assert datos.fase_analisis is None and datos.model_dump(mode="json")["fase_analisis"] is None


def test_el_registro_es_seguro_con_hilos():
    ids = [uuid.uuid4() for _ in range(50)]

    def trabajar(i):
        for fase in FaseAnalisis:
            ingesta_procesamiento.fijar_fase(i, fase)
            assert ingesta_procesamiento.leer_fase(i) is fase
        ingesta_procesamiento.borrar_fase(i)
    hilos = [threading.Thread(target=trabajar, args=(i,)) for i in ids]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert all(ingesta_procesamiento.leer_fase(i) is None for i in ids)
