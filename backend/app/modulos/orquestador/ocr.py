"""
Puerto OCRProvider y adaptador TesseractOCR (ADR-005): unico sitio donde se usa pytesseract.
Preprocesado igual que la linea base de PERSONA_3 (150/153 campos): escala de grises + autocontraste.
Sin enderezado (deskew): la linea base se alcanza sin el (spec, seccion 9).
Fotos con OCR pobre (2026-10-09): si el primer intento saca menos de `UMBRAL_SEGUNDO_INTENTO_OCR` caracteres
validos (150 por defecto; distinto del umbral de texto de la modalidad, 30), se hace un segundo intento con
`preprocesar_foto` (mas resolucion si la imagen es pequena, binarizacion adaptativa y quitar ruido) y se queda
el de mas calidad (`calidad_ocr`: marcadores de clasificacion de las fichas, y despues palabras reconocibles).
Si empatan, el primero. El primer intento no cambia.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
from typing import Protocol

from PIL import Image, ImageChops, ImageFilter, ImageOps

from app.modulos.configuracion import servicio as configuracion
from app.modulos.orquestador.modalidad import _limite

IDIOMAS_POR_DEFECTO = "spa+eng"
# Segundo intento (fotos con OCR pobre). Con 30 (el umbral de texto de la modalidad) no se disparaba en ninguna
# foto de los fixtures; con 150 se dispara en 10 de 38 paginas y mejora 5 (medido el 2026-10-09)
UMBRAL_SEGUNDO_INTENTO_OCR_POR_DEFECTO = 150
ANCHO_MINIMO_FOTO = 1600     # px: por debajo, la imagen se amplia al doble antes del OCR
RADIO_FONDO = 25             # px de la media que estima el fondo local (binarizacion adaptativa)
CONTRASTE_MINIMO = 20        # niveles de gris por debajo del fondo local para contar como tinta
# Parametros medidos con los fixtures de foto (2026-10-09): 15 o 30 de contraste, o la mediana antes de
# binarizar, empeoraban; la mediana despues de binarizar quita las motas sueltas y mejora.


class ErrorOCR(Exception):
    """Tesseract no esta instalado o no pudo leer la imagen."""


class OCRProvider(Protocol):
    def extraer_texto(self, imagen: bytes) -> str: ...


def preprocesar(imagen: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(imagen.convert("L"))


def preprocesar_foto(imagen: Image.Image) -> Image.Image:
    """Segundo intento para fotos con OCR pobre: gris, ampliado x2 si es pequena, binarizada con un umbral
    adaptativo (cada pixel frente a la media de su entorno: aguanta luz desigual y fondos de seguridad mejor
    que un umbral fijo) y sin ruido (mediana sobre la imagen binarizada)."""
    gris = ImageOps.autocontrast(imagen.convert("L"))
    if gris.width < ANCHO_MINIMO_FOTO:
        gris = gris.resize((gris.width * 2, gris.height * 2), Image.LANCZOS)
    fondo = gris.filter(ImageFilter.BoxBlur(RADIO_FONDO))
    tinta = ImageChops.subtract(fondo, gris)  # cuanto mas oscuro que su entorno, mas tinta
    binaria = tinta.point(lambda v: 0 if v > CONTRASTE_MINIMO else 255)
    return binaria.filter(ImageFilter.MedianFilter(3))


def caracteres_validos(texto: str) -> int:
    return sum(c.isalnum() for c in texto)


def umbral_segundo_intento() -> int:
    """Caracteres validos por debajo de los que se hace el segundo intento (`UMBRAL_SEGUNDO_INTENTO_OCR`)."""
    return _limite("UMBRAL_SEGUNDO_INTENTO_OCR", UMBRAL_SEGUNDO_INTENTO_OCR_POR_DEFECTO)


def _normalizar(texto: str) -> str:
    """Mayusculas y sin acentos, como el texto con el que el motor busca los marcadores."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _palabra_reconocible(palabra: str) -> bool:
    """3 letras o mas, con vocal y consonante: descarta el ruido tipico del OCR (`III`, `EE`, `~|`)."""
    return len(palabra) >= 3 and any(c in "AEIOU" for c in palabra) and any(c not in "AEIOU" for c in palabra)


def calidad_ocr(texto: str) -> tuple[int, int]:
    """(marcadores de clasificacion de la ficha que mas encuentra, palabras reconocibles). Se compara en ese
    orden: los marcadores son lo que el motor usa para clasificar y verificar. Si las fichas no se pueden
    cargar, solo cuentan las palabras."""
    normal = _normalizar(texto)
    try:
        fichas = configuracion.listar()
    except configuracion.ErrorConfiguracion:
        fichas = []
    marcadores = max((sum(re.search(m, normal, configuracion.FLAGS_MARCADORES) is not None
                          for m in f.marcadores_clasificacion) for f in fichas), default=0)
    palabras = sum(_palabra_reconocible(p) for p in re.findall(r"[A-Z]+", normal))
    return marcadores, palabras


class TesseractOCR:
    def __init__(self, idiomas: str | None = None):
        self.idiomas = idiomas or os.environ.get("TESSERACT_LANG") or IDIOMAS_POR_DEFECTO

    def extraer_texto(self, imagen: bytes) -> str:
        import pytesseract  # aqui y no arriba: el modulo se puede importar sin Tesseract instalado

        try:
            with Image.open(io.BytesIO(imagen)) as original:
                texto = pytesseract.image_to_string(preprocesar(original), lang=self.idiomas)
                if caracteres_validos(texto) >= umbral_segundo_intento():
                    return texto
                # OCR pobre: segundo intento con el preprocesado de foto; gana el de mas calidad (empate: el 1o)
                segundo = pytesseract.image_to_string(preprocesar_foto(original), lang=self.idiomas)
                return segundo if calidad_ocr(segundo) > calidad_ocr(texto) else texto
        except pytesseract.TesseractNotFoundError as e:
            raise ErrorOCR("Tesseract no esta instalado (en Docker viene en la imagen del backend)") from e
        except (pytesseract.TesseractError, OSError) as e:
            raise ErrorOCR(f"Tesseract no pudo leer la imagen: {e}") from e
