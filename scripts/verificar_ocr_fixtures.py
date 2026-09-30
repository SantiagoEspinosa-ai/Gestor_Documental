"""
Verifica que Tesseract lee los fixtures ficticios (legibilidad OCR).
Responsable: PERSONA_3. Usalo tras cambiar scripts/generar_fixtures.py.

Que hace:
  - *_escaneado.pdf: renderiza cada pagina a 200 dpi con PyMuPDF y le pasa Tesseract (spa+eng).
  - *_foto.jpg: le pasa Tesseract directamente.
  - Con --control, tambien el render de los *_digital.pdf (sin ruido ni distorsion): separa lo que
    se pierde por el ruido de lo que se pierde por la maqueta o la fuente.
  - Preprocesado minimo, el previsto para orquestador/ocr.py: escala de grises + autocontraste.
    No importa nada del orquestador: es una comprobacion independiente de los fixtures.
  - Compara el texto con los valores esperados de fixtures/generados/INDICE.md (fechas en
    DD/MM/AAAA, como aparecen en el documento), normalizando mayusculas, acentos y espacios y
    exigiendo palabra completa. Las copias del caso duplicado no se procesan (son identicas a sano).
  - Escribe la tabla en fixtures/generados/resultado_ocr.md (ignorado por git, como INDICE.md).

Como ejecutarlo (PowerShell, desde la raiz del repo, con los fixtures ya generados). Se usa el
contenedor del backend porque trae Tesseract spa+eng; config/ ya lo monta docker-compose.yml:
    docker compose run --rm --no-deps -v "${PWD}\\fixtures:/fixtures" -v "${PWD}\\scripts:/scripts:ro" `
        backend python /scripts/verificar_ocr_fixtures.py --control

Como interpretar el resultado:
  - "Campos": encontrados / total por fichero. "No encontrados" muestra el valor esperado y el
    fragmento del OCR mas parecido (con su porcentaje de parecido) para ver el tipo de error.
  - "MRZ": lineas de la MRZ del pasaporte leidas sin error (se comparan sin espacios).
  - Si un campo falla tambien en el control digital, el problema es de maqueta o fuente, no de
    ruido. Si solo falla en escaneado o foto, el ruido, la rotacion o la perspectiva son excesivos.
  - Referencia (2026-09-30): 150/153 campos. Los fallos (sexo "M" suelto y Z/2 en la MRZ de
    pasaporte_vencido) ocurren tambien en el control y se dejan a proposito: son casos realistas.
"""
from __future__ import annotations

import argparse
import difflib
import re
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DPI = 200
IDIOMAS = "spa+eng"


def dir_fixtures_por_defecto() -> Path:
    """/fixtures/generados dentro del contenedor; si no, la carpeta del repo."""
    contenedor = Path("/fixtures/generados")
    return contenedor if contenedor.is_dir() else RAIZ / "fixtures" / "generados"


def normalizar(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(plano.upper().split())


def contiene_palabra(esperado: str, texto: str) -> bool:
    """"M" (sexo) o "2029" no cuentan si forman parte de otra palabra."""
    return re.search(rf"(?<![A-Z0-9]){re.escape(esperado)}(?![A-Z0-9])", texto) is not None


def parsear_indice(ruta: Path) -> dict[str, dict]:
    """{archivo: {caso, tipo, campos: {campo: valor como aparece en el documento}, mrz, archivos}}"""
    documentos, actual, en_mrz = {}, None, False
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"^### (\S+) / (\S+)$", linea):
            actual = {"caso": m[1], "tipo": m[2], "campos": {}, "mrz": [], "archivos": []}
            en_mrz = False
            continue
        if linea.startswith("## "):
            actual = None
        if actual is None:
            continue
        if "Archivos:" in linea:
            actual["archivos"] = re.findall(r"`([^`]+)`", linea.split("Archivos:")[1])
            for archivo in actual["archivos"]:
                documentos[archivo] = actual
        elif m := re.match(r"^\| `(\w+)` \| (.+) \|$", linea):
            valor = m[2].strip()
            if f := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", valor):
                valor = f"{f[3]}/{f[2]}/{f[1]}"  # en el documento: DD/MM/AAAA
            actual["campos"][m[1]] = valor
        elif linea == "```":
            en_mrz = not en_mrz
        elif en_mrz:
            actual["mrz"].append(linea)
    return documentos


