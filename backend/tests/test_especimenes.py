"""Tests de fixtures/especimenes/ y scripts/procesar_especimenes.py (PERSONA_3).
Las fotos del repo no pueden llevar metadatos (EXIF, GPS, XMP, ICC, MPO) y deben respetar el tamano.
El script se prueba con imagenes sinteticas: solo datos ficticios (GPS de prueba inventado)."""
import importlib.util
import io
import re
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REPO / "scripts" / "procesar_especimenes.py"
ESPECIMENES = RAIZ_REPO / "fixtures" / "especimenes"
if not SCRIPT.is_file() or not ESPECIMENES.is_dir() or not (RAIZ_REPO / "config" / "tipos").is_dir():
    pytest.skip("Tests de especimenes omitidos: faltan scripts/, fixtures/especimenes o config/tipos "
                "(normal dentro del contenedor del backend)", allow_module_level=True)

from PIL import Image, ImageCms  # noqa: E402

_spec = importlib.util.spec_from_file_location("procesar_especimenes", SCRIPT)
pe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pe)

MAX_BYTES = 2 * 1024 * 1024
FOTOS = sorted(ESPECIMENES.glob("*.jpg"))
TIPOS = pe.tipos_documentales()


# ---------------------------------------------------------------- fotos del repo

def test_hay_fotos_y_solo_jpg_con_el_nombre_acordado():
    assert FOTOS, "fixtures/especimenes/ no tiene fotos"
    otros = [p.name for p in ESPECIMENES.iterdir() if p.suffix != ".jpg" and p.name != "README.md"]
    assert otros == []
    patron = rf"({'|'.join(TIPOS)})_sano_especimen_({'|'.join(pe.CONDICIONES)})\.jpg"
    assert all(re.fullmatch(patron, p.name) for p in FOTOS), [p.name for p in FOTOS]


@pytest.mark.parametrize("ruta", FOTOS, ids=lambda p: p.name)
def test_foto_sin_exif_gps_ni_otros_metadatos(ruta):
    datos = ruta.read_bytes()
    assert datos[:3] == b"\xff\xd8\xff"
    with Image.open(ruta) as foto:
        assert foto.format == "JPEG" and getattr(foto, "n_frames", 1) == 1
        exif = foto.getexif()
        assert len(exif) == 0 and not exif.get_ifd(0x8825), "lleva EXIF o GPS"
        assert pe.metadatos_presentes(foto) == []
    for marca, nombre in pe.MARCAS_PROHIBIDAS.items():
        assert marca not in datos, f"lleva {nombre}"


@pytest.mark.parametrize("ruta", FOTOS, ids=lambda p: p.name)
def test_foto_dentro_del_limite_de_tamano(ruta):
    with Image.open(ruta) as foto:
        assert max(foto.size) <= pe.LADO_LARGO and min(foto.size) >= 1000
    assert ruta.stat().st_size <= MAX_BYTES


def test_el_readme_lista_todas_las_fotos():
    readme = (ESPECIMENES / "README.md").read_text(encoding="utf-8")
    assert all(f"`{p.name}`" in readme for p in FOTOS)
    # 2026-12-15: desde ese dia el comprobante da REG-antiguedad_maxima (emision >= hoy - 90 dias)
    assert "2026-12-15" in readme and "--hoy 2026-09-30" in readme


# ---------------------------------------------------------------- script con imagenes sinteticas

def foto_de_movil(ancho=3000, alto=1200, orientacion=6) -> bytes:
    """JPEG tipo movil: MPO de dos imagenes con EXIF (orientacion, modelo, GPS de prueba), XMP e ICC."""
    imagen = Image.new("RGB", (ancho, alto), (250, 250, 250))
    imagen.paste((200, 30, 30), (0, 0, ancho // 4, alto // 4))  # marca roja arriba a la izquierda
    exif = Image.Exif()
    exif[0x0112] = orientacion
    exif[0x0110] = "MODELO-DE-PRUEBA"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (1.0, 2.0, 3.0)  # coordenadas inventadas
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    salida = io.BytesIO()
    imagen.save(salida, "MPO", save_all=True, append_images=[imagen.resize((ancho // 4, alto // 4))],
                exif=exif, icc_profile=icc, xmp=b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>dato de prueba</x:xmpmeta>")
    return salida.getvalue()


@pytest.fixture
def cruda(tmp_path):
    ruta = tmp_path / "pasaporte_inclinada.JPEG"  # extension en mayusculas
    ruta.write_bytes(foto_de_movil())
    return ruta


def test_la_foto_sintetica_lleva_todos_los_metadatos(cruda):
    with Image.open(cruda) as imagen:
        presentes = pe.metadatos_presentes(imagen)
    assert {"ICC", "XMP", "MPO"} <= set(presentes) and any("con GPS" in p for p in presentes)


def test_procesar_quita_metadatos_aplica_orientacion_y_reduce(cruda, tmp_path):
    salida = tmp_path / "salida"
    resultado = pe.procesar(cruda, salida, TIPOS)
    assert resultado["destino"] == "pasaporte_sano_especimen_inclinada.jpg"
    datos = (salida / resultado["destino"]).read_bytes()
    pe.comprobar_sin_metadatos(datos, "x")  # no lanza
    with Image.open(io.BytesIO(datos)) as foto:
        assert foto.format == "JPEG" and len(foto.getexif()) == 0
        # orientacion 6 = girar 90 grados: 3000x1200 pasa a vertical y el lado largo a 2000
        assert foto.size == (800, 2000)
        # la marca roja (arriba a la izquierda del sensor) queda arriba a la derecha tras girar
        rojo = foto.convert("RGB").getpixel((foto.width - 20, 20))
        assert rojo[0] > 150 and rojo[1] < 100
    for marca in (b"MODELO-DE-PRUEBA", b"dato de prueba", b"Exif\x00\x00", b"MPF\x00"):
        assert marca not in datos


def test_foto_pequena_no_se_agranda(tmp_path):
    ruta = tmp_path / "credencial_elector_buena.jpg"
    ruta.write_bytes(foto_de_movil(1200, 900, orientacion=1))
    resultado = pe.procesar(ruta, tmp_path / "salida", TIPOS)
    assert resultado["tamano"] == (1200, 900)


def test_heic_renombrado_se_rechaza(tmp_path):
    ruta = tmp_path / "pasaporte_buena.jpeg"
    ruta.write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64)
    with pytest.raises(pe.ErrorEspecimen, match="HEIC"):
        pe.procesar(ruta, tmp_path / "salida", TIPOS)
    assert not (tmp_path / "salida").exists()


@pytest.mark.parametrize("nombre, esperado", [
    ("pasaporte_buena.jpeg", "pasaporte_sano_especimen_buena.jpg"),
    ("credencial_elector_dificil.JPG", "credencial_elector_sano_especimen_dificil.jpg"),
    ("comprobante_domicilio_inclinada.JPEG", "comprobante_domicilio_sano_especimen_inclinada.jpg"),
])
def test_nombre_de_salida_siempre_jpg_en_minusculas(nombre, esperado):
    assert pe.nombre_salida(Path(nombre), TIPOS) == esperado


@pytest.mark.parametrize("nombre", ["pasaporte_buena.png", "pasaporte_borrosa.jpg", "factura_buena.jpg"])
def test_nombre_no_valido_se_rechaza(nombre):
    with pytest.raises(pe.ErrorEspecimen):
        pe.nombre_salida(Path(nombre), TIPOS)
