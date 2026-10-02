"""
Prepara un documento para el motor de IA: modalidad, texto y render de cada pagina (Contrato 3).
- pdf_digital: capa de texto de cada pagina + PNG a 150 dpi.
- pdf_escaneado: PNG a 200 dpi; por pagina, capa de texto si supera el umbral (PDF mixto) y OCR si no.
- imagen: la propia imagen (orientada segun EXIF, en PNG) + OCR.
Sin Tesseract, las paginas que necesitaban OCR quedan con texto None y se avisa en el log.
"""
from __future__ import annotations

import io
import logging
import uuid

import pymupdf
from PIL import Image, ImageOps

from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.orquestador.modalidad import UMBRAL_CARACTERES_POR_PAGINA, FormatoNoSoportado, detectar
from app.modulos.orquestador.ocr import ErrorOCR, OCRProvider, TesseractOCR

logger = logging.getLogger(__name__)

DPI_DIGITAL = 150
DPI_ESCANEADO = 200


def preparar(contenido: bytes, nombre: str, tipo_declarado: str | None = None, *,
             identificador: str | None = None, ocr: OCRProvider | None = None) -> DocumentoPreparado:
    modalidad = detectar(contenido, nombre)
    lector = _LectorOCR(ocr if ocr is not None else TesseractOCR())
    if modalidad is Modalidad.imagen:
        paginas = [_pagina_imagen(contenido, lector)]
    else:
        paginas = _paginas_pdf(contenido, modalidad, lector)
    return DocumentoPreparado(
        identificador_unico_documento=identificador or str(uuid.uuid4()),
        modalidad=modalidad,
        paginas=paginas,
        tipo_documental_declarado=tipo_declarado,
    )


class _LectorOCR:
    """Envuelve el OCR: si falla (p. ej. sin Tesseract) devuelve None y avisa una sola vez por documento."""

    def __init__(self, ocr: OCRProvider):
        self._ocr = ocr
        self._avisado = False

    def leer(self, png: bytes) -> str | None:
        try:
            return self._ocr.extraer_texto(png)
        except ErrorOCR as e:
            if not self._avisado:
                # Sin el nombre del archivo: puede contener datos personales.
                logger.warning("OCR no disponible; las paginas sin texto quedan sin texto: %s", e)
                self._avisado = True
            return None


def _paginas_pdf(contenido: bytes, modalidad: Modalidad, lector: _LectorOCR) -> list[Pagina]:
    dpi = DPI_DIGITAL if modalidad is Modalidad.pdf_digital else DPI_ESCANEADO
    paginas = []
    with pymupdf.open(stream=contenido, filetype="pdf") as documento:
        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text()
            png = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False).tobytes("png")
            if modalidad is Modalidad.pdf_escaneado and len("".join(texto.split())) < UMBRAL_CARACTERES_POR_PAGINA:
                texto = lector.leer(png)
            paginas.append(Pagina(numero=numero, texto=texto, imagen_png=png))
    return paginas


def _pagina_imagen(contenido: bytes, lector: _LectorOCR) -> Pagina:
    try:
        with Image.open(io.BytesIO(contenido)) as original:
            imagen = ImageOps.exif_transpose(original).convert("RGB")
    except OSError as e:
        raise FormatoNoSoportado("imagen corrupta o ilegible") from e
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    png = salida.getvalue()
    return Pagina(numero=1, texto=lector.leer(png), imagen_png=png)
