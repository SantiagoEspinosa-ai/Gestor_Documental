"""Tests de los limites de paginas y pixeles del orquestador (seguridad): un PDF con miles de paginas o una pagina
gigante se rechazan con DocumentoDemasiadoGrande antes de renderizar o decodificar nada. Los documentos se generan
en el test; OCR falso, sin Tesseract."""
import io
import time

import pymupdf
import pytest
from PIL import Image

from app.modulos.orquestador import servicio
from app.modulos.orquestador.modalidad import (
    MAX_PAGINAS_DOCUMENTO_POR_DEFECTO,
    MAX_PIXELES_PAGINA_POR_DEFECTO,
    DocumentoDemasiadoGrande,
    FormatoNoSoportado,
    detectar,
)
from app.modulos.orquestador.preparador import preparar


class OCRFalso:
    def __init__(self):
        self.llamadas = 0

    def extraer_texto(self, imagen: bytes) -> str:
        self.llamadas += 1
        return "TEXTO OCR"


@pytest.fixture(autouse=True)
def _limites_por_defecto(monkeypatch):
    monkeypatch.delenv("MAX_PAGINAS_DOCUMENTO", raising=False)
    monkeypatch.delenv("MAX_PIXELES_PAGINA", raising=False)


def _pdf(n_paginas: int, ancho: float = 100, alto: float = 100) -> bytes:  # paginas pequenas: render rapido
    documento = pymupdf.open()
    for _ in range(n_paginas):
        documento.new_page(width=ancho, height=alto)  # vacias: escaneado, sin capa de texto
    return documento.tobytes()


def _png(ancho: int, alto: int) -> bytes:
    salida = io.BytesIO()
    Image.new("1", (ancho, alto)).save(salida, "PNG")  # 1 bit por pixel: poca memoria al generarla
    return salida.getvalue()


def test_limites_por_defecto():
    assert MAX_PAGINAS_DOCUMENTO_POR_DEFECTO == 20 and MAX_PIXELES_PAGINA_POR_DEFECTO == 50_000_000


# --- Paginas ---

def test_pdf_con_miles_de_paginas_se_rechaza_sin_renderizar():
    ocr = OCRFalso()
    inicio = time.perf_counter()
    with pytest.raises(DocumentoDemasiadoGrande, match="2000 paginas; el maximo es 20"):
        preparar(_pdf(2000), "muchas.pdf", ocr=ocr)
    assert ocr.llamadas == 0 and time.perf_counter() - inicio < 10


def test_detectar_tambien_rechaza_antes_de_recorrer_las_paginas():
    with pytest.raises(DocumentoDemasiadoGrande):
        detectar(_pdf(21), "muchas.pdf")


def test_pdf_en_el_limite_de_paginas_se_procesa():
    doc = preparar(_pdf(20), "limite.pdf", ocr=OCRFalso())
    assert len(doc.paginas) == 20


def test_limite_de_paginas_configurable(monkeypatch):
    monkeypatch.setenv("MAX_PAGINAS_DOCUMENTO", "2")
    with pytest.raises(DocumentoDemasiadoGrande, match="el maximo es 2"):
        preparar(_pdf(3), "tres.pdf", ocr=OCRFalso())
    monkeypatch.setenv("MAX_PAGINAS_DOCUMENTO", "30")
    assert len(preparar(_pdf(25), "veinticinco.pdf", ocr=OCRFalso()).paginas) == 25


# --- Pixeles ---

def test_pagina_pdf_gigante_se_rechaza_sin_renderizar():
    # 14 400 x 14 400 puntos (el maximo de un PDF) a 200 dpi: 40 000 x 40 000 px = 1 600 MP
    ocr = OCRFalso()
    with pytest.raises(DocumentoDemasiadoGrande, match="MAX_PIXELES_PAGINA"):
        preparar(_pdf(1, 14400, 14400), "gigante.pdf", ocr=ocr)
    assert ocr.llamadas == 0


def test_imagen_enorme_se_rechaza_antes_de_decodificarla():
    # 8000 x 8000 = 64 MP > 50 MP
    ocr = OCRFalso()
    with pytest.raises(DocumentoDemasiadoGrande, match="8000 x 8000 px supera 50000000"):
        preparar(_png(8000, 8000), "enorme.png", ocr=ocr)
    assert ocr.llamadas == 0


def test_bomba_de_descompresion_de_pillow_es_documento_demasiado_grande(monkeypatch):
    # Pillow rechaza al abrir mas de 2 x MAX_IMAGE_PIXELS; se simula con un limite pequeno
    monkeypatch.setenv("MAX_PIXELES_PAGINA", str(10**9))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(DocumentoDemasiadoGrande, match="Pillow"):
        preparar(_png(100, 100), "bomba.png", ocr=OCRFalso())


def test_limite_de_pixeles_configurable(monkeypatch):
    monkeypatch.setenv("MAX_PIXELES_PAGINA", "10000")
    with pytest.raises(DocumentoDemasiadoGrande):
        preparar(_png(101, 100), "foto.png", ocr=OCRFalso())
    assert len(preparar(_png(100, 100), "foto.png", ocr=OCRFalso()).paginas) == 1  # justo en el limite


def test_foto_de_movil_de_48_mp_cabe_por_defecto():
    # Solo la comprobacion, sin decodificar: 8000 x 6000 = 48 MP
    from app.modulos.orquestador.modalidad import comprobar_pixeles
    comprobar_pixeles(8000, 6000)


# --- Rechazo controlado y configuracion ---

def test_es_un_formato_no_soportado_y_lo_exporta_el_servicio():
    # La plataforma y el CLI ya tratan FormatoNoSoportado (documento en error / salida 2)
    assert issubclass(DocumentoDemasiadoGrande, FormatoNoSoportado)
    assert servicio.DocumentoDemasiadoGrande is DocumentoDemasiadoGrande


def test_procesar_documento_rechaza_sin_llamar_al_motor(monkeypatch):
    with pytest.raises(DocumentoDemasiadoGrande):
        servicio.procesar_documento(_pdf(50), identificador="doc-1", nombre_archivo="muchas.pdf", tipo_declarado=None,
                                    folio="ONB-2026-000001", referencia=None)


@pytest.mark.parametrize("variable", ["MAX_PAGINAS_DOCUMENTO", "MAX_PIXELES_PAGINA"])
@pytest.mark.parametrize("valor", ["0", "-1", "abc", "1.5"])
def test_limite_invalido_es_error_de_configuracion(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ValueError, match=variable):
        preparar(_pdf(1) if variable == "MAX_PAGINAS_DOCUMENTO" else _png(10, 10), "doc", ocr=OCRFalso())
