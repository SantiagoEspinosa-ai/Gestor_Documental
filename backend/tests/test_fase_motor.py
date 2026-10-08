"""Fase del analisis (ADR-014): avisos del motor y del orquestador. Proveedores y enrutador falsos: sin red ni
modelo. Datos inventados."""
import logging

import pymupdf

from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.motor_ia.servicio import analizar, avisar_fase
from app.modulos.orquestador import procesamiento as orquestador
from app.schemas.resultado import EstadoAnalisis, FaseAnalisis
from tests.test_servicio_motor import (
    AHORA,
    INCOMPLETOS,
    REFERENCIA,
    TEXTO_PASAPORTE,
    EnrutadorFalso,
    ProveedorConReclasificacion,
    ProveedorConVision,
    ProveedorFalso,
    doc_con_imagenes,
    documento,
)

F = FaseAnalisis


def fases_de(principal, doc, **kwargs):
    fases: list[FaseAnalisis] = []
    analisis = analizar(doc, folio="CLI-2026-000000", referencia=REFERENCIA, enrutador=EnrutadorFalso(principal),
                        ahora=AHORA, al_avanzar=fases.append, **kwargs)
    return fases, analisis


# --- Motor: orden de las fases en cada camino ---

def test_camino_texto():
    fases, _ = fases_de(ProveedorFalso("ollama"), documento())
    assert fases == [F.clasificando, F.extrayendo]


def test_vision_directa_sin_texto_suficiente():
    doc = DocumentoPreparado("id", Modalidad.imagen, [Pagina(1, texto=None, imagen_png=b"png-ficticio")], "pasaporte")
    fases, _ = fases_de(ProveedorFalso("ollama"), doc)
    assert fases == [F.vision, F.vision]  # clasificacion y extraccion, las dos con vision


def test_reclasificacion_con_vision():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", tipo_vision="pasaporte")
    fases, _ = fases_de(p, doc_con_imagenes(declarado=None))
    assert p.reclasificaciones  # el camino es el de la reclasificacion
    assert fases == [F.clasificando, F.vision, F.vision]  # reclasifica y extrae con vision (OCR pobre)


def test_reintento_con_vision():
    p = ProveedorConVision("ollama", datos=INCOMPLETOS)
    fases, _ = fases_de(p, doc_con_imagenes())
    assert p.pedidos_vision  # el camino es el del reintento
    assert fases == [F.clasificando, F.extrayendo, F.vision]


def test_tipo_confirmado_no_clasifica():
    fases, _ = fases_de(ProveedorFalso("ollama"), documento(), tipo_confirmado="pasaporte")
    assert fases == [F.extrayendo]


def test_un_callback_que_lanza_no_cambia_el_resultado(caplog):
    def falla(fase):
        raise RuntimeError("ANA EJEMPLO PRUEBA")  # un mensaje con datos no debe llegar al log

    referencia = analizar(documento(), folio="CLI-2026-000000", referencia=REFERENCIA,
                          enrutador=EnrutadorFalso(ProveedorFalso("ollama")), ahora=AHORA)
    with caplog.at_level(logging.DEBUG):
        con_fallo = analizar(documento(), folio="CLI-2026-000000", referencia=REFERENCIA,
                             enrutador=EnrutadorFalso(ProveedorFalso("ollama")), ahora=AHORA, al_avanzar=falla)
    assert con_fallo.resultado.model_dump() == referencia.resultado.model_dump()
    assert "ANA EJEMPLO PRUEBA" not in caplog.text and "RuntimeError" in caplog.text


def test_sin_callback_todo_sigue_igual():
    sin = analizar(documento(), folio="CLI-2026-000000", referencia=REFERENCIA,
                   enrutador=EnrutadorFalso(ProveedorFalso("ollama")), ahora=AHORA)
    con = analizar(documento(), folio="CLI-2026-000000", referencia=REFERENCIA,
                   enrutador=EnrutadorFalso(ProveedorFalso("ollama")), ahora=AHORA, al_avanzar=lambda f: None)
    assert sin.resultado.model_dump() == con.resultado.model_dump()
    assert sin.resultado.fase_analisis is None  # el motor nunca la devuelve


def test_avisar_fase_sin_callback_no_hace_nada():
    avisar_fase(None, F.ocr)


# --- Orquestador: preparando y ocr antes que el motor ---

def _pdf_digital() -> bytes:
    pdf = pymupdf.open()
    pagina = pdf.new_page()
    for i, linea in enumerate(TEXTO_PASAPORTE.splitlines()):
        pagina.insert_text((72, 72 + 14 * i), linea)
    return pdf.tobytes()


def test_procesar_documento_avisa_todas_las_fases_en_orden():
    fases: list[FaseAnalisis] = []
    resultado, _ = orquestador.procesar_documento(
        _pdf_digital(), identificador="00000000-0000-4000-8000-000000000001", nombre_archivo="ficticio.pdf",
        tipo_declarado="pasaporte", folio="CLI-2026-000000", referencia=REFERENCIA,
        enrutador=EnrutadorFalso(ProveedorFalso("ollama")), ahora=AHORA, al_avanzar=fases.append)
    assert fases == [F.preparando, F.ocr, F.clasificando, F.extrayendo]
    assert resultado.estado_analisis is EstadoAnalisis.completado and resultado.fase_analisis is None
