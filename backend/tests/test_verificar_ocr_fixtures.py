"""Tests de scripts/verificar_ocr_fixtures.py (PERSONA_3): parser de INDICE.md y comparacion.
No necesitan Tesseract: el OCR se sustituye por texto fijo. Solo datos ficticios."""
import importlib.util
from datetime import date
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ_REPO / "scripts"
if not (SCRIPTS / "verificar_ocr_fixtures.py").is_file() or not (RAIZ_REPO / "config" / "tipos").is_dir():
    pytest.skip("Tests del verificador OCR omitidos: faltan scripts/ o config/tipos "
                "(normal dentro del contenedor del backend)", allow_module_level=True)


def _cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


vo = _cargar("verificar_ocr_fixtures")
gf = _cargar("generar_fixtures")


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    salida = tmp_path_factory.mktemp("fixtures")
    gf.generar(date(2026, 9, 30), salida)
    return vo.parsear_indice(salida / "INDICE.md")


def test_parser_lee_todos_los_archivos_del_indice(indice):
    assert len(indice) == 42  # 30 normales + 12 de dificultad
    assert {d["caso"] for d in indice.values()} == {"sano", "vencido", "domicilio_distinto", "duplicado"}
    assert indice["pasaporte_vencido_foto.jpg"]["nivel"] == "normal"
    assert indice["pasaporte_vencido_foto.jpg"]["modalidad"] == "foto"


def test_parser_lee_los_fixtures_de_dificultad_con_los_valores_del_caso_sano(indice):
    dificultad = {a: d for a, d in indice.items() if d["nivel"] != "normal"}
    assert len(dificultad) == 12
    assert {d["nivel"] for d in dificultad.values()} == {"dificil", "extremo"}
    doc = indice["pasaporte_sano_foto_extremo.jpg"]
    assert (doc["caso"], doc["tipo"], doc["modalidad"], doc["nivel"]) == ("sano", "pasaporte", "foto", "extremo")
    assert doc["campos"] == indice["pasaporte_sano_digital.pdf"]["campos"]
    assert doc["mrz"] == indice["pasaporte_sano_digital.pdf"]["mrz"] and len(doc["mrz"]) == 2
    assert indice["credencial_elector_sano_escaneado_dificil.pdf"]["modalidad"] == "escaneado"


def test_nivel_de_separa_el_control_digital():
    assert vo.nivel_de({"modalidad": "digital", "nivel": "normal"}) == "control"
    assert vo.nivel_de({"modalidad": "foto", "nivel": "extremo"}) == "extremo"


def test_resumen_por_nivel_agrupa_y_ordena():
    resultados = [("extremo", "foto", "pasaporte", 1, 7), ("normal", "foto", "pasaporte", 7, 7),
                  ("dificil", "escaneado", "pasaporte", 4, 7), ("dificil", "foto", "pasaporte", 5, 7),
                  ("control", "digital", "pasaporte", 7, 7)]
    tabla = vo.resumen_por_nivel(resultados)
    assert tabla[:6] == ["| Nivel | Ficheros | Campos encontrados |", "|---|---|---|",
                         "| control | 1 | 7/7 (100%) |", "| normal | 1 | 7/7 (100%) |",
                         "| dificil | 2 | 9/14 (64%) |", "| extremo | 1 | 1/7 (14%) |"]
    detalle = tabla[tabla.index("| Nivel | Modalidad | Tipo | Campos encontrados |") + 2:]
    assert detalle[:3] == ["| control | digital | pasaporte | 7/7 (100%) |", "| normal | foto | pasaporte | 7/7 (100%) |",
                           "| dificil | escaneado | pasaporte | 4/7 (57%) |"]


def test_parser_convierte_fechas_al_formato_del_documento(indice):
    doc = indice["pasaporte_vencido_escaneado.pdf"]
    assert doc["tipo"] == "pasaporte"
    assert doc["campos"]["fecha_vencimiento"] == "31/08/2026"
    assert doc["campos"]["sexo"] == "M"
    assert doc["mrz"][0].startswith("P<UTODEMO<PRUEBAS<<LUIS")
    assert len(doc["mrz"]) == 2


def test_las_tres_modalidades_comparten_valores(indice):
    assert (indice["comprobante_domicilio_domicilio_distinto_foto.jpg"]["campos"]
            == indice["comprobante_domicilio_domicilio_distinto_digital.pdf"]["campos"])
    assert indice["credencial_elector_sano_foto.jpg"]["campos"]["vigencia"] == "2029"


def test_normalizar_mayusculas_acentos_y_espacios():
    assert vo.normalizar("  Calle  Ficticía\n123 ") == "CALLE FICTICIA 123"


def test_contiene_palabra_exige_palabra_completa():
    assert vo.contiene_palabra("M", "SEXO M")
    assert not vo.contiene_palabra("M", "LUIS DEMO PRUEBAS")
    assert not vo.contiene_palabra("2029", "120290")


def test_comparar_detecta_campos_y_mrz(indice):
    doc = indice["pasaporte_vencido_escaneado.pdf"]
    completo = "\n".join([*doc["campos"].values(), " ".join(doc["mrz"][0]), doc["mrz"][1]])
    fallos, mrz_ok = vo.comparar(doc, completo)
    assert fallos == [] and mrz_ok == 2  # la MRZ con espacios intercalados tambien cuenta

    # Sin la MRZ espaciada: en "D E M O" hay una M suelta que contaria como el sexo
    sin_sexo = "\n".join([v for c, v in doc["campos"].items() if c != "sexo"] + doc["mrz"])
    fallos, _ = vo.comparar(doc, sin_sexo)
    assert len(fallos) == 1 and fallos[0].startswith("sexo (M ~")
