"""Tests de "hoy" en la zona horaria del negocio (orquestador/reloj.py; spec, seccion 11)."""
from datetime import date, datetime, timezone

import pytest

from app.modulos.orquestador.reloj import ZONA_HORARIA_POR_DEFECTO, hoy

# 2026-10-02 05:30 UTC = 2026-10-01 23:30 en Ciudad de Mexico (UTC-6, sin horario de verano)
CERCA_DE_MEDIANOCHE = datetime(2026, 10, 2, 5, 30, tzinfo=timezone.utc)


def test_cerca_de_medianoche_usa_la_fecha_de_la_zona_y_no_la_utc(monkeypatch):
    monkeypatch.delenv("ZONA_HORARIA", raising=False)
    assert ZONA_HORARIA_POR_DEFECTO == "America/Mexico_City"
    assert CERCA_DE_MEDIANOCHE.date() == date(2026, 10, 2)          # en UTC ya es el dia 2
    assert hoy(CERCA_DE_MEDIANOCHE) == date(2026, 10, 1)            # en la zona del negocio, todavia el 1


def test_lee_la_zona_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("ZONA_HORARIA", "Europe/Madrid")              # UTC+2 en octubre
    assert hoy(CERCA_DE_MEDIANOCHE) == date(2026, 10, 2)
    monkeypatch.setenv("ZONA_HORARIA", "")                           # vacia -> por defecto
    assert hoy(CERCA_DE_MEDIANOCHE) == date(2026, 10, 1)


def test_zona_desconocida_es_un_error(monkeypatch):
    monkeypatch.setenv("ZONA_HORARIA", "Marte/Olympus")
    with pytest.raises(ValueError, match="ZONA_HORARIA"):
        hoy(CERCA_DE_MEDIANOCHE)


def test_ahora_sin_zona_es_un_error():
    with pytest.raises(ValueError):
        hoy(datetime(2026, 10, 2, 5, 30))


def test_sin_ahora_usa_el_reloj_en_la_zona(monkeypatch):
    monkeypatch.delenv("ZONA_HORARIA", raising=False)
    from zoneinfo import ZoneInfo
    assert hoy() == datetime.now(ZoneInfo("America/Mexico_City")).date()
