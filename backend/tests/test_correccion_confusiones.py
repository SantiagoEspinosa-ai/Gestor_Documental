"""Correccion de confusiones de OCR (letra/digito) en campos con patron: CURP y similares. Datos ficticios."""
import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina, ResultadoExtraccion
from app.modulos.motor_ia.proveedores.base import (
    CONFIANZA_MAXIMA_CORREGIDO,
    campos_con_formato_invalido,
    corregir_campos_con_patron,
    corregir_confusiones,
)
from app.modulos.motor_ia.servicio import analizar
from tests.test_servicio_motor import AHORA, REFERENCIA, EnrutadorFalso, ProveedorFalso

PATRON_CURP = r"^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[A-Z0-9][0-9]$"
CURP = "AEPA900101MDFXXX01"  # ficticia: nacimiento 1990-01-01


# --- corregir_confusiones ---

@pytest.mark.parametrize("leida, esperada", [
    ("AEPA9OO1O1MDFXXX01", CURP),    # O por 0 en posiciones de digito (fecha)
    ("AEPA90010IMDFXXX01", CURP),    # I por 1 en una posicion de digito
    ("AEPA90010LMDFXXX01", CURP),    # L por 1
    ("AEPA900101MDFXXXO1", None),    # la posicion 17 admite letra o digito: ya es valida, no se toca
    ("AEPA9OO101MDFXXXO1", "AEPA900101MDFXXXO1"),  # se corrigen 5 y 6; la O de la 17 no crea ambiguedad
    ("A3PA900101MDFXXX01", None),    # 3 no es una confusion conocida: no hay candidata
    ("4EPA900101MDFXXX01", None),    # idem
    ("0EPA900101MDFXXX01", "OEPA900101MDFXXX01"),  # 0 por O en una posicion de letra
    ("AEP4900101MDFXXX01", None),    # 4 no tiene pareja
    ("AE5A900101MDFXXX01", "AESA900101MDFXXX01"),  # 5 por S en una posicion de letra
    (CURP, None),                    # ya cumple el patron: no se toca
])
def test_confusiones_en_posiciones_de_letra_y_de_digito(leida, esperada):
    assert corregir_confusiones(leida, PATRON_CURP) == esperada


def test_varias_candidatas_no_se_corrige():
    # "O1" no cumple ^([A-Z]{2}|[0-9]{2})$ y tiene dos arreglos de un cambio: "01" y "OI"
    assert corregir_confusiones("O1", r"^([A-Z]{2}|[0-9]{2})$") is None


def test_sin_candidata_sigue_invalido():
    assert corregir_confusiones("AEPA90X101MDFXXX01", PATRON_CURP) is None
    assert corregir_confusiones("", PATRON_CURP) is None


def test_curp_que_no_cuadra_con_el_nacimiento_no_se_corrige():
    esquema = configuracion.obtener("credencial_elector").campos
    leida = "AEPA9OO1O1MDFXXX01"
    assert corregir_campos_con_patron({"curp": leida, "fecha_nacimiento": "1990-01-01"}, esquema) == (
        {"curp": CURP, "fecha_nacimiento": "1990-01-01"}, {"curp"})
    assert corregir_campos_con_patron({"curp": leida, "fecha_nacimiento": "1991-02-03"}, esquema) == (
        {"curp": leida, "fecha_nacimiento": "1991-02-03"}, set())
    # Sin fecha de nacimiento (o ilegible) se corrige solo por el patron
    assert corregir_campos_con_patron({"curp": leida, "fecha_nacimiento": None}, esquema)[1] == {"curp"}


def test_un_valor_corregible_no_cuenta_como_formato_invalido():
    esquema = {n: c.model_dump(mode="json") for n, c in configuracion.obtener("credencial_elector").campos.items()}
    def resultado(curp):
        return ResultadoExtraccion({"curp": curp, "fecha_nacimiento": "1990-01-01"}, {}, {})
    assert "curp" not in campos_con_formato_invalido(resultado("AEPA9OO1O1MDFXXX01"), esquema)
    assert "curp" in campos_con_formato_invalido(resultado("AEPA90X101MDFXXX01"), esquema)
    assert "curp" in campos_con_formato_invalido(resultado("AEPA9OO1O1MDFXXX01".replace("9OO1O1", "9OO2O3")), esquema)


# --- servicio: confianza limitada para que salte el VAL-002 existente ---

def test_cero_seis_queda_por_debajo_del_minimo_de_todas_las_fichas():
    assert all(CONFIANZA_MAXIMA_CORREGIDO < f.confianza_minima_campo for f in configuracion.listar())


def test_el_servicio_corrige_y_limita_la_confianza():
    texto = ("CREDENCIAL PARA VOTAR\nNOMBRE\nANA EJEMPLO PRUEBA\nCURP\nAEPA9OO1O1MDFXXX01\nCLAVE DE ELECTOR\n"
             "EJPRAN90010109M100\nFECHA DE NACIMIENTO\n01/01/1990\nDOMICILIO\nCALLE FICTICIA 123\nVIGENCIA\n2029")
    doc = DocumentoPreparado("id", Modalidad.pdf_digital, [Pagina(1, texto=texto)], "credencial_elector")
    datos = {"nombre_completo": "ANA EJEMPLO PRUEBA", "curp": "AEPA9OO1O1MDFXXX01", "clave_elector": "EJPRAN90010109M100",
             "fecha_nacimiento": "01/01/1990", "domicilio": "CALLE FICTICIA 123", "vigencia": "2029"}
    analisis = analizar(doc, folio="CLI-2026-000000", referencia=REFERENCIA, ahora=AHORA,
                        enrutador=EnrutadorFalso(ProveedorFalso("ollama", tipo="credencial_elector", datos=datos)))
    r = analisis.resultado
    assert r.datos_extraidos["curp"] == CURP
    assert r.nivel_confianza_por_campo["curp"] <= CONFIANZA_MAXIMA_CORREGIDO
    assert r.nivel_confianza_por_campo["nombre_completo"] == 1.0  # los demas no cambian
