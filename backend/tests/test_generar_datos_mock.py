"""Tests de scripts/generar_datos_mock.py (PERSONA_3): reproduce exactamente los datos de los mocks
del repo (JSON y originales). Solo datos ficticios."""
import importlib.util
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REPO / "scripts" / "generar_datos_mock.py"
DATOS = RAIZ_REPO / "frontend" / "src" / "mocks" / "datos"
ORIGINALES = RAIZ_REPO / "frontend" / "public" / "mock-originales"
if not SCRIPT.is_file() or not DATOS.is_dir() or not (RAIZ_REPO / "config" / "tipos").is_dir():
    pytest.skip("Tests del generador de datos de los mocks omitidos: faltan scripts/, frontend/ o config/ "
                "(normal dentro del contenedor del backend)", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("generar_datos_mock", SCRIPT)
gdm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gdm)


@pytest.fixture(scope="module")
def regenerado(tmp_path_factory):
    salida = tmp_path_factory.mktemp("mocks")
    gdm.generar(salida / "datos", salida / "originales")
    return salida


@pytest.mark.parametrize("nombre", ["folios", "procesos", "tipos_documentales", "auditoria"])
def test_reproduce_los_json_del_repo(regenerado, nombre):
    assert (regenerado / "datos" / f"{nombre}.json").read_bytes() == (DATOS / f"{nombre}.json").read_bytes(), (
        f"{nombre}.json difiere: regeneralo con `python scripts/generar_datos_mock.py` y revisa el diff")


def test_reproduce_los_originales_del_repo(regenerado):
    nuevos = {p.name: p.read_bytes() for p in (regenerado / "originales").iterdir()}
    actuales = {p.name: p.read_bytes() for p in ORIGINALES.iterdir()}
    assert nuevos.keys() == actuales.keys()
    assert all(nuevos[n] == actuales[n] for n in nuevos)


def test_usa_la_fecha_fija_de_los_mocks():
    assert gdm.HOY_MOCKS.isoformat() == "2026-09-30"
