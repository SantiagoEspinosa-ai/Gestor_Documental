"""Tests de orquestador/preparador.py con un OCR falso: rapidos y sin Tesseract. Datos inventados."""
import io
import logging
import uuid

import pymupdf
import pytest
from PIL import Image

from app.modulos.motor_ia.interfaces import Modalidad
from app.modulos.orquestador import servicio
from app.modulos.orquestador.modalidad import FormatoNoSoportado
from app.modulos.orquestador.ocr import ErrorOCR
from app.modulos.orquestador.preparador import DPI_DIGITAL, DPI_ESCANEADO, preparar

LINEAS = ["DOCUMENTO DE MUESTRA SIN VALIDEZ", "Nombre: ANA EJEMPLO PRUEBA", "Numero: X1234567P"]


class OCRFalso:
    def __init__(self, texto: str = "TEXTO OCR", error: bool = False):
        self.texto, self.error, self.llamadas = texto, error, 0

    def extraer_texto(self, imagen: bytes) -> str:
        self.llamadas += 1
        Image.open(io.BytesIO(imagen)).verify()  # recibe un PNG valido
        if self.error:
            raise ErrorOCR("simulado")
        return f"{self.texto} {self.llamadas}"


def _png(ancho=300, alto=200, modo="RGB") -> bytes:
    salida = io.BytesIO()
    Image.new(modo, (ancho, alto), (200, 200, 200) if modo == "RGB" else (200, 200, 200, 128)).save(salida, "PNG")
    return salida.getvalue()


def _pdf(paginas: list[str]) -> bytes:
    documento = pymupdf.open()
    for tipo in paginas:
        p = documento.new_page()  # A4: 595 x 842 puntos
        if tipo == "texto":
            for i, linea in enumerate(LINEAS):
                p.insert_text((72, 72 + 20 * i), linea)
        else:
            p.insert_image(pymupdf.Rect(72, 72, 372, 272), stream=_png())
    contenido = documento.tobytes()
    documento.close()
    return contenido


def _ancho_png(png: bytes) -> int:
    return Image.open(io.BytesIO(png)).width


def test_pdf_digital_multipagina():
    ocr = OCRFalso()
    doc = preparar(_pdf(["texto", "texto"]), "documento.pdf", "pasaporte", ocr=ocr)
    assert doc.modalidad is Modalidad.pdf_digital and doc.tipo_documental_declarado == "pasaporte"
    assert [p.numero for p in doc.paginas] == [1, 2]
    assert all("ANA EJEMPLO PRUEBA" in p.texto for p in doc.paginas)
    assert _ancho_png(doc.paginas[0].imagen_png) == round(595 * DPI_DIGITAL / 72)
    assert ocr.llamadas == 0 and doc.contexto_rag == []


def test_pdf_escaneado_usa_ocr_en_cada_pagina():
    ocr = OCRFalso()
    doc = preparar(_pdf(["imagen", "imagen"]), "escaneo.pdf", ocr=ocr)
    assert doc.modalidad is Modalidad.pdf_escaneado
    assert [p.texto for p in doc.paginas] == ["TEXTO OCR 1", "TEXTO OCR 2"]
    assert _ancho_png(doc.paginas[0].imagen_png) == round(595 * DPI_ESCANEADO / 72)


def test_pdf_mixto_usa_la_capa_de_texto_donde_la_hay():
    ocr = OCRFalso()
    doc = preparar(_pdf(["texto", "imagen", "texto"]), "mixto.pdf", ocr=ocr)
    assert doc.modalidad is Modalidad.pdf_escaneado and ocr.llamadas == 1
    assert "ANA EJEMPLO PRUEBA" in doc.paginas[0].texto and "ANA EJEMPLO PRUEBA" in doc.paginas[2].texto
    assert doc.paginas[1].texto == "TEXTO OCR 1"
    assert [p.numero for p in doc.paginas] == [1, 2, 3]


def test_imagen_png_con_transparencia():
    doc = preparar(_png(modo="RGBA"), "foto.png", ocr=OCRFalso())
    assert doc.modalidad is Modalidad.imagen and len(doc.paginas) == 1
    pagina = doc.paginas[0]
    assert pagina.numero == 1 and pagina.texto == "TEXTO OCR 1"
    assert Image.open(io.BytesIO(pagina.imagen_png)).mode == "RGB"


def test_jpg_se_orienta_segun_exif():
    imagen = Image.new("RGB", (400, 200), (180, 180, 180))
    exif = imagen.getexif()
    exif[0x0112] = 6  # Orientation: girada 90 grados, como una foto de movil en vertical
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    doc = preparar(salida.getvalue(), "foto.jpg", ocr=OCRFalso())
    assert Image.open(io.BytesIO(doc.paginas[0].imagen_png)).size == (200, 400)


def test_sin_ocr_las_paginas_quedan_sin_texto_y_avisa_una_vez(caplog):
    caplog.set_level(logging.WARNING)
    doc = preparar(_pdf(["imagen", "imagen"]), "escaneo_personal.pdf", ocr=OCRFalso(error=True))
    assert [p.texto for p in doc.paginas] == [None, None]
    assert all(p.imagen_png for p in doc.paginas)
    avisos = [r for r in caplog.records if "OCR no disponible" in r.getMessage()]
    assert len(avisos) == 1 and "escaneo_personal" not in caplog.text


def test_identificador():
    assert preparar(_png(), "a.png", identificador="doc-1", ocr=OCRFalso()).identificador_unico_documento == "doc-1"
    generado = preparar(_png(), "a.png", ocr=OCRFalso()).identificador_unico_documento
    assert uuid.UUID(generado).version == 4


def test_jpeg_corrupto():
    with pytest.raises(FormatoNoSoportado, match="imagen"):
        preparar(b"\xff\xd8\xff" + b"basura" * 10, "foto.jpg", ocr=OCRFalso())


def test_servicio_expone_la_api_publica():
    assert servicio.preparar is preparar
    assert servicio.detectar(_png(), "x.png") is Modalidad.imagen
    assert servicio.FormatoNoSoportado is FormatoNoSoportado
