"""
Carga y validacion de las fichas YAML de tipos documentales (`config/tipos/*.yaml`).
Uso interno del modulo: los demas modulos importan `configuracion.servicio`.
"""
from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.schemas.resultado import Severidad

# backend/app/modulos/configuracion/cargador.py -> raiz del repo
_RAIZ_REPO = Path(__file__).resolve().parents[4]

# Valor reservado de tipo_documental_detectado (ADR-009): ninguna ficha puede llamarse asi.
NOMBRE_RESERVADO = "desconocido"
# Los marcadores de clasificacion (ADR-007) se buscan linea a linea en el texto normalizado
# (mayusculas, sin acentos): ^ y $ son principio y fin de linea.
FLAGS_MARCADORES = re.MULTILINE


class ErrorConfiguracion(Exception):
    """Una o varias fichas YAML son invalidas. `errores` trae una linea por problema."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Configuracion de tipos invalida:\n" + "\n".join(f"- {e}" for e in errores))


class TipoNoEncontrado(KeyError):
    """Se pidio un tipo documental que no esta en `config/tipos`."""


class TipoCampo(str, Enum):
    texto = "texto"
    fecha = "fecha"
    anio = "anio"


class TipoRegla(str, Enum):
    patron = "patron"
    fecha_posterior_a_hoy = "fecha_posterior_a_hoy"
    fecha_posterior_a_hoy_mas_dias = "fecha_posterior_a_hoy_mas_dias"
    fecha_no_anterior_a_hoy_menos_dias = "fecha_no_anterior_a_hoy_menos_dias"
    anio_mayor_o_igual_actual = "anio_mayor_o_igual_actual"
    obligatorio = "obligatorio"
    confianza_minima = "confianza_minima"


_REGLAS_CON_DIAS = {TipoRegla.fecha_posterior_a_hoy_mas_dias, TipoRegla.fecha_no_anterior_a_hoy_menos_dias}


class _Estricto(BaseModel):
    # Una clave desconocida (p. ej. una errata) es un error, no se ignora.
    model_config = ConfigDict(extra="forbid")


class Campo(_Estricto):
    tipo: TipoCampo
    obligatorio: bool = False
    patron: str | None = None

    @field_validator("patron")
    @classmethod
    def _patron_compila(cls, valor: str | None) -> str | None:
        if valor is not None:
            try:
                re.compile(valor)
            except re.error as e:
                raise ValueError(f"expresion regular invalida: {e}") from e
        return valor


class Regla(_Estricto):
    id: str
    tipo: TipoRegla
    campo: str
    severidad: Severidad
    mensaje: str
    dias: int | None = Field(None, gt=0)

    @model_validator(mode="after")
    def _dias_si_hacen_falta(self) -> Regla:
        if self.tipo in _REGLAS_CON_DIAS and self.dias is None:
            raise ValueError(f"la regla '{self.id}' de tipo {self.tipo.value} necesita 'dias'")
        return self


class TipoDocumental(_Estricto):
    nombre: str
    nombre_visible: str
    categoria: str
    descripcion: str
    caracteristicas_esperadas: list[str]
    formatos_permitidos: list[str] = Field(..., min_length=1)
    ejemplos_referencia: list[str] = []
    campos: dict[str, Campo] = Field(..., min_length=1)
    confianza_minima_clasificacion: float = Field(..., ge=0, le=1)
    confianza_minima_campo: float = Field(..., ge=0, le=1)
    reglas: list[Regla] = []
    comparaciones: dict[str, list[str]] = {}
    # ADR-007: expresiones regulares verificables en el texto; confianza de clasificacion = proporcion encontrada
    marcadores_clasificacion: list[str] = []

    @field_validator("nombre")
    @classmethod
    def _nombre_no_reservado(cls, nombre: str) -> str:
        if nombre == NOMBRE_RESERVADO:
            raise ValueError(f"el nombre '{NOMBRE_RESERVADO}' esta reservado para tipo_documental_detectado (ADR-009)")
        return nombre

    @field_validator("marcadores_clasificacion")
    @classmethod
    def _marcadores_compilan(cls, marcadores: list[str]) -> list[str]:
        for i, marcador in enumerate(marcadores):
            try:
                re.compile(marcador, FLAGS_MARCADORES)
            except re.error as e:
                raise ValueError(f"marcador {i} ('{marcador}'): expresion regular invalida: {e}") from e
        repetidos = sorted({m for m in marcadores if marcadores.count(m) > 1})
        if repetidos:
            raise ValueError(f"marcadores repetidos: {', '.join(repetidos)}")
        return marcadores

    @field_validator("formatos_permitidos")
    @classmethod
    def _normalizar_formatos(cls, formatos: list[str]) -> list[str]:
        return [f.lower().lstrip(".") for f in formatos]

    @model_validator(mode="after")
    def _reglas_coherentes(self) -> TipoDocumental:
        ids = [r.id for r in self.reglas]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            raise ValueError(f"ids de regla repetidos: {', '.join(repetidos)}")
        for regla in self.reglas:
            if regla.campo not in self.campos:
                raise ValueError(f"la regla '{regla.id}' apunta al campo inexistente '{regla.campo}'")
            if regla.tipo is TipoRegla.patron and self.campos[regla.campo].patron is None:
                raise ValueError(f"la regla '{regla.id}' es de tipo patron pero el campo '{regla.campo}' no tiene patron")
        return self


def directorio_config() -> Path:
    """`CONFIG_DIR` si esta definida (en Docker, /config); si no, `config/` en la raiz del repo."""
    return Path(os.environ.get("CONFIG_DIR") or _RAIZ_REPO / "config")


def _formatear(fichero: str, error: ValidationError) -> list[str]:
    lineas = []
    for e in error.errors():
        ruta = ".".join(str(parte) for parte in e["loc"])
        mensaje = e["msg"].removeprefix("Value error, ")
        lineas.append(f"{fichero}: {ruta}: {mensaje}" if ruta else f"{fichero}: {mensaje}")
    return lineas


def cargar_tipos(directorio: Path | str | None = None) -> dict[str, TipoDocumental]:
    """Lee y valida todas las fichas de `<directorio>/tipos/*.yaml`.

    Recoge todos los errores de todos los ficheros y lanza un unico `ErrorConfiguracion`.
    """
    carpeta = Path(directorio or directorio_config()) / "tipos"
    ficheros = sorted(carpeta.glob("*.yaml"))
    if not ficheros:
        raise ErrorConfiguracion([f"no hay fichas YAML en {carpeta}"])

    tipos: dict[str, TipoDocumental] = {}
    errores: list[str] = []
    for ruta in ficheros:
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errores.append(f"{ruta.name}: YAML mal formado: {e}")
            continue
        if not isinstance(datos, dict):
            errores.append(f"{ruta.name}: la ficha debe ser un diccionario YAML")
            continue
        try:
            ficha = TipoDocumental.model_validate(datos)
        except ValidationError as e:
            errores.extend(_formatear(ruta.name, e))
            continue
        if ficha.nombre != ruta.stem:
            errores.append(f"{ruta.name}: nombre '{ficha.nombre}' no coincide con el nombre del fichero")
            continue
        tipos[ficha.nombre] = ficha

    # Comparaciones entre fichas: solo cuando todas las validas estan cargadas.
    for nombre, ficha in tipos.items():
        for otro, campos in ficha.comparaciones.items():
            if otro not in tipos:
                errores.append(f"{nombre}.yaml: comparaciones.{otro}: tipo documental inexistente")
                continue
            for campo in campos:
                if campo not in ficha.campos or campo not in tipos[otro].campos:
                    errores.append(f"{nombre}.yaml: comparaciones.{otro}: el campo '{campo}' no existe en ambas fichas")

    if errores:
        raise ErrorConfiguracion(errores)
    return tipos
