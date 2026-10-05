"""
"Hoy" de las reglas de fecha (validacion.evaluar_reglas), en la zona horaria del negocio, la misma que usa la
plataforma para los folios. Se lee del entorno (`ZONA_HORARIA`) y no de `core.config` (ADR-005: los modulos no
importan el core de la plataforma). Spec, seccion 11.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_HORARIA_POR_DEFECTO = "America/Mexico_City"  # igual que core.config.Settings.zona_horaria


def zona_horaria() -> ZoneInfo:
    """`ZONA_HORARIA` del entorno o America/Mexico_City. Una zona desconocida es un error de configuracion."""
    nombre = os.environ.get("ZONA_HORARIA") or ZONA_HORARIA_POR_DEFECTO
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"ZONA_HORARIA: zona horaria desconocida: {nombre}") from None


def hoy(ahora: datetime | None = None) -> date:
    """Fecha de hoy en la zona del negocio: `datetime.now(ZoneInfo(zona)).date()`. `ahora` (con zona) es para
    los tests."""
    zona = zona_horaria()
    if ahora is None:
        return datetime.now(zona).date()
    if ahora.tzinfo is None:
        raise ValueError("ahora debe llevar zona horaria")
    return ahora.astimezone(zona).date()


__all__ = ["ZONA_HORARIA_POR_DEFECTO", "hoy", "zona_horaria"]
