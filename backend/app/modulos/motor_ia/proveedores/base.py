"""
Utilidades comunes de los proveedores LLM (Ollama y, mas adelante, OpenRouter): parametros de llamada,
parseo estricto del JSON, postprocesado de la respuesta, imagenes y texto.
Reglas de vision y parseo: docs/motor_ia/SPEC_CONFIGURACION.md, seccion 4.
"""
from __future__ import annotations

import io
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.modulos.motor_ia.interfaces import Modalidad, Pagina, ResultadoClasificacion, ResultadoExtraccion

# --- Parametros de llamada (decididos en la tarea 6; ver la spec) ---
TEMPERATURA = 0
NUM_PREDICT = 800                    # tope de salida: sin el, una respuesta llego a repetir "<<<<" 10 minutos
NUM_CTX = 16384                      # medido: 4 paginas A4 a 1000 px + prompt + 20 000 caracteres = 13 476
                                     # tokens de entrada; + NUM_PREDICT deja ~2 100 de margen
ANCHO_MAX_IMAGEN = 1000              # px; sube aciertos y ahorra ~20 % de tiempo (pruebas_ollama.md)
MAX_PAGINAS_POR_LLAMADA_VISION = 4   # mas paginas se procesan por lotes
MAX_CARACTERES_TEXTO = 20000
TIMEOUT_TEXTO_S = 120
# Vision: medido en CPU, 1 pagina A4 = 133 s y 4 paginas = 499 s solo de lectura del prompt.
TIMEOUT_VISION_BASE_S = 60
TIMEOUT_VISION_POR_PAGINA_S = 150
KEEP_ALIVE = "10m"
# Regla del enrutador (spec, seccion 3): modelo de texto si TODAS las paginas tienen al menos estos caracteres
# de texto (capa del PDF u OCR), sin contar espacios; si no, vision. Mismo valor que
# orquestador.modalidad.UMBRAL_CARACTERES_POR_PAGINA (un test lo comprueba).
MIN_CARACTERES_TEXTO_POR_PAGINA = 30
# Riesgo 2 del plan (OCR malo -> vision): si la extraccion con texto deja vacios al menos esta fraccion de
# los campos obligatorios, se reintenta con vision.
FRACCION_OBLIGATORIOS_VACIOS_REINTENTO = 0.5

DESCONOCIDO = "desconocido"
MARCA_RECORTE = "[texto recortado]"


class ErrorProveedor(Exception):
    """El proveedor no respondio bien (conexion, timeout, HTTP, modelo inexistente): probar el respaldo."""


class ErrorRespuestaInvalida(ErrorProveedor):
    """El JSON del modelo sigue siendo invalido tras el reintento de correccion (alerta SYS-002)."""


class RespuestaNoValida(ValueError):
    """La respuesta no cumple la forma pedida; el mensaje se usa en la instruccion de correccion."""


@dataclass
class InfoLlamada:
    """Registro de la ultima operacion de un proveedor: modelo usado, tiempos y tokens (auditoria)."""
    proveedor: str
    modelo: str
    segundos: float = 0.0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    peticiones: int = 0
    reintentos: int = 0
    lotes: int = 1
    entrada: str = ""            # "texto" (sin imagenes) o "vision"
    motivo: str | None = None    # p. ej. por que se reintento con vision


# --- Parseo estricto ---

class _Clasificacion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tipo_documental_detectado: str
    confianza: Any = Field(...)
    razonamiento: Any = ""


class _Extraccion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    datos_extraidos: dict[str, Any]
    nivel_confianza_por_campo: dict[str, Any]
    evidencia_por_campo: dict[str, Any]
    observaciones_visuales: list[Any] = []

    @field_validator("observaciones_visuales", mode="before")
    @classmethod
    def _lista(cls, valor):
        if valor is None:
            return []
        return [valor] if isinstance(valor, str) else valor


_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def limpiar_json(texto: str) -> str:
    """Quita marcas ```json y cualquier texto antes del primer '{' o despues del ultimo '}'."""
    texto = _FENCE.sub("", texto.strip())
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio:fin + 1] if inicio != -1 and fin > inicio else texto


def _parsear(texto: str, modelo: type[BaseModel]) -> BaseModel:
    try:
        datos = json.loads(limpiar_json(texto))
    except json.JSONDecodeError as e:
        raise RespuestaNoValida(f"no es un JSON valido ({e.msg})") from e
    if not isinstance(datos, dict):
        raise RespuestaNoValida("el JSON debe ser un objeto")
    try:
        return modelo.model_validate(datos)
    except ValidationError as e:
        faltan = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise RespuestaNoValida(f"no tiene la forma pedida ({faltan})") from e


def parsear_clasificacion(texto: str) -> _Clasificacion:
    return _parsear(texto, _Clasificacion)


def parsear_extraccion(texto: str) -> _Extraccion:
    return _parsear(texto, _Extraccion)


# --- Normalizacion ---

