"""
Prepara las fotos de especimenes impresos para fixtures/especimenes/ (se suben a git).
Responsable: PERSONA_3. Solo documentos FICTICIOS impresos con scripts/generar_fixtures.py;
nunca fotos de documentos reales.

Uso (desde la raiz del repo):
    python scripts/procesar_especimenes.py ORIGEN [ORIGEN ...] [--salida DIR]
ORIGEN es una foto o una carpeta con fotos. Las originales se quedan donde estan: no se copian al
repo. Antes de procesarlas, mira cada foto: solo puede aparecer el documento ficticio (sin caras,
manos, pantallas, otros papeles ni nada personal). Pasa solo las que cumplen.

Por cada foto `{tipo}_{condicion}.jpeg` (tambien .jpg, .JPG o .JPEG):
  - comprueba por la firma del fichero que es JPEG de verdad (no HEIC renombrado);
  - toma solo la imagen principal (los moviles guardan MPO, con una segunda imagen dentro);
  - aplica la orientacion EXIF, para que no salga girada al quitar los metadatos;
  - convierte a sRGB con el perfil ICC de la camara y luego lo descarta;
  - quita TODOS los metadatos (EXIF, GPS, modelo de camara, XMP, ICC, MPO): la imagen se rehace
    solo con los pixeles;
  - reduce el lado largo a LADO_LARGO (2000) px y guarda en JPEG con calidad CALIDAD (85);
  - escribe {salida}/{tipo}_sano_especimen_{condicion}.jpg y comprueba que no queda ningun metadato.
Valores esperados y fotos descartadas: fixtures/especimenes/README.md. Tests:
backend/tests/test_especimenes.py.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageCms, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
DIR_TIPOS = RAIZ / "config" / "tipos"
SALIDA = RAIZ / "fixtures" / "especimenes"
CASO = "sano"  # se imprimio el caso sano (generar_fixtures.py --hoy 2026-09-30)
CONDICIONES = ("buena", "inclinada", "dificil")
LADO_LARGO = 2000
CALIDAD = 85
EXTENSIONES = {".jpg", ".jpeg"}  # sin distinguir mayusculas

# Marcas de metadatos que no pueden quedar en el fichero final
MARCAS_PROHIBIDAS = {b"Exif\x00\x00": "EXIF", b"http://ns.adobe.com/xap/": "XMP", b"MPF\x00": "MPO",
                     b"ICC_PROFILE\x00": "ICC"}


class ErrorEspecimen(Exception):
    """La foto no se puede procesar (nombre, formato o metadatos)."""


def tipos_documentales(directorio: Path = DIR_TIPOS) -> list[str]:
    return sorted(yaml.safe_load(r.read_text(encoding="utf-8"))["nombre"] for r in directorio.glob("*.yaml"))


def nombre_salida(ruta: Path, tipos: list[str]) -> str:
    """`pasaporte_buena.JPEG` -> `pasaporte_sano_especimen_buena.jpg`."""
    if ruta.suffix.lower() not in EXTENSIONES:
        raise ErrorEspecimen(f"{ruta.name}: extension {ruta.suffix} no admitida (solo .jpg o .jpeg)")
    patron = rf"({'|'.join(map(re.escape, tipos))})_({'|'.join(CONDICIONES)})"
    if not (m := re.fullmatch(patron, ruta.stem)):
        raise ErrorEspecimen(f"{ruta.name}: el nombre debe ser {{tipo}}_{{condicion}} con tipo en {tipos} "
                             f"y condicion en {list(CONDICIONES)}")
    return f"{m[1]}_{CASO}_especimen_{m[2]}.jpg"


def comprobar_firma_jpeg(datos: bytes, nombre: str) -> None:
    if datos[:3] == b"\xff\xd8\xff":
        return
    if datos[4:8] == b"ftyp":  # contenedor ISO (HEIC/HEIF/AVIF) con la extension cambiada
        raise ErrorEspecimen(f"{nombre}: no es JPEG sino {datos[8:12].decode(errors='replace')!r} (HEIC "
                             "renombrado?). Exportalo como JPEG desde el movil")
    raise ErrorEspecimen(f"{nombre}: la firma del fichero no es la de un JPEG")


def metadatos_presentes(imagen: Image.Image) -> list[str]:
    """Nombres de los metadatos que lleva la imagen (nunca sus valores: pueden ser GPS)."""
    presentes = []
    exif = imagen.getexif()
    if len(exif):
        gps = " con GPS" if exif.get_ifd(0x8825) else ""
        presentes.append(f"EXIF ({len(exif)} etiquetas{gps})")
    presentes += [nombre for clave, nombre in (("icc_profile", "ICC"), ("xmp", "XMP"), ("mp", "MPO"),
                                               ("comment", "comentario")) if imagen.info.get(clave)]
    if getattr(imagen, "n_frames", 1) > 1:
        presentes.append(f"{imagen.n_frames} imagenes")
    return presentes


def a_srgb(imagen: Image.Image) -> Image.Image:
    icc = imagen.info.get("icc_profile")
    rgb = imagen.convert("RGB")
    if not icc:
        return rgb
    origen = ImageCms.ImageCmsProfile(io.BytesIO(icc))
    return ImageCms.profileToProfile(rgb, origen, ImageCms.createProfile("sRGB"), outputMode="RGB")


def limpiar(datos: bytes, lado_largo: int = LADO_LARGO) -> Image.Image:
    """Imagen principal, orientada, en sRGB, reducida y sin ningun metadato (solo pixeles)."""
    with Image.open(io.BytesIO(datos)) as original:
        original.seek(0)  # imagen principal de un MPO
        orientada = ImageOps.exif_transpose(original)  # usa la etiqueta Orientation antes de perderla
        orientada.info["icc_profile"] = original.info.get("icc_profile")
        rgb = a_srgb(orientada)
    rgb.thumbnail((lado_largo, lado_largo), Image.LANCZOS)
    return Image.frombytes("RGB", rgb.size, rgb.tobytes())  # info vacio: nada se arrastra al guardar


def comprobar_sin_metadatos(datos: bytes, nombre: str) -> None:
    encontradas = [n for marca, n in MARCAS_PROHIBIDAS.items() if marca in datos]
    with Image.open(io.BytesIO(datos)) as imagen:
        if imagen.format != "JPEG":
            encontradas.append(f"formato {imagen.format}")
        encontradas += metadatos_presentes(imagen)
    if encontradas:
        raise ErrorEspecimen(f"{nombre}: quedan metadatos tras limpiar: {sorted(set(encontradas))}")


def procesar(ruta: Path, salida: Path, tipos: list[str], lado_largo: int = LADO_LARGO,
             calidad: int = CALIDAD) -> dict:
    destino = salida / nombre_salida(ruta, tipos)
    datos = ruta.read_bytes()
    comprobar_firma_jpeg(datos, ruta.name)
    with Image.open(io.BytesIO(datos)) as original:
        quitados, tamano_original = metadatos_presentes(original), original.size
    imagen = limpiar(datos, lado_largo)
    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", quality=calidad, optimize=True)
    comprobar_sin_metadatos(buffer.getvalue(), destino.name)
    salida.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(buffer.getvalue())
    return {"origen": ruta.name, "destino": destino.name, "tamano_original": tamano_original,
            "tamano": imagen.size, "bytes": len(buffer.getvalue()), "quitados": quitados}


def fotos(origenes: list[Path]) -> list[Path]:
    rutas = []
    for origen in origenes:
        if origen.is_dir():
            rutas += sorted(p for p in origen.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES)
        else:
            rutas.append(origen)
    return rutas


def main() -> None:
    parser = argparse.ArgumentParser(description="Quita metadatos y reduce las fotos de especimenes impresos")
    parser.add_argument("origenes", nargs="+", type=Path, help="fotos o carpetas con fotos {tipo}_{condicion}.jpeg")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()
    tipos, errores = tipos_documentales(), []
    for ruta in fotos(args.origenes):
        try:
            r = procesar(ruta, args.salida, tipos)
        except ErrorEspecimen as e:
            errores.append(str(e))
            continue
        print(f"{r['origen']:38s} -> {r['destino']:48s} {r['tamano_original'][0]}x{r['tamano_original'][1]} -> "
              f"{r['tamano'][0]}x{r['tamano'][1]}, {r['bytes'] // 1024} KB; quitado: {', '.join(r['quitados']) or '-'}")
    for error in errores:
        print(f"ERROR {error}", file=sys.stderr)
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
