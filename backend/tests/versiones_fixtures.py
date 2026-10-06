"""Versiones de PyMuPDF y Pillow con las que se registraron los SHA-256 de los fixtures.

Los bytes que generan scripts/generar_fixtures.py y scripts/generar_datos_mock.py dependen de esas
versiones, que requirements.txt fija con == (H13). Con otras versiones (p. ej. un venv antiguo), los tests que comparan hashes o bytes con
los registrados (sha256_fixtures_existentes.txt, frontend/public/mock-originales y los JSON de los
mocks) se omiten con un mensaje, en vez de fallar. El determinismo dentro de una misma instalacion
(generar dos veces y comparar) se sigue comprobando siempre.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

RUTA_REFERENCIA = Path(__file__).with_name("sha256_fixtures_existentes.txt")


def leer_referencia(ruta: Path = RUTA_REFERENCIA) -> tuple[dict[str, str], dict[str, str]]:
    """({paquete: version}, {archivo: sha256}). Lineas `paquete==version` y `sha256  archivo`."""
    versiones, hashes = {}, {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "==" in linea:
            paquete, valor = linea.split("==")
            versiones[paquete.strip()] = valor.strip()
        else:
            sha, archivo = linea.split()
            hashes[archivo] = sha
    return versiones, hashes


def versiones_instaladas(paquetes) -> dict[str, str]:
    instaladas = {}
    for paquete in paquetes:
        try:
            instaladas[paquete] = version(paquete)
        except PackageNotFoundError:
            instaladas[paquete] = "no instalado"
    return instaladas


def motivo_versiones_distintas(ruta: Path = RUTA_REFERENCIA) -> str | None:
    """None si las versiones instaladas son las registradas; si no, el mensaje para pytest.skip."""
    esperadas, _ = leer_referencia(ruta)
    instaladas = versiones_instaladas(esperadas)
    if instaladas == esperadas:
        return None
    texto = lambda v: ", ".join(f"{p} {n}" for p, n in v.items())
    return (f"Hashes registrados con {texto(esperadas)}; instaladas: {texto(instaladas)}. Los bytes generados "
            f"dependen de esas versiones. Instala las registradas o, si el cambio es deliberado, regenera los "
            f"mocks (scripts/generar_datos_mock.py) y {ruta.name}")


def omitir_si_cambian_las_versiones() -> None:
    if motivo := motivo_versiones_distintas():
        pytest.skip(motivo)
