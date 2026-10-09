"""Tests de orquestador/ocr.py. Los que usan Tesseract se saltan si no esta instalado (fuera de Docker)."""
import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.modulos.orquestador.ocr import ErrorOCR, TesseractOCR, preprocesar

con_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no instalado")


def imagen_con_texto(texto: str) -> bytes:
    imagen = Image.new("RGB", (1400, 220), (235, 235, 235))
    ImageDraw.Draw(imagen).text((40, 60), texto, font=ImageFont.load_default(size=72), fill=(30, 30, 30))
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


@con_tesseract
def test_lee_texto_de_una_imagen():
    texto = TesseractOCR().extraer_texto(imagen_con_texto("MUESTRA 12345 EJEMPLO"))
    assert "MUESTRA" in texto and "12345" in texto and "EJEMPLO" in texto


def test_preprocesado_gris_y_autocontraste():
    gris = Image.new("RGB", (10, 10), (120, 120, 120))
    gris.putpixel((0, 0), (100, 100, 100))
    gris.putpixel((1, 1), (150, 150, 150))
    resultado = preprocesar(gris)
    assert resultado.mode == "L" and resultado.getextrema() == (0, 255)


def test_idiomas(monkeypatch):
    monkeypatch.delenv("TESSERACT_LANG", raising=False)
    assert TesseractOCR().idiomas == "spa+eng"
    monkeypatch.setenv("TESSERACT_LANG", "eng")
    assert TesseractOCR().idiomas == "eng"
    assert TesseractOCR("spa").idiomas == "spa"


def test_sin_tesseract_lanza_error_ocr(monkeypatch):
    import pytesseract

    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/no/existe/tesseract")
    with pytest.raises(ErrorOCR, match="no esta instalado"):
        TesseractOCR().extraer_texto(imagen_con_texto("X"))


def test_imagen_ilegible_lanza_error_ocr():
    with pytest.raises(ErrorOCR, match="no pudo leer"):
        TesseractOCR().extraer_texto(b"esto no es una imagen")
