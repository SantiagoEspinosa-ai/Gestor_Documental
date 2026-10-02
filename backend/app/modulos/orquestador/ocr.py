"""
Puerto OCRProvider y adaptador TesseractOCR (ADR-005): unico sitio donde se usa pytesseract.
Preprocesado igual que la linea base de PERSONA_3 (150/153 campos): escala de grises + autocontraste.
Sin enderezado (deskew): la linea base se alcanza sin el (spec, seccion 9).
"""
from __future__ import annotations

import io
import os
from typing import Protocol

from PIL import Image, ImageOps

IDIOMAS_POR_DEFECTO = "spa+eng"


class ErrorOCR(Exception):
    """Tesseract no esta instalado o no pudo leer la imagen."""


class OCRProvider(Protocol):
    def extraer_texto(self, imagen: bytes) -> str: ...


def preprocesar(imagen: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(imagen.convert("L"))


class TesseractOCR:
    def __init__(self, idiomas: str | None = None):
        self.idiomas = idiomas or os.environ.get("TESSERACT_LANG") or IDIOMAS_POR_DEFECTO

    def extraer_texto(self, imagen: bytes) -> str:
        import pytesseract  # aqui y no arriba: el modulo se puede importar sin Tesseract instalado

        try:
            with Image.open(io.BytesIO(imagen)) as original:
                return pytesseract.image_to_string(preprocesar(original), lang=self.idiomas)
        except pytesseract.TesseractNotFoundError as e:
            raise ErrorOCR("Tesseract no esta instalado (en Docker viene en la imagen del backend)") from e
        except (pytesseract.TesseractError, OSError) as e:
            raise ErrorOCR(f"Tesseract no pudo leer la imagen: {e}") from e
