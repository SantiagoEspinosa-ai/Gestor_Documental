"""Tests de la confianza calculada por el codigo (ADR-007, motor_ia/confianza.py). Datos ficticios."""
import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.confianza import (
    TOPE_MRZ_FALLIDA,
    VerificacionMrz,
    confianza_clasificacion,
    confianzas_de_campos,
    normalizar_texto,
)

PASAPORTE = ("PASAPORTE\nNOMBRE COMPLETO\nANA EJEMPLO PRUEBA\nNUMERO PASAPORTE\nZX0000001\nFECHA NACIMIENTO\n"
             "01/01/1990\nFECHA EXPEDICION\n30/09/2021\nFECHA VENCIMIENTO\n30/09/2031\nNACIONALIDAD\nUTOPICA\n"
             "SEXO\nF\nP<UTOEJEMPLO<PRUEBA<<ANA<<<<<<<<<<<<<<<<<<<<<\n"
             "ZX00000015UTO9001011F3109306<<<<<<<<<<<<<<06")
DATOS = {"nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": "ZX0000001", "fecha_nacimiento": "1990-01-01",
         "fecha_expedicion": "2021-09-30", "fecha_vencimiento": "2031-09-30", "nacionalidad": "UTOPICA", "sexo": "F"}


@pytest.fixture(scope="module")
def ficha():
    return configuracion.obtener("pasaporte")


def campos(datos, ficha, texto=PASAPORTE, mrz=None):
    return confianzas_de_campos(datos, ficha, normalizar_texto(texto), mrz)


def test_normalizar_texto_mayusculas_sin_acentos_y_por_lineas():
    assert normalizar_texto("Fecha de  expedición\n  número ") == "FECHA DE EXPEDICION\nNUMERO"


# --- Campos ---

def test_valores_que_aparecen_y_con_formato_valido_valen_1(ficha):
    assert set(campos(DATOS, ficha).values()) == {1.0}


def test_campo_null_vale_0(ficha):
    assert campos({**DATOS, "sexo": None}, ficha)["sexo"] == 0.0


def test_valor_que_no_aparece_en_el_texto_solo_cuenta_el_formato(ficha):
    # p. ej. leido con vision en una foto con OCR malo: el dato no se puede verificar
    assert campos({**DATOS, "nacionalidad": "OTRA"}, ficha)["nacionalidad"] == 0.4


def test_valor_parecido_cuenta_su_parecido(ficha):
    texto = PASAPORTE.replace("ANA EJEMPLO PRUEBA", "ANA EJEMPL0 PRUEBA")  # el OCR leyo un cero
    c = campos(DATOS, ficha, texto)["nombre_completo"]
    assert 0.9 < c < 1.0


def test_valor_poco_parecido_no_cuenta(ficha):
    assert campos({**DATOS, "nombre_completo": "LUIS DEMO PRUEBAS"}, ficha)["nombre_completo"] == 0.4


def test_patron_incumplido_baja_la_confianza(ficha):
    texto = PASAPORTE.replace("ZX0000001", "ZX00-0001")
    assert campos({**DATOS, "numero_pasaporte": "ZX00-0001"}, ficha, texto)["numero_pasaporte"] == 0.6


def test_fecha_que_no_se_pudo_normalizar_vale_poco(ficha):
    assert campos({**DATOS, "fecha_expedicion": "mayo 2034"}, ficha)["fecha_expedicion"] == 0.0


def test_fecha_en_el_texto_sin_separador(ficha):
    texto = PASAPORTE.replace("30/09/2021", "3009/2021")  # el OCR perdio una barra
    assert campos(DATOS, ficha, texto)["fecha_expedicion"] == 1.0


@pytest.mark.parametrize("en_el_texto", ["30 SEP 2021", "30-SEP-2021", "30 DE SEPTIEMBRE DE 2021", "30 SEP 21",
                                         "30 sept. 2021", "30SEP2021"])
def test_fecha_iso_se_verifica_contra_su_forma_en_letras(ficha, en_el_texto):
    texto = PASAPORTE.replace("30/09/2021", en_el_texto)
    assert campos(DATOS, ficha, texto)["fecha_expedicion"] == 1.0  # 2021-09-30 <-> "30 SEP 2021"


def test_rango_pegado_del_texto_da_sus_dos_fechas_y_ninguna_mezcla():
    from app.modulos.motor_ia.confianza import _fechas_del_texto
    assert _fechas_del_texto(normalizar_texto("PERIODO 03 DIC 24-04 FEB 25 TOTAL")) == {"2024-12-03", "2025-02-04"}
    assert _fechas_del_texto(normalizar_texto("DEL 03 DIC 2024 AL 04 FEB 2025")) == {"2024-12-03", "2025-02-04"}


def test_mes_en_letras_dentro_de_una_palabra_no_es_fecha():
    from app.modulos.motor_ia.confianza import _fechas_del_texto
    assert _fechas_del_texto(normalizar_texto("CLIENTE 1234MAYO2026 REF115 MARZO20261")) == set()


def test_fecha_con_dia_y_mes_cambiados_no_aparece(ficha):
    assert campos({**DATOS, "fecha_expedicion": "2021-01-09"}, ficha)["fecha_expedicion"] == 0.4


