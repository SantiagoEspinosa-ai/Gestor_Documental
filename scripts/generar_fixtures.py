"""
Genera documentos FICTICIOS de prueba en fixtures/generados/.
Responsable: PERSONA_3. Nunca usar datos reales.

Uso (desde la raiz del repo):
    python scripts/generar_fixtures.py [--hoy AAAA-MM-DD] [--salida DIR]

Determinista: con el mismo --hoy (y las mismas versiones de PyMuPDF y Pillow) los ficheros salen
identicos byte a byte: semilla fija por fichero, metadatos fijos y sin identificador aleatorio en el
PDF. Las fechas son relativas a --hoy (por defecto date.today()) para que los casos no caduquen.

Los campos de cada documento se leen de config/tipos/*.yaml. Si una ficha tiene un campo que este
generador no sabe rellenar (o al reves), o un valor no cumple su `patron`, el script falla.

Los ficheros generados (incluido INDICE.md) NO se suben a git: fixtures/generados/ esta en
.gitignore. Este script es la fuente de verdad y cada persona los genera en local.

Casos (documentos generados):
  - sano:               persona 1; los 3 documentos coinciden y estan vigentes
  - vencido:            persona 2; pasaporte vencido hace 30 dias
  - domicilio_distinto: persona 1; el comprobante lleva otro domicilio que la credencial
  - duplicado:          copia byte a byte de credencial_elector_sano_* (mismo SHA-256)
Modalidades por documento:
  - *_digital.pdf:   capa de texto real (PyMuPDF)
  - *_escaneado.pdf: render a imagen con ruido y rotacion ligera, SIN capa de texto
  - *_foto.jpg:      perspectiva y sombra sobre un fondo (Pillow)
Niveles de dificultad (solo caso sano, escaneado y foto), para decidir cuando el motor pasa del OCR
al modelo de vision. Nombre: {tipo}_sano_{modalidad}_{nivel}.{pdf|jpg}:
  - normal:  los ficheros de arriba, sin sufijo. Sus parametros no se tocan: de sus SHA-256 dependen
             frontend/public/mock-originales y los mocks (scripts/generar_datos_mock.py)
  - dificil: mas ruido, rotacion, perspectiva, desenfoque y compresion; el OCR lee parte de los campos
  - extremo: ademas baja resolucion; el OCR falla en la mayoria, pero una persona aun puede leerlo
  Objetivo de campos leidos con verificar_ocr_fixtures.py: normal ~100 %, dificil 50-80 %, extremo < 30 %.
INDICE.md: archivos, valores esperados por campo y alertas esperadas por folio de prueba, calculadas
a partir de los YAML (reglas y comparaciones) y de config/procesos.yaml (tipos requeridos), y la
seccion "Fixtures de dificultad" con los parametros aplicados a cada fichero.

En total, 57 ficheros: 27 (3 casos x 3 tipos x 3 modalidades), 3 copias del duplicado, 12 de
dificultad, 10 variantes de lectura (2026-10-08) y 5 de la INE (2026-10-09), fuera de la linea base del hito:
  - comprobante_domicilio_sano_{digital,escaneado}_{mes_abreviado,mes_completo,mes_anio_corto}: la fecha de
    emision con el mes en letras ("15 SEP 2026", "15 DE SEPTIEMBRE DE 2026", "15 SEP 26");
  - pasaporte_sano_{digital,foto}_mrz_ruido: un caracter de ruido delante de la primera linea de la MRZ;
  - pasaporte_fechas_incoherentes_digital: expedicion posterior al vencimiento (REG de coherencia);
  - comprobante_domicilio_sano_digital_sin_recibo: "FECHA LIMITE DE PAGO" y "SERVICIO", sin RECIBO ni
    COMPROBANTE.
  Y 7 variantes de la INE (2026-10-09, PR de fix/lectura-fotos):
  - credencial_elector_sano_{digital,foto}_fondo_seguridad: fondo de seguridad; la foto, de baja resolucion;
  - credencial_elector_sano_digital_emision_vigencia: "EMISION AAAA" y "VIGENCIA AAAA" en la misma linea;
  - credencial_elector_sano_{digital,foto}_curp_confundible: CURP impresa con 1 por I y O por 0.
  (El fondo de seguridad y la CURP confundible generan tambien su PDF digital, base de la foto.)
  No forman parte de ningun folio de prueba ni cambian los SHA-256 de los ficheros de antes. Las fotos reales de los impresos del caso sano no salen de aqui: estan en
fixtures/especimenes/ (en git) y las prepara scripts/procesar_especimenes.py.

Tras cambiar este generador, comprueba la legibilidad OCR con scripts/verificar_ocr_fixtures.py
(Tesseract en el contenedor del backend; el comando esta en su docstring).

Pendiente para PERSONA_2 (no tocar los YAML desde aqui):
  - `ejemplos_referencia` de config/tipos/*.yaml apunta a ficheros de fixtures/ que no existen.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import math
import random
import re
import shutil
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import pymupdf
import yaml
from PIL import Image, ImageEnhance, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
DIR_TIPOS = RAIZ / "config" / "tipos"
RUTA_PROCESOS = RAIZ / "config" / "procesos.yaml"
SALIDA = RAIZ / "fixtures" / "generados"
SEMILLA = 20260930
PROCESO = "onboarding"

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
DOMICILIO_ALTERNATIVO = "Calle Distinta 789, Colonia Otra, Ciudad Ejemplo"  # ficticio

# Codigo de pais de la OACI para especimenes ("Utopia"); nunca un pais real
PAIS_MRZ = "UTO"
PROVEEDOR_FICTICIO = "SERVICIOS DE EJEMPLO S.A."

CASOS = {
    "sano": {"persona": 0, "vencimiento_pasaporte": lambda hoy: sumar_anios(hoy, 5),
             "descripcion": "Los tres documentos coinciden y estan vigentes"},
    "vencido": {"persona": 1, "vencimiento_pasaporte": lambda hoy: hoy - timedelta(days=30),
                "descripcion": "Pasaporte vencido hace 30 dias"},
    "domicilio_distinto": {"persona": 0, "vencimiento_pasaporte": lambda hoy: sumar_anios(hoy, 5),
                           "domicilio_comprobante": DOMICILIO_ALTERNATIVO,
                           "descripcion": "El comprobante lleva un domicilio distinto al de la credencial"},
}
# Copias byte a byte: caso -> (caso de origen, tipo copiado)
DUPLICADOS = {"duplicado": ("sano", "credencial_elector")}
MODALIDADES = {"digital": ".pdf", "escaneado": ".pdf", "foto": ".jpg"}

# Folios de prueba: documentos (caso, tipo) que se suben juntos, en orden
FOLIOS = {
    "sano": {"documentos": [("sano", t) for t in ("pasaporte", "credencial_elector", "comprobante_domicilio")],
             "descripcion": CASOS["sano"]["descripcion"]},
    "vencido": {"documentos": [("vencido", t) for t in ("pasaporte", "credencial_elector", "comprobante_domicilio")],
                "descripcion": CASOS["vencido"]["descripcion"]},
    "domicilio_distinto": {"documentos": [("domicilio_distinto", t) for t in
                                          ("pasaporte", "credencial_elector", "comprobante_domicilio")],
                           "descripcion": CASOS["domicilio_distinto"]["descripcion"]},
    "duplicado": {"documentos": [("sano", "credencial_elector"), ("duplicado", "credencial_elector"),
                                 ("sano", "comprobante_domicilio")],
                  "descripcion": "La credencial se sube dos veces (la segunda es una copia byte a byte)"},
    "falta_requerido": {"documentos": [("sano", "pasaporte"), ("sano", "credencial_elector")],
                        "descripcion": "Falta el comprobante de domicilio, requerido por el proceso"},
}
# Severidades de docs/contratos/codigos_alertas.md (las de REG- las fija cada ficha YAML)
SEVERIDAD_CATALOGO = {"CMP-001": "critica", "EXP-001": "bloqueante", "DUP-001": "critica"}

MM = 72 / 25.4  # puntos PDF por milimetro
# Pasaporte (ID-3, 125 x 88 mm) y credencial (ID-1, 85,6 x 54 mm) a escala para que se lean bien
PAGINAS = {
    "pasaporte": (250 * MM, 176 * MM),
    "credencial_elector": (214 * MM, 135 * MM),
    "comprobante_domicilio": pymupdf.paper_size("a4"),
}
DPI_ESCANEO = 200
DPI_FOTO = 150

# Parametros por nivel de dificultad. "normal" son los de siempre: no cambiarlos (ver docstring).
# rotacion: rango de grados (signo al azar); perspectiva: estrechamiento de cada lado de arriba, en
# fraccion del ancho; ruido: peso del ruido en Image.blend; desenfoque: radio gaussiano en px;
# calidad: JPEG. Ajustados con scripts/verificar_ocr_fixtures.py (fixtures/README.md): el OCR cae
# de golpe al bajar la resolucion (foto extrema: 115 dpi da 12 %, 118 dpi da 0 %), asi que un cambio
# pequeno aqui puede sacar un nivel de su rango. Vuelve a verificar despues de tocarlos.
NIVEL_NORMAL = "normal"
NIVELES_DIFICULTAD = ("dificil", "extremo")
CASO_DIFICULTAD = "sano"
PARAMETROS = {
    "escaneado": {
        "normal": {"dpi": DPI_ESCANEO, "contraste": 0.9, "rotacion": (0.4, 1.2), "ruido": 0.06,
                   "desenfoque": 0.5, "calidad": 80},
        "dificil": {"dpi": 150, "contraste": 0.7, "rotacion": (2.0, 3.0), "ruido": 0.18,
                    "desenfoque": 1.1, "calidad": 40},
        "extremo": {"dpi": 105, "contraste": 0.6, "rotacion": (4.0, 6.0), "ruido": 0.22,
                    "desenfoque": 1.3, "calidad": 30},
    },
    "foto": {
        "normal": {"dpi": DPI_FOTO, "perspectiva": (0.03, 0.06), "rotacion": None, "ruido": 0.0,
                   "desenfoque": 0.6, "calidad": 88},
        "dificil": {"dpi": 130, "perspectiva": (0.08, 0.10), "rotacion": (2.0, 3.0), "ruido": 0.18,
                    "desenfoque": 1.3, "calidad": 40},
        "extremo": {"dpi": 115, "perspectiva": (0.12, 0.15), "rotacion": (4.0, 6.0), "ruido": 0.21,
                    "desenfoque": 1.45, "calidad": 30},
    },
}
# Variantes de lectura (2026-10-08): fixtures para fechas con el mes en letras, MRZ con ruido, fechas
# incoherentes y recibos sin RECIBO ni COMPROBANTE. Se generan al final, sin tocar los ficheros de antes.
MESES_ABREVIADOS = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")
MESES_COMPLETOS = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE",
                   "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")
FORMATOS_FECHA = {
    "mes_abreviado": lambda d: f"{d.day:02d} {MESES_ABREVIADOS[d.month - 1]} {d.year}",
    "mes_completo": lambda d: f"{d.day} DE {MESES_COMPLETOS[d.month - 1]} DE {d.year}",
    "mes_anio_corto": lambda d: f"{d.day:02d} {MESES_ABREVIADOS[d.month - 1]} {d.year % 100:02d}",
}
RUIDO_MRZ = "#"  # delante de la primera linea de la MRZ: 45 caracteres
CASO_INCOHERENTE = "fechas_incoherentes"
TITULO_SIN_RECIBO = "AVISO DE SERVICIO"
PR_VARIANTES = "PR de fix/lectura-documentos (2026-10-08)"
PR_VARIANTES_INE = "PR de fix/lectura-fotos (2026-10-09)"
# CURP ficticia de la variante con caracteres confundibles: coherente con la persona 1 (1990-01-01, mujer) y con
# letras que tienen pareja numerica. Impresa con un 1 en lugar de I (posicion 4, de letra) y O en lugar de 0
# (posiciones 6 y 7, de digito): 3 cambios, que la correccion de confusiones del motor debe deshacer.
CURP_CONFUNDIBLE = "SOBI900101MDFGZS01"
CURP_CONFUNDIBLE_IMPRESA = "SOB19OO101MDFGZS01"
NIVEL_FONDO_SEGURIDAD = "dificil"  # foto de baja resolucion (130 dpi) de la credencial con fondo de seguridad

GRIS_TEXTO = (0.35, 0.35, 0.35)
GRIS_MARCA = (0.93, 0.93, 0.93)  # marca de agua muy tenue
AZUL_CABECERA = (0.12, 0.23, 0.42)


class ErrorFixture(Exception):
    """Incoherencia entre YAML, persona y generador: mejor fallar que generar un fixture falso."""


# ---------------------------------------------------------------- fechas, fichas y semillas

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


def cargar_proceso(nombre: str = PROCESO, ruta: Path = RUTA_PROCESOS) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))["procesos"][nombre]


def rng_para(nombre_archivo: str) -> random.Random:
    """Semilla propia por fichero: anadir un caso no cambia los ficheros que ya existian."""
    return random.Random(f"{SEMILLA}:{nombre_archivo}")


def nombre_archivo(tipo: str, caso: str, modalidad: str, nivel: str = NIVEL_NORMAL) -> str:
    sufijo = "" if nivel == NIVEL_NORMAL else f"_{nivel}"
    return f"{tipo}_{caso}_{modalidad}{sufijo}{MODALIDADES[modalidad]}"


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
        domicilio = CASOS[caso].get("domicilio_comprobante", persona["domicilio"]).upper()
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


# ---------------------------------------------------------------- alertas esperadas

def evaluar_reglas(ficha: dict, valores: dict, hoy: date) -> list[dict]:
    """Reglas del YAML incumplidas. Evaluador propio, independiente del modulo validacion: sirve
    de verdad de referencia. Falla si un valor cae en la frontera de una regla (+-1 dia), para que
    el resultado no dependa de si validacion usa > o >=."""
    incumplidas = []
    for regla in ficha.get("reglas", []):
        tipo, valor = regla["tipo"], valores[regla["campo"]]
        if tipo == "patron":
            cumple = bool(re.fullmatch(ficha["campos"][regla["campo"]]["patron"], str(valor)))
        elif tipo == "anio_mayor_o_igual_actual":
            if valor == hoy.year:
                raise ErrorFixture(f"{ficha['nombre']}.{regla['id']}: anio en la frontera de la regla")
            cumple = valor > hoy.year
        elif tipo in ("fecha_posterior_a_hoy", "fecha_posterior_a_hoy_mas_dias",
                      "fecha_no_anterior_a_hoy_menos_dias"):
            limite = {"fecha_posterior_a_hoy": hoy,
                      "fecha_posterior_a_hoy_mas_dias": hoy + timedelta(days=regla.get("dias", 0)),
                      "fecha_no_anterior_a_hoy_menos_dias": hoy - timedelta(days=regla.get("dias", 0))}[tipo]
            if abs((valor - limite).days) <= 1:
                raise ErrorFixture(f"{ficha['nombre']}.{regla['id']}: fecha en la frontera de la regla")
            cumple = valor > limite
        elif tipo == "curp_coincide_con_fecha":
            # posiciones 5-10 de la CURP = fecha (AAMMDD); posicion 17: digito antes de 2000, letra despues
            fecha = valores[regla["campo_relacionado"]]
            cumple = valor[4:10] == fecha.strftime("%y%m%d") and valor[16].isdigit() == (fecha.year < 2000)
        elif tipo == "fecha_anterior_a_campo":
            cumple = valor < valores[regla["campo_relacionado"]]
        else:
            raise ErrorFixture(f"Tipo de regla desconocido '{tipo}' en {ficha['nombre']}: actualiza el generador")
        if not cumple:
            incumplidas.append({"codigo": f"REG-{regla['id']}", "severidad": regla["severidad"],
                                "campo": regla["campo"], "motivo": regla["mensaje"]})
    return incumplidas


def normalizar(valor) -> str:
    texto_plano = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return " ".join(texto_plano.upper().split())


def alertas_folio(folio: str, documentos: dict, hashes: dict, fichas: dict, proceso: dict,
                  hoy: date, modalidad: str = "digital") -> list[dict]:
    """Alertas deterministas esperadas si se suben juntos los documentos del folio de prueba."""
    miembros = FOLIOS[folio]["documentos"]
    alertas = []
    vistos: dict[str, str] = {}
    for caso, tipo in miembros:
        patron_archivo = f"`{tipo}_{caso}_*`"
        donde = f"documento {patron_archivo}"
        for alerta in evaluar_reglas(fichas[tipo], documentos[(caso, tipo)]["valores"], hoy):
            alertas.append({**alerta, "donde": donde})
        sha = hashes[nombre_archivo(tipo, caso, modalidad)]
        if sha in vistos:  # misma huella en el mismo folio
            alertas.append({"codigo": "DUP-001", "severidad": SEVERIDAD_CATALOGO["DUP-001"], "campo": None,
                            "donde": donde, "motivo": f"Mismo SHA-256 que {vistos[sha]} (misma modalidad)"})
        else:
            vistos[sha] = patron_archivo
    for i, (caso_a, tipo_a) in enumerate(miembros):
        for caso_b, tipo_b in miembros[i + 1:]:
            campos = (set(fichas[tipo_a].get("comparaciones", {}).get(tipo_b, []))
                      | set(fichas[tipo_b].get("comparaciones", {}).get(tipo_a, [])))
            va, vb = documentos[(caso_a, tipo_a)]["valores"], documentos[(caso_b, tipo_b)]["valores"]
            for campo in sorted(campos):
                if normalizar(va[campo]) != normalizar(vb[campo]):
                    alertas.append({"codigo": "CMP-001", "severidad": SEVERIDAD_CATALOGO["CMP-001"],
                                    "campo": campo, "donde": "alertas_expediente",
                                    "motivo": f"{campo} distinto entre {tipo_a} y {tipo_b}"})
    presentes = {tipo for _, tipo in miembros}
    for tipo in proceso["tipos_requeridos"]:
        if tipo not in presentes:
            # campo = nombre del tipo que falta (acordado con PERSONA_1)
            alertas.append({"codigo": "EXP-001", "severidad": SEVERIDAD_CATALOGO["EXP-001"], "campo": tipo,
                            "donde": "alertas_expediente",
                            "motivo": f"Falta {tipo}, requerido por el proceso {PROCESO}"})
    return alertas


# ---------------------------------------------------------------- dibujo del documento digital

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


def campos_en_columna(pagina, x, y, campos: dict, valores: dict, paso=30, tam=12, fmt=formatear):
    for campo in campos:  # orden del YAML
        texto(pagina, x, y, campo.replace("_", " ").upper(), tam=7, color=GRIS_TEXTO)
        texto(pagina, x, y + 13, fmt(valores[campo]), tam=tam, fuente="hebo")
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


def dibujar_credencial(pagina, ficha, valores, fondo_seguridad: bool = False, emision: int | None = None,
                       impresos: dict | None = None):
    """Sin parametros opcionales, igual que siempre. `fondo_seguridad`: lineas onduladas finas detras de los
    datos. `emision`: la ultima linea es "EMISION <anio>  VIGENCIA <anio>" (las dos en la misma linea).
    `impresos`: valores que se imprimen en lugar de los esperados (p. ej. una CURP con confusiones)."""
    cabecera(pagina, ficha["nombre_visible"])
    if fondo_seguridad:
        fondo_de_seguridad(pagina)
    marca_de_agua_lateral(pagina)
    silueta(pagina, pymupdf.Rect(20, 52, 150, 216))
    mostrados = {**valores, **(impresos or {})}
    if emision is None:
        campos_en_columna(pagina, 172, 56, ficha["campos"], mostrados, paso=31, tam=11)
        return
    campos = {c: d for c, d in ficha["campos"].items() if c != "vigencia"}
    y = campos_en_columna(pagina, 172, 56, campos, mostrados, paso=31, tam=11)
    texto(pagina, 172, y + 13, f"EMISIÓN {emision}   VIGENCIA {valores['vigencia']}", tam=11, fuente="hebo")


def fondo_de_seguridad(pagina) -> None:
    """Fondo de seguridad ficticio: lineas onduladas finas en tonos claros, como las de una credencial."""
    ancho, alto = pagina.rect.width, pagina.rect.height
    for k in range(0, int(alto) + 40, 6):
        puntos = [pymupdf.Point(x, 40 + k + 5 * math.sin(x / 9 + k / 7)) for x in range(0, int(ancho) + 6, 6)]
        pagina.draw_polyline(puntos, color=(0.72, 0.80, 0.88), width=0.6)


def dibujar_comprobante(pagina, ficha, valores, rng: random.Random, fmt=formatear, titulo: str | None = None,
                        fecha_limite_pago: date | None = None):
    cabecera(pagina, f"{valores['proveedor']} - {titulo or ficha['nombre_visible']}", alto_barra=46)
    y = campos_en_columna(pagina, 50, 90, ficha["campos"], valores, paso=36, fmt=fmt)
    if fecha_limite_pago is not None:  # variante sin_recibo
        texto(pagina, 50, y, "FECHA LIMITE DE PAGO", tam=7, color=GRIS_TEXTO)
        texto(pagina, 50, y + 13, formatear(fecha_limite_pago), tam=12, fuente="hebo")
        y += 36
    # Detalle decorativo con importes ficticios (dependen solo de la semilla del fichero)
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


# ---------------------------------------------------------------- modalidades

def metadatos(ficha: dict, caso: str, modalidad: str, hoy: date) -> dict:
    fecha_pdf = f"D:{hoy.strftime('%Y%m%d')}000000Z"
    return {"title": f"{ficha['nombre_visible']} (ficticio)", "author": "generar_fixtures.py",
            "subject": f"Documento ficticio para pruebas. Sin validez. Caso {caso}, {modalidad}.",
            "keywords": "", "creator": "generar_fixtures.py", "producer": "PyMuPDF",
            "creationDate": fecha_pdf, "modDate": fecha_pdf}


def generar_digital(tipo: str, caso: str, ficha: dict, valores: dict, hoy: date, destino: Path,
                    formato_fecha=None, ruido_mrz: str = "", titulo: str | None = None,
                    fecha_limite_pago: date | None = None, credencial: dict | None = None) -> list[str]:
    """PDF con capa de texto real. Devuelve el texto que debe poder extraerse. Los parametros opcionales son
    para las variantes de lectura; sin ellos, el PDF sale igual que siempre."""
    fmt = formatear if formato_fecha is None else (
        lambda v: formato_fecha(v) if isinstance(v, date) else formatear(v))
    doc = pymupdf.open()
    pagina = doc.new_page(width=PAGINAS[tipo][0], height=PAGINAS[tipo][1])
    esperado = [fmt(valores[c]) for c in ficha["campos"]]
    if tipo == "pasaporte":
        mrz = generar_mrz(valores)
        validar_mrz(*mrz, valores)
        if ruido_mrz:
            mrz = (ruido_mrz + mrz[0], mrz[1])
        dibujar_pasaporte(pagina, ficha, valores, mrz)
        esperado += list(mrz)
    elif tipo == "credencial_elector":
        if credencial:
            dibujar_credencial(pagina, ficha, valores, **credencial)
            impresos = credencial.get("impresos") or {}
            esperado = [fmt(impresos.get(c, valores[c])) for c in ficha["campos"]]
        else:
            dibujar_credencial(pagina, ficha, valores)
    elif formato_fecha is None and titulo is None and fecha_limite_pago is None:
        dibujar_comprobante(pagina, ficha, valores, rng_para(destino.name))
    else:
        dibujar_comprobante(pagina, ficha, valores, rng_para(destino.name), fmt=fmt, titulo=titulo,
                            fecha_limite_pago=fecha_limite_pago)
    doc.set_metadata(metadatos(ficha, caso, "digital", hoy))
    doc.save(destino, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return esperado


def renderizar(ruta_pdf: Path, dpi: int, modo: str) -> Image.Image:
    espacio = pymupdf.csGRAY if modo == "L" else pymupdf.csRGB
    with pymupdf.open(ruta_pdf) as doc:
        pix = doc[0].get_pixmap(dpi=dpi, colorspace=espacio, alpha=False)
        return Image.frombytes(modo, (pix.width, pix.height), pix.samples)


def ruido(tamano: tuple[int, int], rng: random.Random) -> Image.Image:
    """Ruido uniforme reproducible (Image.effect_noise de Pillow no admite semilla)."""
    return Image.frombytes("L", tamano, rng.randbytes(tamano[0] * tamano[1]))


def generar_escaneado(digital: Path, destino: Path, ficha: dict, caso: str, hoy: date,
                      nivel: str = NIVEL_NORMAL) -> dict:
    """Imagen en gris con ruido y rotacion, dentro de un PDF SIN capa de texto. Devuelve los
    parametros aplicados. Con menos dpi la imagen tiene menos pixeles y la pagina el mismo tamano."""
    p = PARAMETROS["escaneado"][nivel]
    rng = rng_para(destino.name)
    img = ImageEnhance.Contrast(renderizar(digital, p["dpi"], "L")).enhance(p["contraste"])
    angulo = rng.uniform(*p["rotacion"]) * rng.choice((-1, 1))
    img = img.rotate(angulo, resample=Image.BICUBIC, expand=True, fillcolor=255)
    img = Image.blend(img, ruido(img.size, rng), p["ruido"]).filter(ImageFilter.GaussianBlur(p["desenfoque"]))
    jpg = io.BytesIO()
    img.save(jpg, "JPEG", quality=p["calidad"])
    doc = pymupdf.open()
    pagina = doc.new_page(width=img.width * 72 / p["dpi"], height=img.height * 72 / p["dpi"])
    pagina.insert_image(pagina.rect, stream=jpg.getvalue())
    modalidad = "escaneado" if nivel == NIVEL_NORMAL else f"escaneado, nivel {nivel}"
    doc.set_metadata(metadatos(ficha, caso, modalidad, hoy))
    doc.save(destino, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    with pymupdf.open(destino) as comprobacion:
        if comprobacion[0].get_text().strip():
            raise ErrorFixture(f"{destino.name}: el escaneado no debe tener capa de texto")
    return {"dpi": p["dpi"], "rotacion": angulo, "ruido": p["ruido"], "desenfoque": p["desenfoque"],
            "calidad": p["calidad"], "contraste": p["contraste"]}


def coeficientes_perspectiva(destino: list, origen: list) -> list[float]:
    """Coeficientes de Image.PERSPECTIVE que llevan cada punto de destino a su punto de origen."""
    filas, b = [], []
    for (x, y), (u, v) in zip(destino, origen):
        filas.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        filas.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    n = 8  # eliminacion de Gauss con pivote parcial (sin numpy)
    m = [fila + [bi] for fila, bi in zip(filas, b)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [a - f * c for a, c in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def rotar_puntos(puntos: list, grados: float, centro: tuple[float, float]) -> list:
    angulo = math.radians(grados)
    cx, cy = centro
    return [(cx + (x - cx) * math.cos(angulo) - (y - cy) * math.sin(angulo),
             cy + (x - cx) * math.sin(angulo) + (y - cy) * math.cos(angulo)) for x, y in puntos]


def generar_foto(digital: Path, destino: Path, nivel: str = NIVEL_NORMAL) -> dict:
    """Foto de movil simulada: perspectiva, sombra y luz desigual sobre una mesa. Devuelve los
    parametros aplicados. Los pasos extra de los niveles (rotacion, ruido) solo tiran del generador
    aleatorio si el nivel los tiene, asi el nivel normal sale igual byte a byte."""
    p = PARAMETROS["foto"][nivel]
    rng = rng_para(destino.name)
    img = renderizar(digital, p["dpi"], "RGB")
    w, h = img.size
    margen = int(0.08 * max(w, h))
    lienzo = (w + 2 * margen, h + 2 * margen)
    # Mesa con textura ligera
    textura = ruido((lienzo[0] // 8, lienzo[1] // 8), rng).resize(lienzo, Image.BILINEAR)
    fondo = Image.blend(Image.new("RGB", lienzo, (118, 104, 88)), Image.merge("RGB", (textura,) * 3), 0.10)
    # Perspectiva: la parte de arriba se ve mas estrecha (camara algo inclinada)
    t = rng.uniform(*p["perspectiva"]) * w
    j = lambda: rng.uniform(-0.01, 0.01) * h
    destino_quad = [(margen + t, margen + j()), (margen + w - t, margen + j()),
                    (margen + w, margen + h + j()), (margen, margen + h + j())]
    angulo = 0.0
    if p["rotacion"]:  # documento girado sobre la mesa (el margen deja sitio hasta ~6 grados)
        angulo = rng.uniform(*p["rotacion"]) * rng.choice((-1, 1))
        destino_quad = rotar_puntos(destino_quad, angulo, (lienzo[0] / 2, lienzo[1] / 2))
    coef = coeficientes_perspectiva(destino_quad, [(0, 0), (w, 0), (w, h), (0, h)])
    documento = img.transform(lienzo, Image.PERSPECTIVE, coef, Image.BICUBIC)
    mascara = Image.new("L", (w, h), 255).transform(lienzo, Image.PERSPECTIVE, coef, Image.BICUBIC)
    # Sombra proyectada bajo el documento
    sombra = Image.new("L", lienzo, 0)
    sombra.paste(mascara, (int(margen * 0.15), int(margen * 0.2)))
    sombra = sombra.filter(ImageFilter.GaussianBlur(margen * 0.12)).point(lambda p: int(p * 0.6))
    fondo = Image.composite(ImageEnhance.Brightness(fondo).enhance(0.45), fondo, sombra)
    fondo.paste(documento, (0, 0), mascara)
    # Luz desigual: un lado algo mas oscuro
    # (se gira un degradado mas grande y se recorta el centro: asi no quedan esquinas sin luz)
    lado = int(1.5 * max(lienzo))
    gradiente = Image.linear_gradient("L").resize((lado, lado), Image.BILINEAR)
    gradiente = gradiente.rotate(rng.uniform(20, 70), resample=Image.BILINEAR)
    x0, y0 = (lado - lienzo[0]) // 2, (lado - lienzo[1]) // 2
    gradiente = gradiente.crop((x0, y0, x0 + lienzo[0], y0 + lienzo[1])).point(lambda p: int(p * 0.7))
    foto = Image.composite(ImageEnhance.Brightness(fondo).enhance(0.75), fondo, gradiente)
    if p["ruido"]:  # ruido del sensor
        foto = Image.blend(foto, Image.merge("RGB", (ruido(lienzo, rng),) * 3), p["ruido"])
    foto.filter(ImageFilter.GaussianBlur(p["desenfoque"])).save(destino, "JPEG", quality=p["calidad"])
    return {"dpi": p["dpi"], "perspectiva": t / w, "rotacion": angulo, "ruido": p["ruido"],
            "desenfoque": p["desenfoque"], "calidad": p["calidad"]}


# ---------------------------------------------------------------- generacion e INDICE.md

def comprobar_capa_texto(ruta: Path, esperado: list[str]) -> None:
    with pymupdf.open(ruta) as doc:
        contenido = "\n".join(p.get_text() for p in doc)
    faltan = [e for e in esperado if e not in contenido]
    if faltan:
        raise ErrorFixture(f"{ruta.name}: la capa de texto no contiene {faltan}")


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def escribir_indice(salida: Path, hoy: date, fichas: dict, proceso: dict, documentos: dict,
                    hashes: dict, dificultad: dict, variantes: dict | None = None) -> Path:
    persona = lambda i: f"persona {i + 1} ({PERSONAS_FICTICIAS[i]['nombre_completo'].upper()})"
    iso = lambda v: v.isoformat() if isinstance(v, date) else str(v)
    lineas = [
        "# INDICE de fixtures ficticios", "",
        f"Generado por `scripts/generar_fixtures.py` con `--hoy {hoy.isoformat()}` (semilla {SEMILLA}).",
        "No se sube a git: regeneralo en local con el script, que es la fuente de verdad.",
        "Todos los datos son ficticios. Byte a byte reproducible con el mismo `--hoy` y las mismas",
        "versiones de PyMuPDF y Pillow.", "",
        "Fechas de los valores esperados en ISO 8601 (AAAA-MM-DD); en los documentos aparecen como",
        "DD/MM/AAAA.", "",
        "## Archivos", "",
        "| Archivo | Caso | Tipo | Modalidad | Persona | SHA-256 |", "|---|---|---|---|---|---|",
    ]
    for (caso, tipo), doc in documentos.items():
        for modalidad in MODALIDADES:
            archivo = nombre_archivo(tipo, caso, modalidad)
            lineas.append(f"| `{archivo}` | {caso} | {tipo} | {modalidad} | {persona(doc['persona'])} "
                          f"| `{hashes[archivo][:16]}...` |")
    lineas += ["", "## Valores esperados por documento", "",
               "Iguales en las tres modalidades del mismo documento."]
    for (caso, tipo), doc in documentos.items():
        archivos = ", ".join(f"`{nombre_archivo(tipo, caso, m)}`" for m in MODALIDADES)
        lineas += ["", f"### {caso} / {tipo}", "", f"{persona(doc['persona'])}. Archivos: {archivos}.", ""]
        if "copia_de" in doc:
            lineas += [f"Copia byte a byte de `{tipo}_{doc['copia_de']}_*` (mismo SHA-256 en cada modalidad).", ""]
        lineas += ["| Campo | Valor esperado |", "|---|---|"]
        lineas += [f"| `{campo}` | {iso(doc['valores'][campo])} |" for campo in fichas[tipo]["campos"]]
        if tipo == "pasaporte":
            lineas += ["", "MRZ:", "", "```", *generar_mrz(doc["valores"]), "```"]
    lineas += ["", f"## Folios de prueba y alertas esperadas (proceso `{PROCESO}`)", "",
               "Sube los documentos de cada folio en ese orden y en la misma modalidad (DUP-001 solo",
               "salta si los dos ficheros son identicos). Solo se listan alertas deterministas:",
               "VAL-002, CLS-002 y VIS-xxx dependen del modelo. Severidad de REG- segun la ficha YAML;",
               "la de CMP-001, EXP-001 y DUP-001 segun `docs/contratos/codigos_alertas.md`."]
    for folio, definicion in FOLIOS.items():
        miembros = ", ".join(f"`{tipo}_{caso}_*`" for caso, tipo in definicion["documentos"])
        lineas += ["", f"### Folio `{folio}`", "", f"{definicion['descripcion']}. Documentos: {miembros}.", ""]
        alertas = alertas_folio(folio, documentos, hashes, fichas, proceso, hoy)
        if not alertas:
            lineas.append("Alertas esperadas: ninguna.")
            continue
        lineas += ["| Codigo | Severidad | Donde | Campo | Motivo |", "|---|---|---|---|---|"]
        lineas += [f"| `{a['codigo']}` | {a['severidad']} | {a['donde']} | {a['campo'] or '-'} | {a['motivo']} |"
                   for a in alertas]
    lineas += ["", "## Fixtures de dificultad", "",
               f"Escaneado y foto del caso `{CASO_DIFICULTAD}` con mas degradacion, para decidir cuando el motor",
               "pasa del OCR al modelo de vision. El nivel `normal` son los `*_sano_escaneado.pdf` y",
               "`*_sano_foto.jpg` de arriba. Objetivo de campos leidos con `scripts/verificar_ocr_fixtures.py`:",
               "normal ~100 %, dificil 50-80 %, extremo < 30 %. No forman parte de ningun folio de prueba.", "",
               "| Archivo | Tipo | Modalidad | Nivel | Parametros aplicados | SHA-256 |", "|---|---|---|---|---|---|"]
    lineas += [f"| `{archivo}` | {d['tipo']} | {d['modalidad']} | {d['nivel']} | "
               f"{describir_parametros(d['parametros'])} | `{hashes[archivo][:16]}...` |"
               for archivo, d in dificultad.items()]
    for tipo in fichas:
        valores = documentos[(CASO_DIFICULTAD, tipo)]["valores"]
        lineas += ["", f"### Valores esperados: {tipo}", "",
                   f"Los mismos que `{CASO_DIFICULTAD} / {tipo}`.", "", "| Campo | Valor esperado |", "|---|---|"]
        lineas += [f"| `{campo}` | {iso(valores[campo])} |" for campo in fichas[tipo]["campos"]]
        if tipo == "pasaporte":
            lineas += ["", "MRZ:", "", "```", *generar_mrz(valores), "```"]
    for pr in dict.fromkeys(v.get("pr", PR_VARIANTES) for v in (variantes or {}).values()):
        del_pr = {a: v for a, v in variantes.items() if v.get("pr", PR_VARIANTES) == pr}
        lineas += escribir_variantes(pr, del_pr, hashes, fichas, iso)
    ruta = salida / "INDICE.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    return ruta


def escribir_variantes(pr: str, variantes: dict, hashes: dict, fichas: dict, iso) -> list[str]:
    """Seccion de INDICE.md con las variantes de lectura anadidas en un PR, fuera de la linea base del hito."""
    lineas = []
    if variantes:
        lineas += ["", f"## Variantes de lectura (anadidas en el {pr})", "",
                   "**Anadidas en este PR, fuera de la linea base del hito**: no forman parte de ningun folio de",
                   "prueba ni de los SHA-256 registrados de los ficheros de antes. Cubren fallos vistos con",
                   "documentos reales: fechas con el mes en letras, MRZ con ruido de OCR, fechas incoherentes",
                   "y recibos sin RECIBO ni COMPROBANTE.", "",
                   "| Archivo | Tipo | Modalidad | Que prueba | Alertas deterministas esperadas | SHA-256 |",
                   "|---|---|---|---|---|---|"]
        for archivo, v in variantes.items():
            alertas = ", ".join(f"`{a['codigo']}` ({a['severidad']}, {a['campo']})" for a in v["alertas"]) or "ninguna"
            lineas.append(f"| `{archivo}` | {v['tipo']} | {v['modalidad']} | {v['prueba']} | {alertas} "
                          f"| `{hashes[archivo][:16]}...` |")
        vistos = []
        for archivo, v in variantes.items():
            clave = (v["tipo"], tuple(sorted((k, iso(x)) for k, x in v["valores"].items())))
            if clave in vistos:
                continue
            vistos.append(clave)
            mismos = [a for a, w in variantes.items()
                      if (w["tipo"], tuple(sorted((k, iso(x)) for k, x in w["valores"].items()))) == clave]
            lineas += ["", f"### Valores esperados: {', '.join(f'`{a}`' for a in mismos)}", "",
                       "| Campo | Valor esperado |", "|---|---|"]
            lineas += [f"| `{campo}` | {iso(v['valores'][campo])} |" for campo in fichas[v["tipo"]]["campos"]]
    return lineas


def generar(hoy: date, salida: Path = SALIDA) -> dict[str, str]:
    """Genera todos los fixtures e INDICE.md y devuelve {nombre_archivo: sha256}."""
    fichas, proceso = cargar_fichas(), cargar_proceso()
    for persona in PERSONAS_FICTICIAS:
        validar_persona(persona, fichas)
    salida.mkdir(parents=True, exist_ok=True)
    documentos: dict[tuple[str, str], dict] = {}
    for caso, definicion in CASOS.items():
        persona = PERSONAS_FICTICIAS[definicion["persona"]]
        for tipo, ficha in fichas.items():
            valores = valores_documento(tipo, persona, caso, hoy)
            validar_valores(tipo, valores, ficha)
            evaluar_reglas(ficha, valores, hoy)  # falla pronto si un valor cae en una frontera
            documentos[(caso, tipo)] = {"valores": valores, "persona": definicion["persona"]}
            digital = salida / nombre_archivo(tipo, caso, "digital")
            comprobar_capa_texto(digital, generar_digital(tipo, caso, ficha, valores, hoy, digital))
            generar_escaneado(digital, salida / nombre_archivo(tipo, caso, "escaneado"), ficha, caso, hoy)
            generar_foto(digital, salida / nombre_archivo(tipo, caso, "foto"))
    for caso, (origen, tipo) in DUPLICADOS.items():
        documentos[(caso, tipo)] = {**documentos[(origen, tipo)], "copia_de": origen}
        for modalidad in MODALIDADES:
            shutil.copyfile(salida / nombre_archivo(tipo, origen, modalidad),
                            salida / nombre_archivo(tipo, caso, modalidad))
    dificultad = generar_dificultad(salida, fichas, hoy)
    variantes = generar_variantes(salida, fichas, documentos, hoy)  # al final: no cambia nada de lo anterior
    hashes = {nombre_archivo(t, c, m): sha256(salida / nombre_archivo(t, c, m))
              for (c, t) in documentos for m in MODALIDADES}
    hashes |= {archivo: sha256(salida / archivo) for archivo in dificultad}
    hashes |= {archivo: sha256(salida / archivo) for archivo in variantes}
    escribir_indice(salida, hoy, fichas, proceso, documentos, hashes, dificultad, variantes)
    return hashes


def generar_variantes(salida: Path, fichas: dict, documentos: dict, hoy: date) -> dict[str, dict]:
    """Variantes de lectura (2026-10-08). Devuelve {archivo: {tipo, modalidad, prueba, valores, alertas}}."""
    variantes: dict[str, dict] = {}

    def anotar(ruta: Path, tipo: str, modalidad: str, prueba: str, valores: dict, alertas=()) -> None:
        variantes[ruta.name] = {"tipo": tipo, "modalidad": modalidad, "prueba": prueba, "valores": valores,
                                "alertas": list(alertas)}

    # Comprobante con la fecha de emision con el mes en letras, en digital y escaneado
    tipo, ficha = "comprobante_domicilio", fichas["comprobante_domicilio"]
    valores = documentos[("sano", tipo)]["valores"]
    for variante, formato in FORMATOS_FECHA.items():
        digital = salida / nombre_archivo(tipo, "sano", "digital", variante)
        comprobar_capa_texto(digital, generar_digital(tipo, "sano", ficha, valores, hoy, digital, formato_fecha=formato))
        escaneado = salida / nombre_archivo(tipo, "sano", "escaneado", variante)
        generar_escaneado(digital, escaneado, ficha, "sano", hoy)
        prueba = f'fecha_emision con el mes en letras: "{formato(valores["fecha_emision"])}"'
        anotar(digital, tipo, "digital", prueba, valores)
        anotar(escaneado, tipo, "escaneado", prueba, valores)

    # Comprobante sin RECIBO ni COMPROBANTE, con FECHA LIMITE DE PAGO y SERVICIO
    digital = salida / nombre_archivo(tipo, "sano", "digital", "sin_recibo")
    comprobar_capa_texto(digital, generar_digital(tipo, "sano", ficha, valores, hoy, digital, titulo=TITULO_SIN_RECIBO,
                                                  fecha_limite_pago=valores["fecha_emision"] + timedelta(days=20)))
    with pymupdf.open(digital) as doc:
        contenido = " ".join(p.get_text() for p in doc).upper()
    if "RECIBO" in contenido or "COMPROBANTE" in contenido or "SERVICIO" not in contenido:
        raise ErrorFixture(f"{digital.name}: debe llevar SERVICIO y no RECIBO ni COMPROBANTE")
    anotar(digital, tipo, "digital", 'marcadores "FECHA LIMITE DE PAGO" y "SERVICIO", sin RECIBO ni COMPROBANTE',
           valores)

    # Pasaporte con un caracter de ruido delante de la primera linea de la MRZ, en digital y foto
    tipo, ficha = "pasaporte", fichas["pasaporte"]
    valores = documentos[("sano", tipo)]["valores"]
    digital = salida / nombre_archivo(tipo, "sano", "digital", "mrz_ruido")
    comprobar_capa_texto(digital, generar_digital(tipo, "sano", ficha, valores, hoy, digital, ruido_mrz=RUIDO_MRZ))
    foto = salida / nombre_archivo(tipo, "sano", "foto", "mrz_ruido")
    generar_foto(digital, foto)
    prueba = f'MRZ con "{RUIDO_MRZ}" delante de la primera linea (45 caracteres)'
    anotar(digital, tipo, "digital", prueba, valores)
    anotar(foto, tipo, "foto", prueba, valores)

    # Pasaporte con la expedicion posterior al vencimiento: se completa con su REG de coherencia
    valores = {**valores, "fecha_expedicion": valores["fecha_vencimiento"] + timedelta(days=365)}
    validar_valores(tipo, valores, ficha)
    alertas = evaluar_reglas(ficha, valores, hoy)
    if not alertas:
        raise ErrorFixture(f"{CASO_INCOHERENTE}: debe incumplir una regla de coherencia")
    digital = salida / nombre_archivo(tipo, CASO_INCOHERENTE, "digital")
    comprobar_capa_texto(digital, generar_digital(tipo, CASO_INCOHERENTE, ficha, valores, hoy, digital))
    anotar(digital, tipo, "digital", "expedicion posterior al vencimiento", valores, alertas)

    # INE (2026-10-09, PR de fix/lectura-fotos)
    tipo, ficha = "credencial_elector", fichas["credencial_elector"]
    valores = documentos[("sano", tipo)]["valores"]

    def anotar_ine(ruta: Path, modalidad: str, prueba: str, vals: dict) -> None:
        anotar(ruta, tipo, modalidad, prueba, vals)
        variantes[ruta.name]["pr"] = PR_VARIANTES_INE

    # Foto de baja resolucion con fondo de seguridad: el OCR saca poco texto
    digital = salida / nombre_archivo(tipo, "sano", "digital", "fondo_seguridad")
    comprobar_capa_texto(digital, generar_digital(tipo, "sano", ficha, valores, hoy, digital,
                                                  credencial={"fondo_seguridad": True}))
    foto = salida / nombre_archivo(tipo, "sano", "foto", "fondo_seguridad")
    generar_foto(digital, foto, NIVEL_FONDO_SEGURIDAD)
    anotar_ine(digital, "digital", "fondo de seguridad (lineas onduladas) detras de los datos", valores)
    anotar_ine(foto, "foto", f"fondo de seguridad en una foto de baja resolucion (nivel {NIVEL_FONDO_SEGURIDAD})",
               valores)

    # EMISION y VIGENCIA en la misma linea
    emision = valores["vigencia"] - 10
    digital = salida / nombre_archivo(tipo, "sano", "digital", "emision_vigencia")
    comprobar_capa_texto(digital, generar_digital(tipo, "sano", ficha, valores, hoy, digital,
                                                  credencial={"emision": emision}))
    anotar_ine(digital, "digital", f'"EMISION {emision}" y "VIGENCIA {valores["vigencia"]}" en la misma linea: '
                                   "vigencia esperada, la de VIGENCIA", valores)

    # CURP impresa con caracteres confundibles (1 por I en una letra; O por 0 en dos digitos)
    valores_curp = {**valores, "curp": CURP_CONFUNDIBLE}
    validar_valores(tipo, valores_curp, ficha)
    if evaluar_reglas(ficha, valores_curp, hoy):
        raise ErrorFixture("La CURP ficticia de la variante debe cumplir las reglas de la ficha")
    for modalidad in ("digital", "foto"):
        ruta_v = salida / nombre_archivo(tipo, "sano", modalidad, "curp_confundible")
        if modalidad == "digital":
            comprobar_capa_texto(ruta_v, generar_digital(tipo, "sano", ficha, valores_curp, hoy, ruta_v,
                                                         credencial={"impresos": {"curp": CURP_CONFUNDIBLE_IMPRESA}}))
        else:
            generar_foto(salida / nombre_archivo(tipo, "sano", "digital", "curp_confundible"), ruta_v)
        anotar_ine(ruta_v, modalidad, f'CURP impresa "{CURP_CONFUNDIBLE_IMPRESA}" (1 por I y O por 0); esperada la '
                                      "correcta", valores_curp)
    return variantes


def generar_dificultad(salida: Path, fichas: dict, hoy: date) -> dict[str, dict]:
    """Escaneado y foto de cada tipo del caso sano en los niveles dificil y extremo, a partir de su
    PDF digital (ya generado). Devuelve {archivo: {tipo, modalidad, nivel, parametros}}."""
    dificultad = {}
    for tipo, ficha in fichas.items():
        digital = salida / nombre_archivo(tipo, CASO_DIFICULTAD, "digital")
        for modalidad in ("escaneado", "foto"):
            for nivel in NIVELES_DIFICULTAD:
                destino = salida / nombre_archivo(tipo, CASO_DIFICULTAD, modalidad, nivel)
                parametros = (generar_escaneado(digital, destino, ficha, CASO_DIFICULTAD, hoy, nivel)
                              if modalidad == "escaneado" else generar_foto(digital, destino, nivel))
                dificultad[destino.name] = {"tipo": tipo, "modalidad": modalidad, "nivel": nivel,
                                            "parametros": parametros}
    return dificultad


def describir_parametros(p: dict) -> str:
    partes = [f"{p['dpi']} dpi", f"rotacion {p['rotacion']:+.2f} grados"]
    if "perspectiva" in p:
        partes.append(f"perspectiva {p['perspectiva']:.1%}")
    if "contraste" in p:
        partes.append(f"contraste {p['contraste']}")
    partes += [f"ruido {p['ruido']}", f"desenfoque {p['desenfoque']} px", f"JPEG {p['calidad']}"]
    return ", ".join(partes)


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
    print(f"{len(hashes)} fixtures e INDICE.md generados en {args.salida} (hoy = {args.hoy}):")
    for nombre, sha in hashes.items():
        print(f"  {nombre:52s} sha256 {sha[:16]}...")


if __name__ == "__main__":
    main()
