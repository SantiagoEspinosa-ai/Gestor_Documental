"""Carga de `config/procesos.yaml` en la tabla `procesos` al arrancar (upsert).

`leer_procesos` es pura (solo lee y valida ficheros); `sincronizar_procesos` escribe en BD.
"""
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.modelos import Folio, Proceso

log = logging.getLogger(__name__)

FICHERO = "procesos.yaml"


class ErrorProcesos(Exception):
    """Todos los problemas de procesos.yaml juntos, una linea por problema."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("\n".join(errores))


class ProcesoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str
    prefijo_folio: str = Field(pattern=r"^[A-Z]{2,5}$")
    tipos_requeridos: list[str] = Field(min_length=1)
    tipos_opcionales: list[str] = []
    permitir_antecedentes: bool
    caducidad_antecedentes_dias: int = Field(gt=0)
    webhook_url: str | None = None
    modelos: str = "default"

    @field_validator("webhook_url", mode="before")
    @classmethod
    def _vacio_es_none(cls, valor):
        return valor or None


def leer_procesos(config_dir: Path) -> list[ProcesoConfig]:
    """Lee y valida procesos.yaml. Lanza ErrorProcesos con todos los errores a la vez."""
    ruta = config_dir / FICHERO
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ErrorProcesos([f"{FICHERO}: no se puede leer: {e}"]) from e
    if not isinstance(datos, dict) or not isinstance(datos.get("procesos"), dict):
        raise ErrorProcesos([f"{FICHERO}: falta el diccionario 'procesos'"])

    # TODO: cambiar por configuracion.listar() cuando el modulo de PERSONA_2 este en main
    tipos_existentes = {p.stem for p in (config_dir / "tipos").glob("*.yaml")}

    errores: list[str] = []
    procesos: list[ProcesoConfig] = []
    for nombre, campos in datos["procesos"].items():
        campos = campos if isinstance(campos, dict) else {}
        try:
            procesos.append(ProcesoConfig(nombre=nombre, **campos))
        except ValidationError as e:
            for err in e.errors():
                campo = ".".join(str(parte) for parte in err["loc"])
                errores.append(f"{FICHERO}: {nombre}.{campo}: {err['msg']}")

        # Los tipos se revisan sobre el YAML crudo para informar tambien si el proceso es invalido
        listas = {c: campos.get(c) or [] for c in ("tipos_requeridos", "tipos_opcionales")}
        listas = {c: v for c, v in listas.items() if isinstance(v, list)}
        for tipo in sorted(set(listas.get("tipos_requeridos", [])) & set(listas.get("tipos_opcionales", []))):
            errores.append(f"{FICHERO}: {nombre}.tipos_opcionales: '{tipo}' ya esta en tipos_requeridos")
        for campo, tipos in listas.items():
            for tipo in tipos:
                if tipo not in tipos_existentes:
                    errores.append(f"{FICHERO}: {nombre}.{campo}: el tipo '{tipo}' no existe en tipos/")

    prefijos: dict[str, str] = {}
    for p in procesos:
        if p.prefijo_folio in prefijos:
            errores.append(f"{FICHERO}: {p.nombre}.prefijo_folio: '{p.prefijo_folio}' ya lo usa "
                           f"{prefijos[p.prefijo_folio]}")
        prefijos.setdefault(p.prefijo_folio, p.nombre)

    if errores:
        raise ErrorProcesos(errores)
    return procesos


def sincronizar_procesos(sesion: Session, procesos: list[ProcesoConfig]) -> None:
    """Upsert de los procesos en BD. No borra los que ya no estan en el YAML (tienen folios)."""
    # Primero se comprueba todo; si algo falla no se actualiza nada
    errores = []
    for p in procesos:
        fila = sesion.get(Proceso, p.nombre)
        if fila and fila.prefijo_folio != p.prefijo_folio and sesion.scalar(
                select(Folio.folio).where(Folio.proceso == p.nombre).limit(1)):
            # Romperia la secuencia de folios y las claves de S3 (ADR-006 bloque 4)
            errores.append(f"{FICHERO}: {p.nombre}.prefijo_folio: no se puede cambiar de "
                           f"'{fila.prefijo_folio}' a '{p.prefijo_folio}' porque ya hay folios")
    if errores:
        raise ErrorProcesos(errores)

    for p in procesos:
        fila = sesion.get(Proceso, p.nombre) or Proceso(nombre=p.nombre)
        for campo, valor in p.model_dump(exclude={"nombre"}).items():
            setattr(fila, campo, valor)
        sesion.add(fila)

    en_yaml = {p.nombre for p in procesos}
    for nombre in sesion.scalars(select(Proceso.nombre)):
        if nombre not in en_yaml:
            log.warning("El proceso '%s' esta en BD pero ya no en %s; no se borra", nombre, FICHERO)
    sesion.commit()


def listar_procesos(sesion: Session) -> list[Proceso]:
    """Procesos de la tabla, ordenados por nombre (GET /procesos)."""
    return list(sesion.scalars(select(Proceso).order_by(Proceso.nombre)))
