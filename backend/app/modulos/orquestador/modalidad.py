"""
Deteccion de la modalidad de un documento: pdf_digital | pdf_escaneado | imagen (Contrato 3).
El contenido manda sobre la extension: se mira la firma de los primeros bytes.
"""
from __future__ import annotations

import logging
from pathlib import PurePath

import pymupdf

from app.modulos.motor_ia.interfaces import Modalidad

logger = logging.getLogger(__name__)

# Una pagina cuenta como "con texto" si tiene al menos estos caracteres (sin espacios) extraibles.
UMBRAL_CARACTERES_POR_PAGINA = 30

_FIRMAS = {
    b"%PDF-": "pdf",
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
}
_EXTENSIONES = {"pdf": "pdf", "png": "png", "jpg": "jpeg", "jpeg": "jpeg"}


class FormatoNoSoportado(ValueError):
    """El archivo no es un PDF, PNG o JPEG legible."""


def _formato_por_contenido(contenido: bytes) -> str | None:
    for firma, formato in _FIRMAS.items():
        if contenido.startswith(firma):
            return formato
    return None


def caracteres_por_pagina(contenido: bytes) -> list[int]:
    """Caracteres de texto extraible (sin espacios) de cada pagina de un PDF, en orden."""
    try:
        documento = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception as e:  # PyMuPDF lanza tipos distintos segun la version para un PDF danado
        raise FormatoNoSoportado("PDF corrupto o ilegible") from e
    with documento:
        if documento.needs_pass:
            raise FormatoNoSoportado("PDF protegido con contrasena")
        if documento.page_count == 0:
            raise FormatoNoSoportado("PDF sin paginas")
        return [len("".join(pagina.get_text().split())) for pagina in documento]


def detectar(contenido: bytes, nombre: str) -> Modalidad:
    """Devuelve la modalidad del documento.

    - PDF con al menos `UMBRAL_CARACTERES_POR_PAGINA` en todas sus paginas -> pdf_digital.
    - PDF con alguna pagina por debajo del umbral (escaneado o mixto) -> pdf_escaneado.
    - PNG o JPEG -> imagen.
    Formato desconocido, PDF corrupto o cifrado -> FormatoNoSoportado.
    """
    formato = _formato_por_contenido(contenido)
    if formato is None:
        raise FormatoNoSoportado("formato no soportado: se admiten PDF, PNG y JPEG")

    extension = PurePath(nombre).suffix.lower().lstrip(".")
    if _EXTENSIONES.get(extension) != formato:
        # Sin el nombre del archivo en el log: puede contener datos personales.
        logger.warning("la extension '.%s' no coincide con el contenido (%s); manda el contenido", extension, formato)

    if formato != "pdf":
        return Modalidad.imagen
    if all(n >= UMBRAL_CARACTERES_POR_PAGINA for n in caracteres_por_pagina(contenido)):
        return Modalidad.pdf_digital
    return Modalidad.pdf_escaneado
