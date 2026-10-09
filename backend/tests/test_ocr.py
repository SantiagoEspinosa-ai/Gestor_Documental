"""Tests de orquestador/ocr.py. Los que usan Tesseract se saltan si no esta instalado (fuera de Docker)."""
import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.modulos.orquestador import ocr
from app.modulos.orquestador.ocr import (
    ErrorOCR,
    TesseractOCR,
    calidad_ocr,
    preprocesar,
    preprocesar_foto,
    umbral_segundo_intento,
)

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


# --- Segundo intento para fotos con OCR pobre (2026-10-09) ---

def test_umbral_segundo_intento_configurable(monkeypatch):
    monkeypatch.delenv("UMBRAL_SEGUNDO_INTENTO_OCR", raising=False)
    assert umbral_segundo_intento() == 150
    monkeypatch.setenv("UMBRAL_SEGUNDO_INTENTO_OCR", "80")
    assert umbral_segundo_intento() == 80
    for malo in ("0", "-5", "abc"):
        monkeypatch.setenv("UMBRAL_SEGUNDO_INTENTO_OCR", malo)
        with pytest.raises(ValueError, match="UMBRAL_SEGUNDO_INTENTO_OCR"):
            umbral_segundo_intento()


def test_calidad_marcadores_antes_que_palabras():
    # Marcadores de la credencial (ficticia): CURP, VIGENCIA, DOMICILIO; sin acentos ni mayusculas en el original
    con_marcadores = "Curp\nVigencia 2030\nDomicilio"
    muchas_palabras = "LOREM IPSUM DOLOR AMET CONSECTETUR ADIPISCING ELIT SEDDO EIUSMOD TEMPOR"
    assert calidad_ocr(con_marcadores)[0] == 3
    assert calidad_ocr(muchas_palabras) == (0, 10)
    assert calidad_ocr(con_marcadores) > calidad_ocr(muchas_palabras)


def test_calidad_ignora_ruido():
    assert calidad_ocr("III EE ~| ,,, 0O0 SSS") == (0, 0)


def test_preprocesado_de_foto_amplia_y_binariza():
    pequena = Image.new("RGB", (400, 100), (200, 200, 200))
    ImageDraw.Draw(pequena).text((10, 30), "MUESTRA", fill=(20, 20, 20))
    resultado = preprocesar_foto(pequena)
    assert resultado.size == (800, 200) and set(resultado.histogram()[1:255]) == {0}
    grande = Image.new("RGB", (1700, 100), (200, 200, 200))
    assert preprocesar_foto(grande).size == (1700, 100)


class _Tesseract:
    """Simula pytesseract.image_to_string: devuelve los textos en orden y cuenta las llamadas."""

    def __init__(self, *textos):
        self.textos, self.llamadas = list(textos), 0

    def __call__(self, imagen, lang=None):
        self.llamadas += 1
        return self.textos.pop(0)


def _con_tesseract_simulado(monkeypatch, *textos):
    import pytesseract

    falso = _Tesseract(*textos)
    monkeypatch.setattr(pytesseract, "image_to_string", falso)
    monkeypatch.delenv("UMBRAL_SEGUNDO_INTENTO_OCR", raising=False)
    return falso


SUFICIENTE = "CREDENCIAL PARA VOTAR " + "EJEMPLO " * 25   # > 150 caracteres validos


def test_con_texto_suficiente_no_hay_segundo_intento(monkeypatch):
    falso = _con_tesseract_simulado(monkeypatch, SUFICIENTE, "no se usa")
    assert TesseractOCR().extraer_texto(imagen_con_texto("X")) == SUFICIENTE
    assert falso.llamadas == 1


def test_segundo_intento_gana_si_tiene_mas_calidad(monkeypatch):
    falso = _con_tesseract_simulado(monkeypatch, "ruido III", "CURP VIGENCIA DOMICILIO")
    assert TesseractOCR().extraer_texto(imagen_con_texto("X")) == "CURP VIGENCIA DOMICILIO"
    assert falso.llamadas == 2


def test_mas_caracteres_sin_mas_calidad_gana_el_primero(monkeypatch):
    primero = "CURP VIGENCIA"
    segundo = "LOREM IPSUM DOLOR AMET CONSECTETUR ADIPISCING ELIT"  # mas caracteres, sin marcadores
    _con_tesseract_simulado(monkeypatch, primero, segundo)
    assert TesseractOCR().extraer_texto(imagen_con_texto("X")) == primero


def test_empate_gana_el_primero(monkeypatch):
    _con_tesseract_simulado(monkeypatch, "CURP MUESTRA", "CURP EJEMPLO")
    assert TesseractOCR().extraer_texto(imagen_con_texto("X")) == "CURP MUESTRA"


def test_calidad_sin_fichas_cuenta_solo_palabras(monkeypatch):
    def falla():
        raise ocr.configuracion.ErrorConfiguracion("sin fichas")

    monkeypatch.setattr(ocr.configuracion, "listar", falla)
    assert calidad_ocr("CURP VIGENCIA DOMICILIO") == (0, 3)
