"""
Confianza calculada por el codigo (ADR-007): de campo y de clasificacion. La confianza que devuelve el
modelo no se usa aqui; va a la auditoria. Funciones puras, sin BD ni modelo.
Decisiones y pesos: docs/motor_ia/SPEC_CONFIGURACION.md, seccion 14.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.modulos.configuracion.servicio import FLAGS_MARCADORES, TipoCampo, TipoDocumental
from app.modulos.motor_ia.proveedores.base import PATRON_FECHA_MES_EN_LETRAS, normalizar_fecha

# Confianza de campo = PESO_APARECE * aparece + PESO_FORMATO * formato_valido (campo null -> 0)
PESO_APARECE = 0.6
PESO_FORMATO = 0.4
# Un texto que no aparece exacto cuenta si hay un tramo del documento parecido (p. ej. el OCR leyo
# "GALLE" y el modelo de vision "CALLE"): aparece = parecido.
SIMILITUD_MINIMA = 0.85
# Si fallan los digitos de control de la MRZ, los campos que cubre no pasan de aqui.
TOPE_MRZ_FALLIDA = 0.5

_FECHA_EN_TEXTO = re.compile(r"(?<!\d)(\d{1,4})[/.\- ](\d{1,2})[/.\- ](\d{2,4})(?!\d)")
# Mes en letras ("15 SEP 2026"): el texto ya esta normalizado (mayusculas, sin acentos). Sin cifras ni letras
# pegadas por delante ni cifras por detras, para no cortar un numero o una palabra
_FECHA_MES_EN_TEXTO = re.compile(rf"(?<![0-9A-Z]){PATRON_FECHA_MES_EN_LETRAS}(?!\d)")
_SEPARADOR_ENTRE_DIGITOS = re.compile(r"(?<=\d)[/.\- ](?=\d)")


@dataclass(frozen=True)
class VerificacionMrz:
    """Lo que aporta la MRZ del pasaporte: sus valores y si sus digitos de control son correctos."""
    numero_documento: str
    fecha_nacimiento: str     # AAMMDD
    fecha_vencimiento: str    # AAMMDD
    sexo: str | None
    digitos: Mapping[str, bool]  # validar_digitos: numero_documento, fecha_nacimiento, ..., compuesto
    pagina: int | None = None    # pagina del documento donde esta la MRZ (evidencia del sexo, VAL-003)


# campo de la ficha del pasaporte -> digito de control que lo cubre (ademas del compuesto)
_CAMPOS_MRZ = {"numero_pasaporte": "numero_documento", "fecha_nacimiento": "fecha_nacimiento",
               "fecha_vencimiento": "fecha_vencimiento", "sexo": None}


def normalizar_texto(texto: str | None) -> str:
    """Mayusculas, sin acentos y con los espacios de cada linea colapsados; conserva los saltos de linea."""
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return "\n".join(" ".join(linea.upper().split()) for linea in plano.splitlines())


def texto_del_documento(paginas: Iterable[Any]) -> str:
    """Texto de todas las paginas (capa del PDF u OCR), normalizado."""
    return normalizar_texto("\n".join(getattr(p, "texto", None) or "" for p in paginas))


def confianza_clasificacion(ficha: TipoDocumental | None, texto_normalizado: str) -> float:
    """Proporcion de `marcadores_clasificacion` de la ficha que aparecen en el texto. Sin ficha (p. ej.
    `desconocido`) o sin marcadores: 0."""
    if ficha is None or not ficha.marcadores_clasificacion:
        return 0.0
    encontrados = sum(re.search(m, texto_normalizado, FLAGS_MARCADORES) is not None
                      for m in ficha.marcadores_clasificacion)
    return round(encontrados / len(ficha.marcadores_clasificacion), 3)


def confianzas_de_campos(datos: Mapping[str, Any], ficha: TipoDocumental, texto_normalizado: str,
                         mrz: VerificacionMrz | None = None) -> dict[str, float]:
    """Confianza de cada campo de la ficha: si el valor aparece en el texto y si tiene un formato valido.
    Con la MRZ del pasaporte: si sus digitos fallan, tope de TOPE_MRZ_FALLIDA salvo que el valor este tal cual
    en la zona visual; si cuadran, el valor queda verificado si coincide con ella y sin verificar si no."""
    planos = _sin_separadores(texto_normalizado)
    fechas = _fechas_del_texto(texto_normalizado)
    resultado = {}
    for nombre, campo in ficha.campos.items():
        valor = datos.get(nombre)
        if valor is None:
            resultado[nombre] = 0.0
            continue
        aparece = _aparece(valor, campo.tipo, texto_normalizado, planos, fechas)
        formato = 1.0 if _formato_valido(valor, campo) else 0.0
        if mrz is not None and nombre in _CAMPOS_MRZ:
            if not _digitos_mrz_ok(mrz, nombre):
                # MRZ mal leida: no verifica nada. Tope solo si el valor tampoco esta tal cual en la zona visual
                # (calibracion: el OCR lee mal la MRZ de un pasaporte cuya zona visual esta bien).
                if aparece < 1.0:
                    resultado[nombre] = round(min(PESO_APARECE * aparece + PESO_FORMATO * formato, TOPE_MRZ_FALLIDA), 3)
                    continue
            elif _coincide_con_mrz(mrz, nombre, valor):
                aparece = 1.0
            else:
                aparece = 0.0  # la MRZ, con sus digitos correctos, dice otra cosa: el valor no esta verificado
        resultado[nombre] = round(PESO_APARECE * aparece + PESO_FORMATO * formato, 3)
    return resultado


def _formato_valido(valor: Any, campo) -> bool:
    if campo.tipo is TipoCampo.fecha:
        return isinstance(valor, str) and normalizar_fecha(valor) == valor
    if campo.tipo is TipoCampo.anio:
        return isinstance(valor, int) and not isinstance(valor, bool) and 1000 <= valor <= 9999
    if campo.patron is not None:
        return isinstance(valor, str) and re.fullmatch(campo.patron, valor) is not None
    return True


def _aparece(valor: Any, tipo: TipoCampo, texto: str, planos: str, fechas: set[str]) -> float:
    if tipo is TipoCampo.fecha:
        if not isinstance(valor, str) or normalizar_fecha(valor) != valor:
            return 0.0  # texto no normalizable: no se puede verificar
        if valor in fechas:
            return 1.0
        anio, mes, dia = valor.split("-")
        return 1.0 if f"{dia}{mes}{anio}" in planos else 0.0  # el OCR perdio un separador: "3009/2021"
    buscado = normalizar_texto(str(valor))
    if not buscado:
        return 0.0
    if re.search(rf"(?<![A-Z0-9]){re.escape(buscado)}(?![A-Z0-9])", texto):
        return 1.0
    if tipo is TipoCampo.anio:
        return 0.0
    parecido = _mejor_parecido(buscado, texto)
    return parecido if parecido >= SIMILITUD_MINIMA else 0.0


def _mejor_parecido(buscado: str, texto: str) -> float:
    """Mayor parecido entre el valor y un tramo del texto con el mismo numero de palabras."""
    n = len(buscado.split())
    mejor = 0.0
    for linea in texto.splitlines():
        palabras = linea.split()
        for i in range(max(len(palabras) - n + 1, 1)):
            tramo = " ".join(palabras[i:i + n])
            if abs(len(tramo) - len(buscado)) > max(3, len(buscado) // 5):
                continue
            mejor = max(mejor, SequenceMatcher(None, buscado, tramo).ratio())
    return round(mejor, 3)


def _fechas_del_texto(texto: str) -> set[str]:
    """Fechas del texto en ISO, para verificar las extraidas: numericas y con el mes en letras. Un rango
    ("03 DIC 24-04 FEB 25") da sus dos fechas, cada una por separado; nunca una mezcla."""
    fechas = set()
    for m in _FECHA_EN_TEXTO.finditer(texto):
        if (iso := normalizar_fecha(m.group(0).replace(" ", "/"))) is not None:
            fechas.add(iso)
    for m in _FECHA_MES_EN_TEXTO.finditer(texto):
        if (iso := normalizar_fecha(m.group(0))) is not None:
            fechas.add(iso)
    return fechas


def _sin_separadores(texto: str) -> str:
    return _SEPARADOR_ENTRE_DIGITOS.sub("", texto)


def _digitos_mrz_ok(mrz: VerificacionMrz, campo: str) -> bool:
    propio = _CAMPOS_MRZ[campo]
    return mrz.digitos.get("compuesto", False) and (propio is None or mrz.digitos.get(propio, False))


def _coincide_con_mrz(mrz: VerificacionMrz, campo: str, valor: Any) -> bool:
    if campo == "numero_pasaporte":
        return isinstance(valor, str) and valor.upper() == mrz.numero_documento
    if campo == "sexo":
        return mrz.sexo is not None and str(valor).upper() == mrz.sexo
    aammdd = mrz.fecha_nacimiento if campo == "fecha_nacimiento" else mrz.fecha_vencimiento
    return isinstance(valor, str) and len(valor) == 10 and valor[2:4] + valor[5:7] + valor[8:10] == aammdd
