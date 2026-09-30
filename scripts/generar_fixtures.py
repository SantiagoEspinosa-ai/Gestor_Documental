"""
Genera documentos FICTICIOS de prueba en fixtures/generados/.
Responsable: PERSONA_3. Nunca usar datos reales.

Uso (desde la raiz del repo):
    python scripts/generar_fixtures.py [--hoy AAAA-MM-DD] [--salida DIR]

Determinista: con el mismo --hoy los ficheros salen identicos byte a byte (semilla fija, metadatos
fijos y sin identificador aleatorio en el PDF). Las fechas son relativas a --hoy (por defecto
date.today()) para que los casos no caduquen.

Los campos de cada documento se leen de config/tipos/*.yaml. Si una ficha tiene un campo que este
generador no sabe rellenar (o al reves), o un valor no cumple su `patron`, el script falla.

Los ficheros generados (incluido INDICE.md) NO se suben a git: fixtures/generados/ esta en
.gitignore. Este script es la fuente de verdad y cada persona los genera en local.

Casos:
  - sano:     persona 1; los 3 documentos coinciden y estan vigentes
  - vencido:  persona 2; pasaporte vencido hace 30 dias
Modalidades: PDF digital con capa de texto real (PyMuPDF).

Pendiente para la segunda parte:
  - Casos domicilio_distinto y duplicado (copia byte a byte).
  - Modalidades *_escaneado.pdf (render a imagen con ruido y ligera rotacion, sin capa de texto) y
    *_foto.jpg (perspectiva y sombra), con Pillow y la misma SEMILLA.
  - fixtures/generados/INDICE.md con caso, archivo y valores esperados de cada campo. El caso
    vencido debe listar tanto REG-vigencia_documento (bloqueante) como REG-vigencia_proxima
    (preventiva): vencer hace 30 dias incumple las dos reglas del pasaporte.
Pendiente para PERSONA_2 (no tocar los YAML desde aqui):
  - `ejemplos_referencia` de config/tipos/*.yaml apunta a ficheros de fixtures/ que no existen.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import re
from datetime import date, timedelta
from pathlib import Path

import pymupdf
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DIR_TIPOS = RAIZ / "config" / "tipos"
SALIDA = RAIZ / "fixtures" / "generados"
SEMILLA = 20260930

PERSONAS_FICTICIAS = [
    {"nombre_completo": "Ana Ejemplo Prueba", "fecha_nacimiento": "1990-01-01",
     "curp": "AEPA900101MDFXXX01", "domicilio": "Calle Ficticia 123, Colonia Demo, Ciudad Ejemplo",
     # Anadidos para los documentos; todos inventados
     "sexo": "F", "nacionalidad": "UTOPICA", "numero_pasaporte": "ZX0000001",
     "clave_elector": "EJPRAN90010199M101"},
    {"nombre_completo": "Luis Demo Pruebas", "fecha_nacimiento": "1985-06-15",
     "curp": "DEPL850615HDFXXX02", "domicilio": "Avenida Inventada 456, Colonia Test, Ciudad Ejemplo",
     "sexo": "M", "nacionalidad": "UTOPICA", "numero_pasaporte": "ZX0000002",
     "clave_elector": "DEPRLU85061599H102"},
]

# Codigo de pais de la OACI para especimenes ("Utopia"); nunca un pais real
PAIS_MRZ = "UTO"
PROVEEDOR_FICTICIO = "SERVICIOS DE EJEMPLO S.A."

CASOS = {
    "sano": {"persona": 0, "vencimiento_pasaporte": lambda hoy: sumar_anios(hoy, 5)},
    "vencido": {"persona": 1, "vencimiento_pasaporte": lambda hoy: hoy - timedelta(days=30)},
}

MM = 72 / 25.4  # puntos PDF por milimetro
# Pasaporte (ID-3, 125 x 88 mm) y credencial (ID-1, 85,6 x 54 mm) a escala para que se lean bien
PAGINAS = {
    "pasaporte": (250 * MM, 176 * MM),
    "credencial_elector": (214 * MM, 135 * MM),
    "comprobante_domicilio": pymupdf.paper_size("a4"),
}
GRIS_TEXTO = (0.35, 0.35, 0.35)
GRIS_MARCA = (0.93, 0.93, 0.93)  # marca de agua muy tenue
AZUL_CABECERA = (0.12, 0.23, 0.42)


class ErrorFixture(Exception):
    """Incoherencia entre YAML, persona y generador: mejor fallar que generar un fixture falso."""


# ---------------------------------------------------------------- fechas y fichas

def sumar_anios(d: date, anios: int) -> date:
    try:
        return d.replace(year=d.year + anios)
    except ValueError:  # 29 de febrero en un anio no bisiesto
        return d.replace(year=d.year + anios, day=28)


def cargar_fichas(directorio: Path = DIR_TIPOS) -> dict[str, dict]:
    fichas = {}
    for ruta in sorted(directorio.glob("*.yaml")):
        ficha = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        fichas[ficha["nombre"]] = ficha
    return fichas


# ---------------------------------------------------------------- coherencia con la CURP

def datos_de_curp(curp: str) -> tuple[date, str]:
    """Fecha de nacimiento y sexo (F/M como en la MRZ) segun la CURP."""
    siglo = 1900 if curp[16].isdigit() else 2000  # posicion 17: digito antes de 2000, letra despues
    nacimiento = date(siglo + int(curp[4:6]), int(curp[6:8]), int(curp[8:10]))
    sexo = {"H": "M", "M": "F"}[curp[10]]
    return nacimiento, sexo


def validar_persona(persona: dict, fichas: dict[str, dict]) -> None:
    errores = []
    curp = persona["curp"]
    patron_curp = fichas["credencial_elector"]["campos"]["curp"]["patron"]
    if not re.fullmatch(patron_curp, curp):
        raise ErrorFixture(f"CURP {curp} no cumple el patron del YAML")
    nacimiento, sexo = datos_de_curp(curp)
    if date.fromisoformat(persona["fecha_nacimiento"]) != nacimiento:
        errores.append(f"fecha_nacimiento {persona['fecha_nacimiento']} no coincide con la CURP ({nacimiento})")
    if persona["sexo"] != sexo:
        errores.append(f"sexo {persona['sexo']} no coincide con la CURP ({curp[10]} -> {sexo})")
    clave = persona["clave_elector"]  # sin patron en el YAML: formato de 18 posiciones, estado 99
    if len(clave) != 18 or clave[6:12] != curp[4:10] or clave[12:14] != "99" or clave[14] != curp[10]:
        errores.append(f"clave_elector {clave} no es coherente con la CURP (fecha, estado 99, sexo)")
    if errores:
        raise ErrorFixture(f"{persona['nombre_completo']}: " + "; ".join(errores))


# ---------------------------------------------------------------- MRZ (formato TD3 de la OACI)

def digito_control(texto: str) -> str:
    valor = lambda c: int(c) if c.isdigit() else (ord(c) - 55 if c.isalpha() else 0)
    return str(sum(valor(c) * (7, 3, 1)[i % 3] for i, c in enumerate(texto)) % 10)


def generar_mrz(v: dict) -> tuple[str, str]:
    nombre, *apellidos = v["nombre_completo"].split()
    linea1 = f"P<{PAIS_MRZ}{'<'.join(apellidos)}<<{nombre}".ljust(44, "<")[:44]
    numero = v["numero_pasaporte"].ljust(9, "<")
    nac = v["fecha_nacimiento"].strftime("%y%m%d")
    ven = v["fecha_vencimiento"].strftime("%y%m%d")
    personal = "<" * 14
    parte_num = numero + digito_control(numero)
    parte_nac = nac + digito_control(nac)
    parte_ven = ven + digito_control(ven)
    parte_per = personal + digito_control(personal)
    compuesto = digito_control(parte_num + parte_nac + parte_ven + parte_per)
    linea2 = parte_num + PAIS_MRZ + parte_nac + v["sexo"] + parte_ven + parte_per + compuesto
    return linea1, linea2


def validar_mrz(linea1: str, linea2: str, v: dict) -> None:
    if len(linea1) != 44 or len(linea2) != 44:
        raise ErrorFixture("La MRZ debe tener dos lineas de 44 caracteres")
    comprobaciones = [(linea2[0:9], linea2[9]), (linea2[13:19], linea2[19]), (linea2[21:27], linea2[27]),
                      (linea2[28:42], linea2[42]),
                      (linea2[0:10] + linea2[13:20] + linea2[21:43], linea2[43])]
    if any(digito_control(dato) != control for dato, control in comprobaciones):
        raise ErrorFixture(f"Digito de control incorrecto en la MRZ: {linea2}")
    if linea2[13:19] != v["fecha_nacimiento"].strftime("%y%m%d") or linea2[20] != v["sexo"]:
        raise ErrorFixture("Fecha de nacimiento o sexo de la MRZ no coinciden con los datos")


# ---------------------------------------------------------------- valores por tipo

def valores_documento(tipo: str, persona: dict, caso: str, hoy: date) -> dict:
    nacimiento = date.fromisoformat(persona["fecha_nacimiento"])
    nombre = persona["nombre_completo"].upper()
    domicilio = persona["domicilio"].upper()
    if tipo == "pasaporte":
        vence = CASOS[caso]["vencimiento_pasaporte"](hoy)
        return {"nombre_completo": nombre, "numero_pasaporte": persona["numero_pasaporte"],
                "fecha_nacimiento": nacimiento, "fecha_expedicion": sumar_anios(vence, -10),
                "fecha_vencimiento": vence, "nacionalidad": persona["nacionalidad"],
                "sexo": persona["sexo"]}
    if tipo == "credencial_elector":
        return {"nombre_completo": nombre, "curp": persona["curp"],
                "clave_elector": persona["clave_elector"], "fecha_nacimiento": nacimiento,
                "domicilio": domicilio, "vigencia": hoy.year + 3}
    if tipo == "comprobante_domicilio":
        return {"nombre_titular": nombre, "domicilio": domicilio, "proveedor": PROVEEDOR_FICTICIO,
                "fecha_emision": hoy - timedelta(days=15)}
    raise ErrorFixture(f"El generador no tiene plantilla para el tipo {tipo}")


def validar_valores(tipo: str, valores: dict, ficha: dict) -> None:
    campos = ficha["campos"]
    faltan, sobran = set(campos) - set(valores), set(valores) - set(campos)
    if faltan or sobran:
        raise ErrorFixture(f"{tipo}: el YAML y el generador no coinciden "
                           f"(sin valor: {sorted(faltan)}; no estan en el YAML: {sorted(sobran)})")
    for campo, definicion in campos.items():
        patron = definicion.get("patron")
        if patron and not re.fullmatch(patron, str(valores[campo])):
            raise ErrorFixture(f"{tipo}.{campo}={valores[campo]!r} no cumple el patron {patron}")


def formatear(valor) -> str:
    return valor.strftime("%d/%m/%Y") if isinstance(valor, date) else str(valor)


# ---------------------------------------------------------------- dibujo

def texto(pagina, x, y, cadena, tam=10, fuente="helv", color=(0, 0, 0), rotar=0):
    pagina.insert_text((x, y), cadena, fontsize=tam, fontname=fuente, color=color, rotate=rotar)


def marca_de_agua_lateral(pagina) -> None:
    """Franja derecha reservada: fuera de las zonas de datos para no perjudicar al OCR."""
    ancho, alto = pagina.rect.width, pagina.rect.height
    texto(pagina, ancho - 10, alto - 40, "SIN VALIDEZ - ESPECIMEN FICTICIO", tam=11, fuente="hebo",
          color=GRIS_MARCA, rotar=90)


def cabecera(pagina, titulo: str, alto_barra: float = 34) -> None:
    ancho = pagina.rect.width
    pagina.draw_rect(pymupdf.Rect(0, 0, ancho, alto_barra), color=None, fill=AZUL_CABECERA)
    aviso = "ESPECIMEN FICTICIO"
    x_aviso = ancho - 18 - pymupdf.get_text_length(aviso, fontname="hebo", fontsize=10)
    tam = 14  # reduce el titulo si no cabe antes del aviso
    while tam > 8 and 18 + pymupdf.get_text_length(titulo.upper(), fontname="hebo", fontsize=tam) > x_aviso - 12:
        tam -= 1
    texto(pagina, 18, alto_barra - 12, titulo.upper(), tam=tam, fuente="hebo", color=(1, 1, 1))
    texto(pagina, x_aviso, alto_barra - 12, aviso, tam=10, fuente="hebo", color=(1, 1, 1))


def silueta(pagina, rect: pymupdf.Rect) -> None:
    pagina.draw_rect(rect, color=(0.6, 0.6, 0.6), fill=(0.85, 0.85, 0.85), width=0.8)
    cx, gris = rect.x0 + rect.width / 2, (0.55, 0.55, 0.55)
    pagina.draw_circle((cx, rect.y0 + rect.height * 0.38), rect.width * 0.22, color=None, fill=gris)
    hombros = pymupdf.Rect(rect.x0 + rect.width * 0.12, rect.y0 + rect.height * 0.66,
                           rect.x1 - rect.width * 0.12, rect.y1 + rect.height * 0.25)
    pagina.draw_oval(hombros, color=None, fill=gris)
    pagina.draw_rect(pymupdf.Rect(rect.x0, rect.y1, rect.x1, rect.y1 + rect.height * 0.3),
                     color=None, fill=(1, 1, 1))  # recorta los hombros al marco
    pagina.draw_rect(rect, color=(0.6, 0.6, 0.6), width=0.8)


def campos_en_columna(pagina, x, y, campos: dict, valores: dict, paso=30, tam=12, ancho_max=None):
    for campo in campos:  # orden del YAML
        texto(pagina, x, y, campo.replace("_", " ").upper(), tam=7, color=GRIS_TEXTO)
        texto(pagina, x, y + 13, formatear(valores[campo]), tam=tam, fuente="hebo")
        y += paso
    return y


def dibujar_pasaporte(pagina, ficha, valores, mrz):
    cabecera(pagina, ficha["nombre_visible"])
    marca_de_agua_lateral(pagina)
    silueta(pagina, pymupdf.Rect(22, 58, 172, 248))
    campos_en_columna(pagina, 200, 62, ficha["campos"], valores, paso=33)
    # MRZ al pie, en letra monoespaciada (dos lineas de 44 caracteres)
    pagina.draw_rect(pymupdf.Rect(0, pagina.rect.height - 78, pagina.rect.width - 28, pagina.rect.height),
                     color=None, fill=(0.97, 0.97, 0.97))
    for i, linea in enumerate(mrz):
        texto(pagina, 22, pagina.rect.height - 46 + i * 22, linea, tam=15, fuente="cour")


def dibujar_credencial(pagina, ficha, valores, mrz=None):
    cabecera(pagina, ficha["nombre_visible"])
    marca_de_agua_lateral(pagina)
    silueta(pagina, pymupdf.Rect(20, 52, 150, 216))
    campos_en_columna(pagina, 172, 56, ficha["campos"], valores, paso=31, tam=11)


def dibujar_comprobante(pagina, ficha, valores, rng: random.Random, mrz=None):
    cabecera(pagina, f"{valores['proveedor']} - {ficha['nombre_visible']}", alto_barra=46)
    y = campos_en_columna(pagina, 50, 90, ficha["campos"], valores, paso=36)
    # Detalle decorativo con importes ficticios (dependen solo de SEMILLA)
    y += 20
    texto(pagina, 50, y, "DETALLE DEL PERIODO (IMPORTES FICTICIOS)", tam=9, fuente="hebo", color=GRIS_TEXTO)
    total = 0.0
    for concepto in ("Cargo fijo", "Consumo del periodo", "Impuestos"):
        y += 18
        importe = round(rng.uniform(40, 400), 2)
        total += importe
        texto(pagina, 50, y, concepto, tam=10)
        texto(pagina, 420, y, f"{importe:10.2f}", tam=10, fuente="cour")
    y += 22
    texto(pagina, 50, y, "TOTAL", tam=10, fuente="hebo")
    texto(pagina, 420, y, f"{total:10.2f}", tam=10, fuente="cour")
    # Marca de agua en el pie, lejos de los datos
    texto(pagina, 50, pagina.rect.height - 30, "SIN VALIDEZ - DOCUMENTO FICTICIO GENERADO PARA PRUEBAS",
          tam=11, fuente="hebo", color=GRIS_MARCA)


# ---------------------------------------------------------------- generacion

def generar_pdf(tipo: str, ficha: dict, valores: dict, hoy: date, rng: random.Random,
                destino: Path) -> list[str]:
    """Genera un PDF digital y devuelve las lineas de texto esperadas en su capa de texto."""
    doc = pymupdf.open()
    pagina = doc.new_page(width=PAGINAS[tipo][0], height=PAGINAS[tipo][1])
    esperado = [formatear(valores[c]) for c in ficha["campos"]]
    if tipo == "pasaporte":
        mrz = generar_mrz(valores)
        validar_mrz(*mrz, valores)
        dibujar_pasaporte(pagina, ficha, valores, mrz)
        esperado += list(mrz)
    elif tipo == "credencial_elector":
        dibujar_credencial(pagina, ficha, valores)
    else:
        dibujar_comprobante(pagina, ficha, valores, rng)
    fecha_pdf = f"D:{hoy.strftime('%Y%m%d')}000000Z"
    doc.set_metadata({"title": f"{ficha['nombre_visible']} (ficticio)", "author": "generar_fixtures.py",
                      "subject": "Documento ficticio para pruebas. Sin validez.", "keywords": "",
                      "creator": "generar_fixtures.py", "producer": "PyMuPDF",
                      "creationDate": fecha_pdf, "modDate": fecha_pdf})
    doc.save(destino, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return esperado


def comprobar_capa_texto(ruta: Path, esperado: list[str]) -> None:
    with pymupdf.open(ruta) as doc:
        contenido = "\n".join(p.get_text() for p in doc)
    faltan = [e for e in esperado if e not in contenido]
    if faltan:
        raise ErrorFixture(f"{ruta.name}: la capa de texto no contiene {faltan}")


def generar(hoy: date, salida: Path = SALIDA) -> dict[str, str]:
    """Genera todos los fixtures y devuelve {nombre_archivo: sha256}."""
    fichas = cargar_fichas()
    for persona in PERSONAS_FICTICIAS:
        validar_persona(persona, fichas)
    rng = random.Random(SEMILLA)
    salida.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for caso, definicion in CASOS.items():
        persona = PERSONAS_FICTICIAS[definicion["persona"]]
        for tipo, ficha in fichas.items():
            valores = valores_documento(tipo, persona, caso, hoy)
            validar_valores(tipo, valores, ficha)
            destino = salida / f"{tipo}_{caso}_digital.pdf"
            esperado = generar_pdf(tipo, ficha, valores, hoy, rng, destino)
            comprobar_capa_texto(destino, esperado)
            hashes[destino.name] = hashlib.sha256(destino.read_bytes()).hexdigest()
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera fixtures ficticios en fixtures/generados/",
        epilog="Los ficheros generados (incluido INDICE.md) no se suben a git: este script es la fuente "
               "de verdad y cada persona los genera en local.")
    parser.add_argument("--hoy", type=date.fromisoformat, default=date.today(),
                        help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()
    hashes = generar(args.hoy, args.salida)
    print(f"Fixtures generados en {args.salida} (hoy = {args.hoy}):")
    for nombre, sha in hashes.items():
        print(f"  {nombre:45s} sha256 {sha[:16]}...")


if __name__ == "__main__":
    main()