def leer_texto(ruta: Path) -> str:
    import pymupdf
    import pytesseract
    from PIL import Image, ImageOps

    preprocesar = lambda imagen: ImageOps.autocontrast(imagen.convert("L"))
    if ruta.suffix == ".pdf":
        partes = []
        with pymupdf.open(ruta) as doc:
            for pagina in doc:
                pix = pagina.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY, alpha=False)
                imagen = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                partes.append(pytesseract.image_to_string(preprocesar(imagen), lang=IDIOMAS))
        return "\n".join(partes)
    with Image.open(ruta) as imagen:
        return pytesseract.image_to_string(preprocesar(imagen), lang=IDIOMAS)


def mejor_parecido(valor: str, lineas: list[str]) -> tuple[float, str]:
    """Fragmento del OCR mas parecido al valor (ventanas de tantas palabras como el valor)."""
    n = max(1, len(valor.split()))
    mejor = (0.0, "")
    for linea in lineas:
        palabras = linea.split()
        for i in range(max(1, len(palabras) - n + 1)):
            fragmento = " ".join(palabras[i:i + n])
            ratio = difflib.SequenceMatcher(None, valor, fragmento).ratio()
            if ratio > mejor[0]:
                mejor = (ratio, fragmento)
    return mejor


def comparar(doc: dict, crudo: str) -> tuple[list[str], int]:
    """Campos no encontrados (con su parecido) y lineas de MRZ leidas."""
    texto = normalizar(crudo)
    lineas = [normalizar(l) for l in crudo.splitlines() if l.strip()] or [texto]
    fallos = []
    for campo, valor in doc["campos"].items():
        esperado = normalizar(valor)
        if not contiene_palabra(esperado, texto):
            ratio, fragmento = mejor_parecido(esperado, lineas)
            fallos.append(f"{campo} ({valor} ~ '{fragmento}' {ratio:.0%})")
    sin_espacios = texto.replace(" ", "")  # Tesseract suele meter espacios dentro de la MRZ
    return fallos, sum(normalizar(l) in sin_espacios for l in doc["mrz"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Comprueba con Tesseract la legibilidad de los fixtures")
    parser.add_argument("--fixtures", type=Path, default=dir_fixtures_por_defecto())
    parser.add_argument("--control", action="store_true", help="incluye el render de los PDF digitales")
    parser.add_argument("--salida", type=Path, default=None,
                        help="tabla en Markdown (por defecto <fixtures>/resultado_ocr.md)")
    args = parser.parse_args()
    import pytesseract

    documentos = parsear_indice(args.fixtures / "INDICE.md")
    modalidades = ["escaneado", "foto"] + (["digital"] if args.control else [])
    archivos = sorted(a for a, d in documentos.items()
                      if d["caso"] != "duplicado" and any(f"_{m}." in a for m in modalidades))
    print(f"Tesseract {pytesseract.get_tesseract_version()} | idiomas {IDIOMAS} | {len(archivos)} ficheros\n")

    filas, resumen = [], {}
    for archivo in archivos:
        doc = documentos[archivo]
        modalidad = next(m for m in modalidades if f"_{m}." in archivo)
        inicio = time.perf_counter()
        crudo = leer_texto(args.fixtures / archivo)
        segundos = time.perf_counter() - inicio
        fallos, mrz_ok = comparar(doc, crudo)
        total = len(doc["campos"])
        encontrados = total - len(fallos)
        acumulado = resumen.setdefault((modalidad, doc["tipo"]), [0, 0])
        acumulado[0] += encontrados
        acumulado[1] += total
        mrz = f"{mrz_ok}/{len(doc['mrz'])}" if doc["mrz"] else "-"
        filas.append(f"| `{archivo}` | {modalidad} | {encontrados}/{total} | {mrz} | {segundos:.1f}s | "
                     f"{'; '.join(fallos) or '-'} |")
        print(f"{encontrados}/{total}  {archivo}")

    tabla = ["| Archivo | Modalidad | Campos | MRZ | Tiempo | No encontrados (esperado ~ OCR parecido) |",
             "|---|---|---|---|---|---|", *filas, "",
             "| Modalidad | Tipo | Campos encontrados |", "|---|---|---|"]
    for (modalidad, tipo), (ok, total) in sorted(resumen.items()):
        tabla.append(f"| {modalidad} | {tipo} | {ok}/{total} ({ok / total:.0%}) |")
    salida = "\n".join(tabla)
    print("\n" + salida)
    destino = args.salida or args.fixtures / "resultado_ocr.md"
    destino.write_text(salida + "\n", encoding="utf-8")
    print(f"\nTabla guardada en {destino}")


if __name__ == "__main__":
    main()
