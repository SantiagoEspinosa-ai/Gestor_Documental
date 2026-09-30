"""Lectura minima de las fichas de `config/tipos/*.yaml` que necesita la ingesta.

TODO: sustituir por configuracion.servicio.obtener()/listar() de PERSONA_2 cuando su modulo este en main.
"""
from pathlib import Path

import yaml

from app.core.config import get_settings


def _fichas() -> dict[str, dict]:
    carpeta: Path = get_settings().config_dir / "tipos"
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) or {} for p in carpeta.glob("*.yaml")}


def existe_tipo(tipo: str) -> bool:
    return tipo in _fichas()


def formatos_permitidos(tipo: str | None) -> set[str]:
    """Extensiones (minusculas, sin punto) del tipo dado, o de todos los tipos si es None."""
    fichas = _fichas()
    elegidas = [fichas[tipo]] if tipo else fichas.values()
    return {str(f).lower().lstrip(".") for ficha in elegidas for f in ficha.get("formatos_permitidos", [])}