def test_anio_entero():
    credencial = configuracion.obtener("credencial_elector")
    texto = normalizar_texto("VIGENCIA\n2029")
    c = confianzas_de_campos({"vigencia": 2029}, credencial, texto)
    assert c["vigencia"] == 1.0
    assert confianzas_de_campos({"vigencia": "2029-2031"}, credencial, texto)["vigencia"] == 0.0


# --- MRZ ---

def mrz(digitos_ok=True, **cambios):
    digitos = {"numero_documento": True, "fecha_nacimiento": True, "fecha_vencimiento": True,
               "datos_personales": True, "compuesto": digitos_ok}
    valores = {"numero_documento": "ZX0000001", "fecha_nacimiento": "900101", "fecha_vencimiento": "310930",
               "sexo": "F", **cambios}
    return VerificacionMrz(digitos=digitos, **valores)


SOLO_ETIQUETAS = ("PASAPORTE\nNOMBRE COMPLETO\nANA EJEMPLO PRUEBA\nNUMERO PASAPORTE\nFECHA NACIMIENTO\n"
                  "FECHA EXPEDICION\n30/09/2021\nFECHA VENCIMIENTO\nNACIONALIDAD\nUTOPICA\nSEXO")


def test_mrz_con_digitos_fallidos_pone_tope_si_la_zona_visual_no_lo_confirma(ficha):
    c = campos(DATOS, ficha, SOLO_ETIQUETAS, mrz=mrz(digitos_ok=False))
    assert {k: c[k] for k in ("numero_pasaporte", "fecha_nacimiento", "fecha_vencimiento", "sexo")} == dict.fromkeys(
        ("numero_pasaporte", "fecha_nacimiento", "fecha_vencimiento", "sexo"), 0.4)  # sin verificar y <= tope
    assert c["nombre_completo"] == 1.0 and c["fecha_expedicion"] == 1.0   # la MRZ no los cubre


def test_mrz_con_digitos_fallidos_no_castiga_lo_que_la_zona_visual_si_lee(ficha):
    # calibracion: el OCR lee mal la MRZ de pasaporte_vencido_escaneado, pero la zona visual esta bien
    c = campos(DATOS, ficha, mrz=mrz(digitos_ok=False))
    assert set(c.values()) == {1.0}


def test_mrz_con_digitos_fallidos_y_valor_parecido_tiene_tope(ficha):
    texto = PASAPORTE.replace("\nZX0000001\n", "\nZX000O001\n")
    assert campos(DATOS, ficha, texto, mrz=mrz(digitos_ok=False))["numero_pasaporte"] <= TOPE_MRZ_FALLIDA


def test_mrz_correcta_que_dice_otra_cosa_deja_el_valor_sin_verificar(ficha):
    # p. ej. el modelo copio "2X0000001" del OCR y la MRZ, con sus digitos bien, dice ZX0000001
    texto = PASAPORTE.replace("\nZX0000001\n", "\n2X0000001\n")
    c = campos({**DATOS, "numero_pasaporte": "2X0000001"}, ficha, texto, mrz=mrz())
    assert c["numero_pasaporte"] == 0.4


def test_mrz_correcta_verifica_un_valor_que_no_esta_en_la_zona_visual(ficha):
    texto = PASAPORTE.replace("\n30/09/2031", "\n")  # la zona visual no da el vencimiento, la MRZ si
    assert campos(DATOS, ficha, texto, mrz=mrz())["fecha_vencimiento"] == 1.0
    assert campos(DATOS, ficha, texto)["fecha_vencimiento"] == 0.4


# --- Clasificacion ---

@pytest.mark.parametrize("tipo, texto, esperada", [
    ("pasaporte", PASAPORTE, 1.0),
    ("credencial_elector", "CREDENCIAL DE ELECTOR\nCURP\nAEPA900101MDFXXX01\nCLAVE ELECTOR\nX\nVIGENCIA\n2029\n"
                           "DOMICILIO\nCALLE FICTICIA 123\nFECHA NACIMIENTO\n01/01/1990", 1.0),
    ("comprobante_domicilio", "SERVICIOS DE EJEMPLO S.A. - COMPROBANTE DE DOMICILIO\nNOMBRE TITULAR\nANA\n"
                              "DOMICILIO\nCALLE\nFECHA EMISION\n15/09/2026\nTOTAL 731.57", 1.0),
    ("credencial_elector", PASAPORTE, 0.143),  # solo comparte "FECHA NACIMIENTO": 1 de 7
])
def test_confianza_de_clasificacion_por_marcadores(tipo, texto, esperada):
    assert confianza_clasificacion(configuracion.obtener(tipo), normalizar_texto(texto)) == esperada


def test_un_marcador_sin_encontrar_aun_supera_el_umbral(ficha):
    texto = PASAPORTE.replace("NACIONALIDAD", "")
    c = confianza_clasificacion(ficha, normalizar_texto(texto))
    assert c == round(6 / 7, 3) and c >= ficha.confianza_minima_clasificacion


def test_sin_ficha_o_sin_marcadores_vale_0(ficha):
    assert confianza_clasificacion(None, normalizar_texto(PASAPORTE)) == 0.0
    assert confianza_clasificacion(ficha.model_copy(update={"marcadores_clasificacion": []}), "PASAPORTE") == 0.0
