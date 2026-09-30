"""
Enrutador (Contrato 3): lee y valida `config/modelos.yaml` y devuelve el proveedor de cada tarea.
- Sin nombres de modelos ni claves en el codigo: se leen de las variables de entorno que indica el YAML.
- El modelo de texto o de vision lo elige el proveedor segun la modalidad (spec, seccion 3).
- Barrera de privacidad (ADR-003): un proveedor con `privado: false` solo se usa si
  PERMITIR_PROVEEDORES_NO_PRIVADOS esta activada (desarrollo con fixtures ficticios).
- Principal no disponible -> ErrorEnrutador al arrancar. Respaldo no disponible -> None y aviso.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.interfaces import ProveedorLLM, Tarea
from app.modulos.motor_ia.proveedores.ollama import OllamaProvider

logger = logging.getLogger(__name__)

VARIABLE_PRIVACIDAD = "PERMITIR_PROVEEDORES_NO_PRIVADOS"
TAREAS_OBLIGATORIAS = (Tarea.clasificacion, Tarea.extraccion)  # Tarea.validacion se acepta, pero no se usa
_VALORES_DE_EJEMPLO = ("TU_CLAVE_AQUI", "TU_MODELO_AQUI")
_ACTIVADO = {"1", "true", "si", "yes"}


class ErrorEnrutador(Exception):
    """modelos.yaml invalido o un proveedor principal no disponible. `errores`: una linea por problema.
    Los mensajes nombran variables de entorno, nunca sus valores."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Configuracion de modelos invalida:\n" + "\n".join(f"- {e}" for e in errores))


class _NoDisponible(Exception):
    pass


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DefProveedor(_Estricto):
    tipo: Literal["ollama", "openrouter"]
    base_url_env: str
    modelo_texto_env: str | None = None
    modelo_vision_env: str | None = None
    modelo_env: str | None = None
    api_key_env: str | None = None
    soporta_vision: bool
    privado: bool

    @model_validator(mode="after")
    def _variables_segun_tipo(self) -> DefProveedor:
        necesarias = {"ollama": ("modelo_texto_env", "modelo_vision_env"),
                      "openrouter": ("modelo_env", "api_key_env")}[self.tipo]
        faltan = [c for c in necesarias if not getattr(self, c)]
        if faltan:
            raise ValueError(f"un proveedor de tipo {self.tipo} necesita {', '.join(faltan)}")
        return self

    def variables(self) -> list[str]:
        return [v for v in (self.base_url_env, self.modelo_texto_env, self.modelo_vision_env,
                            self.modelo_env, self.api_key_env) if v]


class DefTarea(_Estricto):
    principal: str
    respaldo: str | None = None
    por_tipo: dict[str, str] = {}

    @field_validator("por_tipo", mode="before")
    @classmethod
    def _vacio(cls, valor):
        return valor or {}


class ConfigModelos(_Estricto):
    proveedores: dict[str, DefProveedor] = Field(..., min_length=1)
    tareas: dict[Tarea, DefTarea]
    criterios: dict[str, str] = {}  # texto documental; no se usa


def _barrera_abierta(entorno: Mapping[str, str]) -> bool:
    return entorno.get(VARIABLE_PRIVACIDAD, "").strip().lower() in _ACTIVADO


def _crear(defn: DefProveedor, entorno: Mapping[str, str]) -> ProveedorLLM:
    problemas = []
    for variable in defn.variables():
        valor = (entorno.get(variable) or "").strip()
        if not valor:
            problemas.append(f"falta la variable de entorno {variable}")
        elif valor.startswith(_VALORES_DE_EJEMPLO):
            problemas.append(f"la variable de entorno {variable} tiene el valor de ejemplo")
    if defn.tipo != "ollama":
        problemas.append(f"el tipo '{defn.tipo}' aun no esta implementado")
    if problemas:
        raise _NoDisponible("; ".join(problemas))
    return OllamaProvider(entorno[defn.base_url_env], entorno[defn.modelo_texto_env], entorno[defn.modelo_vision_env])


