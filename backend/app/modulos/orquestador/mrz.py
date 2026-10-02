"""
Zona de lectura mecanica (MRZ) del pasaporte, formato TD3 de la OACI: dos lineas de 44 caracteres.
Funciones puras sobre el texto del documento (capa de texto u OCR). Se conectan en motor_ia/servicio.py
(tarea 9): sexo desde la MRZ si la extraccion no lo trae y, con ADR-007, confianza baja en los campos
cuyos digitos de control fallan. No hay alerta propia para los digitos de control (spec, seccion 9).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LONGITUD_LINEA = 44
_CARACTERES = re.compile(r"^[A-Z0-9<]{44}$")
_PESOS = (7, 3, 1)


@dataclass(frozen=True)
class Mrz:
    linea1: str
    linea2: str

    @property
    def numero_documento(self) -> str:
        return self.linea2[0:9].rstrip("<")

    @property
    def fecha_nacimiento(self) -> str:
        return self.linea2[13:19]  # AAMMDD

    @property
    def sexo(self) -> str | None:
        """Posicion 21 de la linea 2: 'F', 'M' o 'X'; '<' (sin especificar) -> None."""
        valor = self.linea2[20]
        return valor if valor in "FMX" else None

    @property
    def fecha_vencimiento(self) -> str:
        return self.linea2[21:27]  # AAMMDD


def digito_control(texto: str) -> str | None:
    """Digito de control OACI (pesos 7-3-1; A=10 ... Z=35; '<'=0). None si hay un caracter no valido."""
    total = 0
    for i, c in enumerate(texto):
        if c.isdigit():
            valor = int(c)
        elif "A" <= c <= "Z":
            valor = ord(c) - 55
        elif c == "<":
            valor = 0
        else:
            return None
        total += valor * _PESOS[i % 3]
    return str(total % 10)


def buscar_mrz(texto: str | None) -> Mrz | None:
    """Busca dos lineas consecutivas de 44 caracteres [A-Z0-9<] con la primera empezando por 'P'.
    Tolera los espacios que Tesseract mete dentro de la MRZ."""
    if not texto:
        return None
    lineas = [re.sub(r"\s+", "", linea).upper() for linea in texto.splitlines()]
    lineas = [linea for linea in lineas if linea]
    for primera, segunda in zip(lineas, lineas[1:]):
        if primera.startswith("P") and _CARACTERES.match(primera) and _CARACTERES.match(segunda):
            return Mrz(primera, segunda)
    return None


def validar_digitos(mrz: Mrz) -> dict[str, bool]:
    """Resultado de cada digito de control de la linea 2 (TD3)."""
    l2 = mrz.linea2
    comprobaciones = {
        "numero_documento": (l2[0:9], l2[9]),
        "fecha_nacimiento": (l2[13:19], l2[19]),
        "fecha_vencimiento": (l2[21:27], l2[27]),
        "datos_personales": (l2[28:42], l2[42]),
        "compuesto": (l2[0:10] + l2[13:20] + l2[21:43], l2[43]),
    }
    resultado = {nombre: digito_control(dato) == control for nombre, (dato, control) in comprobaciones.items()}
    # OACI: si los datos personales son todo relleno, su digito de control puede ser '<' ademas de '0'.
    if set(l2[28:42]) == {"<"} and l2[42] in "<0":
        resultado["datos_personales"] = True
    return resultado