_DMA = re.compile(r"^(\d{1,2})[/.\- ](\d{1,2})[/.\- ](\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ANIO = re.compile(r"^\d{4}$")
_EVIDENCIA = re.compile(r"^(pagina_([1-9]\d*))(:.+)?$")


def normalizar_fecha(valor) -> str | None:
    """Dia/mes/anio (separador / . - o espacio) -> AAAA-MM-DD; ISO valido se deja igual.
    None si no es una fecha reconocible o no existe (p. ej. 31/02/2024)."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if m := _ISO.match(texto):
        anio, mes, dia = map(int, m.groups())
    elif m := _DMA.match(texto):
        dia, mes, anio = map(int, m.groups())
    else:
        return None
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


def _confianza(valor) -> float:
    if isinstance(valor, bool):
        return 0.0
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    return min(max(numero, 0.0), 1.0) if numero == numero else 0.0  # NaN -> 0


def _evidencia(valor, modalidad: Modalidad, paginas: list[int]) -> str | None:
    """`pagina_<n>[:detalle]` valida; en vision solo `pagina_<n>`. En un lote, `pagina_1..k` relativo
    a las imagenes enviadas se traduce a la pagina real. Invalida -> None."""
    if not isinstance(valor, str) or not (m := _EVIDENCIA.match(valor.strip())):
        return None
    numero = int(m.group(2))
    if paginas and numero not in paginas:
        if numero <= len(paginas):
            numero = paginas[numero - 1]
        else:
            return None
    if modalidad is Modalidad.pdf_digital:
        return f"pagina_{numero}{m.group(3) or ''}"
    return f"pagina_{numero}"


def _tipo_campo(definicion) -> str:
    if isinstance(definicion, Mapping):
        tipo = definicion.get("tipo", "texto")
    else:
        tipo = getattr(definicion, "tipo", "texto")
    return getattr(tipo, "value", tipo)


def postprocesar_extraccion(respuesta: _Extraccion, esquema_campos: Mapping[str, Any], modalidad: Modalidad,
                            paginas: list[int] | None = None) -> ResultadoExtraccion:
    """Aplica las reglas de la spec: solo campos de la ficha, fechas normalizadas (si no se puede, texto
    original con confianza 0), anio de 4 cifras a entero, evidencia valida y confianza en [0, 1]."""
    paginas = paginas or []
    datos, confianzas, evidencias = {}, {}, {}
    for campo, definicion in esquema_campos.items():
        valor = respuesta.datos_extraidos.get(campo)
        if isinstance(valor, str):
            # "" y los textos solo con espacios cuentan como ausentes (null): asi los ven VAL-001 y VAL-004
            # (acordado con PERSONA_3).
            valor = valor.strip() or None
        confianza = _confianza(respuesta.nivel_confianza_por_campo.get(campo))
        if valor is None:
            datos[campo], confianzas[campo] = None, 0.0
            continue
        tipo = _tipo_campo(definicion)
        if tipo == "fecha":
            normalizada = normalizar_fecha(valor)
            if normalizada is None:
                valor, confianza = str(valor), 0.0   # las reglas de fecha lo trataran como fecha invalida
            else:
                valor = normalizada
        elif tipo == "anio":
            if isinstance(valor, int) and not isinstance(valor, bool) and 1000 <= valor <= 9999:
                pass
            elif isinstance(valor, str) and _ANIO.match(valor):
                valor = int(valor)
            else:
                valor, confianza = str(valor), 0.0
        elif not isinstance(valor, str):
            valor = str(valor)
        datos[campo], confianzas[campo] = valor, confianza
        if (evidencia := _evidencia(respuesta.evidencia_por_campo.get(campo), modalidad, paginas)) is not None:
            evidencias[campo] = evidencia
    observaciones = [str(o).strip() for o in respuesta.observaciones_visuales if str(o).strip()]
    return ResultadoExtraccion(datos, confianzas, evidencias, observaciones)


def _pagina_de(evidencia: str) -> int:
    return int(_EVIDENCIA.match(evidencia).group(2))


def combinar_lotes(resultados: list[ResultadoExtraccion]) -> ResultadoExtraccion:
    """Une las extracciones de varios lotes: por campo, el valor no nulo con evidencia valida; ante
    empate, el de la pagina mas baja. Si ningun lote tiene evidencia valida, el primer valor no nulo."""
    if len(resultados) == 1:
        return resultados[0]
    campos = list(dict.fromkeys(c for r in resultados for c in r.datos_extraidos))
    datos, confianzas, evidencias = {}, {}, {}
    for campo in campos:
        con_evidencia = [r for r in resultados
                         if r.datos_extraidos.get(campo) is not None and campo in r.evidencia_por_campo]
        if con_evidencia:
            elegido = min(con_evidencia, key=lambda r: _pagina_de(r.evidencia_por_campo[campo]))
            evidencias[campo] = elegido.evidencia_por_campo[campo]
        else:
            elegido = next((r for r in resultados if r.datos_extraidos.get(campo) is not None), resultados[0])
        datos[campo] = elegido.datos_extraidos.get(campo)
        confianzas[campo] = elegido.nivel_confianza_por_campo.get(campo, 0.0)
    observaciones = list(dict.fromkeys(o for r in resultados for o in r.observaciones_visuales))
    return ResultadoExtraccion(datos, confianzas, evidencias, observaciones)


def tiene_texto_suficiente(paginas: list[Pagina], minimo: int = MIN_CARACTERES_TEXTO_POR_PAGINA) -> bool:
    """True si hay paginas y todas tienen al menos `minimo` caracteres de texto, sin contar espacios."""
    return bool(paginas) and all(len("".join((p.texto or "").split())) >= minimo for p in paginas)


def obligatorios_vacios(resultado: ResultadoExtraccion, esquema_campos: Mapping[str, Any]) -> tuple[int, int]:
    """(campos obligatorios a null, campos obligatorios) de la ficha."""
    obligatorios = [c for c, d in esquema_campos.items()
                    if (d.get("obligatorio") if isinstance(d, Mapping) else getattr(d, "obligatorio", False))]
    return sum(resultado.datos_extraidos.get(c) is None for c in obligatorios), len(obligatorios)


def necesita_reintento_vision(resultado: ResultadoExtraccion, esquema_campos: Mapping[str, Any]) -> bool:
    vacios, total = obligatorios_vacios(resultado, esquema_campos)
    return total > 0 and vacios >= FRACCION_OBLIGATORIOS_VACIOS_REINTENTO * total


def combinar_texto_y_vision(texto: ResultadoExtraccion, vision: ResultadoExtraccion) -> ResultadoExtraccion:
    """Tras el reintento con vision: manda la vision; el texto solo rellena los campos que la vision dejo a null."""
    datos, confianzas = dict(vision.datos_extraidos), dict(vision.nivel_confianza_por_campo)
    evidencias = dict(vision.evidencia_por_campo)
    for campo, valor in texto.datos_extraidos.items():
        if datos.get(campo) is None and valor is not None:
            datos[campo] = valor
            confianzas[campo] = texto.nivel_confianza_por_campo.get(campo, 0.0)
            if campo in texto.evidencia_por_campo:
                evidencias[campo] = texto.evidencia_por_campo[campo]
            else:
                evidencias.pop(campo, None)
    observaciones = list(dict.fromkeys([*vision.observaciones_visuales, *texto.observaciones_visuales]))
    return ResultadoExtraccion(datos, confianzas, evidencias, observaciones)


def postprocesar_clasificacion(respuesta: _Clasificacion, tipos_posibles: Iterable[str]) -> ResultadoClasificacion:
    """Un tipo que no esta entre los posibles pasa a `desconocido` con confianza 0."""
    por_nombre = {t.lower(): t for t in tipos_posibles}
    detectado = respuesta.tipo_documental_detectado.strip().lower()
    razonamiento = str(respuesta.razonamiento or "").strip()
    if detectado in por_nombre:
        return ResultadoClasificacion(por_nombre[detectado], _confianza(respuesta.confianza), razonamiento)
    confianza = _confianza(respuesta.confianza) if detectado == DESCONOCIDO else 0.0
    return ResultadoClasificacion(DESCONOCIDO, confianza, razonamiento)


# --- Imagenes y texto ---

def timeout_vision(n_imagenes: int) -> float:
    """Timeout de una peticion de vision: base + un margen por imagen (4 imagenes -> 660 s)."""
    return TIMEOUT_VISION_BASE_S + TIMEOUT_VISION_POR_PAGINA_S * max(n_imagenes, 1)


def reducir_imagen(png: bytes, ancho_max: int = ANCHO_MAX_IMAGEN) -> bytes:
    """Reduce al ancho maximo manteniendo la proporcion; nunca amplia. Devuelve PNG."""
    with Image.open(io.BytesIO(png)) as imagen:
        if imagen.width <= ancho_max:
            return png
        alto = round(imagen.height * ancho_max / imagen.width)
        salida = io.BytesIO()
        imagen.resize((ancho_max, alto), Image.LANCZOS).save(salida, format="PNG")
        return salida.getvalue()


def lotes_de_paginas(paginas: list[Pagina], tamano: int = MAX_PAGINAS_POR_LLAMADA_VISION) -> list[list[Pagina]]:
    """Paginas con imagen, en orden, en lotes de `tamano`. Sin imagenes: un unico lote vacio."""
    con_imagen = [p for p in paginas if p.imagen_png]
    return [con_imagen[i:i + tamano] for i in range(0, len(con_imagen), tamano)] or [[]]


def recortar_texto(paginas: list[Pagina], max_caracteres: int = MAX_CARACTERES_TEXTO) -> tuple[list[Pagina], bool]:
    """Limita el texto total a `max_caracteres` respetando el orden de las paginas. La pagina donde
    se corta termina en MARCA_RECORTE y las siguientes quedan sin texto. Devuelve (paginas, recortado)."""
    restante, recortado, salida = max_caracteres, False, []
    for pagina in paginas:
        texto = pagina.texto or ""
        if recortado:
            salida.append(replace(pagina, texto=None if pagina.texto is None else ""))
        elif len(texto) > restante:
            salida.append(replace(pagina, texto=f"{texto[:restante]}\n{MARCA_RECORTE}"))
            recortado, restante = True, 0
        else:
            salida.append(pagina)
            restante -= len(texto)
    return salida, recortado