class EnrutadorYaml:
    """Implementa `Enrutador` (Contrato 3). Una instancia por proveedor, compartida entre tareas."""

    def __init__(self, config: ConfigModelos, entorno: Mapping[str, str]):
        self._config = config
        barrera_abierta = _barrera_abierta(entorno)
        principales = {n for t in config.tareas.values() for n in (t.principal, *t.por_tipo.values())}
        respaldos = {t.respaldo for t in config.tareas.values() if t.respaldo} - principales

        errores, self._proveedores = [], {}
        for nombre in sorted(principales):
            defn = config.proveedores[nombre]
            if not defn.privado and not barrera_abierta:
                errores.append(f"proveedor principal '{nombre}': no es privado y {VARIABLE_PRIVACIDAD} no esta activada")
                continue
            try:
                self._proveedores[nombre] = _crear(defn, entorno)
            except _NoDisponible as e:
                errores.append(f"proveedor principal '{nombre}' no disponible: {e}")
        if errores:
            raise ErrorEnrutador(errores)

        for nombre in sorted(respaldos):
            defn = config.proveedores[nombre]
            if not defn.privado and not barrera_abierta:
                logger.warning("respaldo '%s' desactivado: no es privado y %s no esta activada", nombre, VARIABLE_PRIVACIDAD)
                continue
            try:
                self._proveedores[nombre] = _crear(defn, entorno)
            except _NoDisponible as e:
                logger.warning("respaldo '%s' no disponible: %s", nombre, e)

    def _tarea(self, tarea: Tarea):
        if tarea not in self._config.tareas:
            raise ErrorEnrutador([f"la tarea '{tarea.value}' no tiene proveedor en modelos.yaml"])
        return self._config.tareas[tarea]

    def nombre_principal(self, tarea: Tarea, tipo_documental: str | None = None) -> str:
        definicion = self._tarea(tarea)
        return definicion.por_tipo.get(tipo_documental, definicion.principal)

    def obtener(self, tarea: Tarea, tipo_documental: str | None = None) -> ProveedorLLM:
        return self._proveedores[self.nombre_principal(tarea, tipo_documental)]

    def respaldo(self, tarea: Tarea, tipo_documental: str | None = None) -> ProveedorLLM | None:
        nombre = self._tarea(tarea).respaldo
        if not nombre or nombre == self.nombre_principal(tarea, tipo_documental):
            return None
        return self._proveedores.get(nombre)


def _formatear(error: ValidationError) -> list[str]:
    lineas = []
    for e in error.errors():
        ruta = ".".join(str(p) for p in e["loc"])
        mensaje = e["msg"].removeprefix("Value error, ")
        lineas.append(f"modelos.yaml: {ruta}: {mensaje}" if ruta else f"modelos.yaml: {mensaje}")
    return lineas


def cargar_config(directorio: Path | str | None = None, tipos_documentales: Iterable[str] | None = None) -> ConfigModelos:
    """Lee y valida `<directorio>/modelos.yaml` (por defecto, CONFIG_DIR). Todos los errores a la vez."""
    ruta = Path(directorio or configuracion.directorio_config()) / "modelos.yaml"
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ErrorEnrutador([f"no existe {ruta}"]) from e
    except yaml.YAMLError as e:
        raise ErrorEnrutador([f"modelos.yaml: YAML mal formado: {e}"]) from e
    try:
        config = ConfigModelos.model_validate(datos)
    except ValidationError as e:
        raise ErrorEnrutador(_formatear(e)) from e

    tipos = set(tipos_documentales) if tipos_documentales is not None else {f.nombre for f in configuracion.listar()}
    errores = [f"modelos.yaml: falta la tarea '{t.value}'" for t in TAREAS_OBLIGATORIAS if t not in config.tareas]
    for tarea, definicion in config.tareas.items():
        referencias = [("principal", definicion.principal), ("respaldo", definicion.respaldo)]
        referencias += [(f"por_tipo.{tipo}", nombre) for tipo, nombre in definicion.por_tipo.items()]
        for campo, nombre in referencias:
            if nombre is not None and nombre not in config.proveedores:
                errores.append(f"modelos.yaml: tareas.{tarea.value}.{campo}: proveedor inexistente '{nombre}'")
        for tipo in definicion.por_tipo:
            if tipo not in tipos:
                errores.append(f"modelos.yaml: tareas.{tarea.value}.por_tipo: tipo documental inexistente '{tipo}'")
    if errores:
        raise ErrorEnrutador(errores)
    return config


def crear_enrutador(directorio: Path | str | None = None, entorno: Mapping[str, str] | None = None,
                    tipos_documentales: Iterable[str] | None = None) -> EnrutadorYaml:
    """Carga modelos.yaml y crea los proveedores. `entorno` por defecto: os.environ."""
    return EnrutadorYaml(cargar_config(directorio, tipos_documentales), os.environ if entorno is None else entorno)
