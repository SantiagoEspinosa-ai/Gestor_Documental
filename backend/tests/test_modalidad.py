"""Tests del detector de modalidad (orquestador). Los archivos se generan aqui con datos inventados."""
import io

import pymupdf
import pytest
from PIL import Image

from app.modulos.motor_ia.interfaces import Modalidad
from app.modulos.orquestador.modalidad import (
    UMBRAL_CARACTERES_POR_PAGINA,
    FormatoNoSoportado,
    caracteres_por_pagina,
    detectar,
)

TEXTO_PAGINA = [
    "DOCUMENTO DE MUESTRA SIN VALIDEZ",
    "Nombre: ANA EJEMPLO PRUEBA",
    "Numero: X1234567P",
]


def _png(color=(200, 200, 200)) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (120, 80), color).save(salida, format="PNG")
    return salida.getvalue()


def _jpg() -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (120, 80), (180, 180, 180)).save(salida, format="JPEG")
    return salida.getvalue()


def _pdf(paginas: list[str], **opciones_guardado) -> bytes:
    """Una pagina por elemento: 'texto' (lineas legibles), 'imagen' (solo una imagen) o un texto literal."""
    documento = pymupdf.open()
    for pagina in paginas:
        p = documento.new_page()
        if pagina == "texto":
            for i, linea in enumerate(TEXTO_PAGINA):
                p.insert_text((72, 72 + 20 * i), linea)
        elif pagina == "imagen":
            p.insert_image(pymupdf.Rect(72, 72, 372, 272), stream=_png())
        else:
            p.insert_text((72, 72), pagina)
    contenido = documento.tobytes(**opciones_guardado)
    documento.close()
    return contenido


# --- PDF ---

def test_pdf_con_texto_es_digital():
    assert detectar(_pdf(["texto"]), "documento.pdf") is Modalidad.pdf_digital


def test_pdf_multipagina_con_texto_es_digital():
    contenido = _pdf(["texto", "texto", "texto"])
    assert len(caracteres_por_pagina(contenido)) == 3
    assert detectar(contenido, "documento.pdf") is Modalidad.pdf_digital


def test_pdf_solo_imagen_es_escaneado():
    assert detectar(_pdf(["imagen"]), "escaneo.pdf") is Modalidad.pdf_escaneado


def test_pdf_mixto_es_escaneado():
    assert detectar(_pdf(["texto", "imagen", "texto"]), "mixto.pdf") is Modalidad.pdf_escaneado


def test_pdf_con_poco_texto_es_escaneado():
    # Un escaneo con solo un pie de pagina no llega al umbral.
    assert detectar(_pdf(["Pagina 1"]), "escaneo.pdf") is Modalidad.pdf_escaneado


def test_umbral_exacto_cuenta_como_texto():
    justo = "X" * UMBRAL_CARACTERES_POR_PAGINA
    uno_menos = "X" * (UMBRAL_CARACTERES_POR_PAGINA - 1)
    assert detectar(_pdf([justo]), "a.pdf") is Modalidad.pdf_digital
    assert detectar(_pdf([uno_menos]), "a.pdf") is Modalidad.pdf_escaneado


def test_los_espacios_no_cuentan_para_el_umbral():
    texto = " ".join(["X"] * (UMBRAL_CARACTERES_POR_PAGINA - 1))  # 29 letras y 28 espacios
    assert detectar(_pdf([texto]), "a.pdf") is Modalidad.pdf_escaneado


# --- Imagenes ---

@pytest.mark.parametrize("nombre", ["foto.png", "FOTO.PNG"])
def test_png_es_imagen(nombre):
    assert detectar(_png(), nombre) is Modalidad.imagen


@pytest.mark.parametrize("nombre", ["foto.jpg", "foto.jpeg", "FOTO.JPG"])
def test_jpg_es_imagen(nombre):
    assert detectar(_jpg(), nombre) is Modalidad.imagen


# --- El contenido manda sobre la extension ---

def test_pdf_con_extension_de_imagen_se_trata_como_pdf(caplog):
    assert detectar(_pdf(["texto"]), "foto.jpg") is Modalidad.pdf_digital
    assert "no coincide con el contenido" in caplog.text
    assert "foto.jpg" not in caplog.text  # el nombre del archivo no va al log


def test_png_con_extension_pdf_se_trata_como_imagen():
    assert detectar(_png(), "documento.pdf") is Modalidad.imagen


def test_archivo_sin_extension_se_detecta_por_contenido():
    assert detectar(_png(), "sin_extension") is Modalidad.imagen


# --- Errores ---

@pytest.mark.parametrize("contenido, nombre", [
    (b"texto plano sin formato", "notas.txt"),
    (b"texto plano con extension enganosa", "documento.pdf"),
    (b"GIF89a" + b"\x00" * 20, "animacion.gif"),
    (b"", "vacio.pdf"),
])
def test_formato_no_soportado(contenido, nombre):
    with pytest.raises(FormatoNoSoportado):
        detectar(contenido, nombre)


def test_pdf_corrupto():
    with pytest.raises(FormatoNoSoportado):
        detectar(b"%PDF-1.7\n esto no es un PDF valido", "roto.pdf")


def test_pdf_protegido_con_contrasena():
    cifrado = _pdf(["texto"], encryption=pymupdf.PDF_ENCRYPT_AES_256,
                   user_pw="clave_de_prueba", owner_pw="clave_de_prueba")
    with pytest.raises(FormatoNoSoportado, match="contrasena"):
        detectar(cifrado, "protegido.pdf")
