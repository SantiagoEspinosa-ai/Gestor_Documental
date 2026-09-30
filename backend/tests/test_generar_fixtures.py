"""Tests de scripts/generar_fixtures.py (PERSONA_3). Solo datos ficticios."""
import copy
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_SCRIPT = RAIZ_REPO / "scripts" / "generar_fixtures.py"
DIR_TIPOS = RAIZ_REPO / "config" / "tipos"
# El contenedor del backend solo monta ./backend, ./config en /config y ./prompts: sin el script
# (o sin config/tipos junto a el) estos tests no aplican. Se ejecutan desde la raiz del repo.
if not RUTA_SCRIPT.is_file() or not DIR_TIPOS.is_dir():
    pytest.skip(f"Tests del generador de fixtures omitidos: no se encuentra {RUTA_SCRIPT} o {DIR_TIPOS} "
                "(normal dentro del contenedor del backend; ejecutalos desde el repo completo)",
                allow_module_level=True)
_spec = importlib.util.spec_from_file_location("generar_fixtures", RUTA_SCRIPT)
gf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gf)

HOY = date(2026, 9, 30)


@pytest.fixture(scope="module")
def fichas():
    return gf.cargar_fichas()


def test_digito_control_con_el_ejemplo_de_la_norma_oaci():
    # Especimen publico de la norma OACI 9303 (Utopia)
    assert gf.digito_control("L898902C3") == "6"
    assert gf.digito_control("740812") == "2"
    assert gf.digito_control("120415") == "9"
    assert gf.digito_control("<<<<<<<<<<<<<<") == "0"


def test_mrz_de_cada_persona_es_valida_y_coherente_con_la_curp():
    for persona in gf.PERSONAS_FICTICIAS:
        valores = gf.valores_documento("pasaporte", persona, "sano", HOY)
        linea1, linea2 = gf.generar_mrz(valores)
        gf.validar_mrz(linea1, linea2, valores)
        nacimiento, sexo = gf.datos_de_curp(persona["curp"])
        assert linea1.startswith("P<UTO") and len(linea1) == len(linea2) == 44
        assert linea2[13:19] == nacimiento.strftime("%y%m%d") and linea2[20] == sexo


def test_mrz_con_digito_alterado_falla():
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    linea1, linea2 = gf.generar_mrz(valores)
    alterada = linea2[:9] + str((int(linea2[9]) + 1) % 10) + linea2[10:]
    with pytest.raises(gf.ErrorFixture, match="control"):
        gf.validar_mrz(linea1, alterada, valores)


def test_datos_de_curp():
    assert gf.datos_de_curp("AEPA900101MDFXXX01") == (date(1990, 1, 1), "F")
    assert gf.datos_de_curp("DEPL850615HDFXXX02") == (date(1985, 6, 15), "M")
    assert gf.datos_de_curp("ZZZZ050315HDFXXXA1") == (date(2005, 3, 15), "M")  # letra -> 2000+


def test_personas_ficticias_son_coherentes(fichas):
    for persona in gf.PERSONAS_FICTICIAS:
        gf.validar_persona(persona, fichas)


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("sexo", "M", "sexo"),
    ("fecha_nacimiento", "1990-01-02", "fecha_nacimiento"),
    ("clave_elector", "EJPRAN90010109M101", "clave_elector"),  # estado 09 en vez de 99
    ("curp", "AEPA900101XDFXXX01", "patron"),
])
def test_persona_incoherente_con_la_curp_falla(fichas, campo, valor, mensaje):
    persona = copy.deepcopy(gf.PERSONAS_FICTICIAS[0])
    persona[campo] = valor
    with pytest.raises(gf.ErrorFixture, match=mensaje):
        gf.validar_persona(persona, fichas)


def test_campo_nuevo_en_el_yaml_sin_valor_falla(fichas):
    ficha = copy.deepcopy(fichas["pasaporte"])
    ficha["campos"]["lugar_nacimiento"] = {"tipo": "texto", "obligatorio": False}
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    with pytest.raises(gf.ErrorFixture, match="lugar_nacimiento"):
        gf.validar_valores("pasaporte", valores, ficha)


def test_valor_que_no_cumple_el_patron_falla(fichas):
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    valores["numero_pasaporte"] = "ZX-01"
    with pytest.raises(gf.ErrorFixture, match="patron"):
        gf.validar_valores("pasaporte", valores, fichas["pasaporte"])


def test_fechas_relativas_a_hoy():
    ana, luis = gf.PERSONAS_FICTICIAS
    assert gf.valores_documento("pasaporte", ana, "sano", HOY)["fecha_vencimiento"] == date(2031, 9, 30)
    assert gf.valores_documento("pasaporte", luis, "vencido", HOY)["fecha_vencimiento"] == HOY - timedelta(days=30)
    assert gf.valores_documento("pasaporte", ana, "sano", HOY)["fecha_expedicion"] == date(2021, 9, 30)
    assert gf.valores_documento("credencial_elector", ana, "sano", HOY)["vigencia"] == 2029
    assert gf.valores_documento("comprobante_domicilio", ana, "sano", HOY)["fecha_emision"] == date(2026, 9, 15)


def test_sumar_anios_desde_29_de_febrero():
    assert gf.sumar_anios(date(2028, 2, 29), 5) == date(2033, 2, 28)
    assert gf.sumar_anios(date(2028, 2, 29), 4) == date(2032, 2, 29)


def test_generacion_completa_y_determinista(tmp_path):
    primera = gf.generar(HOY, tmp_path / "a")
    segunda = gf.generar(HOY, tmp_path / "b")
    esperados = {f"{t}_{c}_digital.pdf" for c in ("sano", "vencido")
                 for t in ("pasaporte", "credencial_elector", "comprobante_domicilio")}
    assert set(primera) == esperados
    assert primera == segunda  # mismos SHA-256
    assert gf.generar(HOY + timedelta(days=1), tmp_path / "c") != primera  # las fechas si cambian


def test_capa_de_texto_contiene_los_datos(tmp_path):
    import pymupdf
    gf.generar(HOY, tmp_path)
    with pymupdf.open(tmp_path / "pasaporte_vencido_digital.pdf") as doc:
        contenido = doc[0].get_text()
    assert "LUIS DEMO PRUEBAS" in contenido and "31/08/2026" in contenido and "P<UTODEMO<PRUEBAS<<LUIS" in contenido
