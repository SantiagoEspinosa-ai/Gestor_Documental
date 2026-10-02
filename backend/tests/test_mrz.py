"""Tests de orquestador/mrz.py con el especimen publico de la OACI (Doc 9303, datos ficticios)."""
import pytest

from app.modulos.orquestador.mrz import Mrz, buscar_mrz, digito_control, validar_digitos

# Especimen de la OACI (Doc 9303): pais ficticio UTO, todos los digitos de control correctos.
LINEA1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
LINEA2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_especimen_bien_formado():
    assert len(LINEA1) == len(LINEA2) == 44


def test_buscar_mrz_en_texto_con_espacios_y_ruido():
    texto = f"PASAPORTE\nNombre: ANNA\n\n{LINEA1[:20]} {LINEA1[20:]}\n{LINEA2[:10]}  {LINEA2[10:]}\nfin"
    mrz = buscar_mrz(texto)
    assert mrz == Mrz(LINEA1, LINEA2)
    assert (mrz.numero_documento, mrz.fecha_nacimiento, mrz.sexo, mrz.fecha_vencimiento) == \
        ("L898902C3", "740812", "F", "120415")


@pytest.mark.parametrize("texto", [None, "", "sin mrz", f"{LINEA1}\n{LINEA2[:-1]}", f"{LINEA1[1:]}X\n{LINEA2}",
                                   f"{LINEA1}\n{LINEA2.replace('<', '#')}"])
def test_sin_mrz(texto):
    assert buscar_mrz(texto) is None


def test_digitos_de_control_correctos():
    assert validar_digitos(Mrz(LINEA1, LINEA2)) == {
        "numero_documento": True, "fecha_nacimiento": True, "fecha_vencimiento": True,
        "datos_personales": True, "compuesto": True,
    }


def test_confusion_z_2_se_detecta():
    # Error tipico de OCR: un 2 leido como Z en la fecha de nacimiento.
    erronea = LINEA2[:18] + "Z" + LINEA2[19:]
    resultado = validar_digitos(Mrz(LINEA1, erronea))
    assert resultado["fecha_nacimiento"] is False and resultado["compuesto"] is False
    assert resultado["numero_documento"] is True


@pytest.mark.parametrize("control", ["<", "0"])
def test_datos_personales_de_relleno(control):
    linea2 = "L898902C36UTO7408122F1204159" + "<" * 14 + control + "4"
    assert validar_digitos(Mrz(LINEA1, linea2))["datos_personales"] is True


def test_sexo_sin_especificar():
    assert Mrz(LINEA1, LINEA2[:20] + "<" + LINEA2[21:]).sexo is None


def test_digito_control():
    assert digito_control("L898902C3") == "6"
    assert digito_control("740812") == "2"
    assert digito_control("12#") is None
