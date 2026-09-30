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


def _campo(definicion: dict) -> dict:
    campo = {"tipo": definicion.get("tipo"), "obligatorio": bool(definicion.get("obligatorio", False))}
    if definicion.get("patron"):
        campo["patron"] = definicion["patron"]
    return campo


def listar_fichas() -> list[dict]:
    """Fichas con la forma `TipoDocumental` de endpoints.md, ordenadas por nombre.

    TODO: sustituir por configuracion.servicio.listar() de PERSONA_2 cuando su modulo este en main.
    """
    return [
        {
            "nombre": ficha.get("nombre", nombre),
            "nombre_visible": ficha.get("nombre_visible"),
            "categoria": ficha.get("categoria"),
            "descripcion": ficha.get("descripcion"),
            "formatos_permitidos": [str(f).lower().lstrip(".") for f in ficha.get("formatos_permitidos", [])],
            "campos": {c: _campo(d or {}) for c, d in (ficha.get("campos") or {}).items()},
            "confianza_minima_clasificacion": ficha.get("confianza_minima_clasificacion"),
            "confianza_minima_campo": ficha.get("confianza_minima_campo"),
            "reglas": ficha.get("reglas") or [],
            "comparaciones": ficha.get("comparaciones") or {},
        }
        for nombre, ficha in sorted(_fichas().items())
    ]
