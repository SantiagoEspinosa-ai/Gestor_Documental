"""
API publica del modulo configuracion: lo unico que importan los demas modulos (ADR-005).
"""
from __future__ import annotations

from pathlib import Path

from app.modulos.configuracion.cargador import (
    FLAGS_MARCADORES,
    NOMBRE_RESERVADO,
    Campo,
    ErrorConfiguracion,
    Regla,
    TipoCampo,
    TipoDocumental,
    TipoNoEncontrado,
    TipoRegla,
    cargar_tipos,
    directorio_config,
)

__all__ = [
    "FLAGS_MARCADORES", "NOMBRE_RESERVADO", "Campo", "ErrorConfiguracion", "Regla", "TipoCampo", "TipoDocumental", "TipoNoEncontrado", "TipoRegla",
    "cargar", "directorio_config", "listar", "obtener",
]

_tipos: dict[str, TipoDocumental] | None = None


def cargar(directorio: Path | str | None = None) -> dict[str, TipoDocumental]:
    """Carga (o recarga) y valida las fichas. Llamar al arrancar: si una es invalida, lanza ErrorConfiguracion."""
    global _tipos
    _tipos = cargar_tipos(directorio)
    return _tipos


def _cargados() -> dict[str, TipoDocumental]:
    return _tipos if _tipos is not None else cargar()


def obtener(nombre: str) -> TipoDocumental:
    try:
        return _cargados()[nombre]
    except KeyError:
        raise TipoNoEncontrado(nombre) from None


def listar() -> list[TipoDocumental]:
    return list(_cargados().values())
