"""Lectura de la INE (fix/nombre-ine-columnas): nombre con la otra columna mezclada y posicion 17 de la CURP.
Datos ficticios."""
from datetime import date

import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.motor_ia.proveedores.base import (
    CONFIANZA_MAXIMA_CORREGIDO,
    corregir_lectura_ine,
    corregir_siglo_curp,
    limpiar_nombre_columnas,
    normalizar_fecha,
)
from app.modulos.motor_ia.servicio import analizar
from app.modulos.validacion.servicio import evaluar_reglas
from tests.test_servicio_motor import AHORA, REFERENCIA, EnrutadorFalso, ProveedorFalso

CREDENCIAL = configuracion.obtener("credencial_elector")


# --- Fallo 1: nombre con la otra columna mezclada ---

@pytest.mark.parametrize("leido, esperado", [
    ("ANA 01/01/1990 EJEMPLO SEXO M PRUEBA", "ANA EJEMPLO PRUEBA"),          # como el OCR del fixture en columnas
    ("NOMBRE FECHA DE NACIMIENTO ANA EJEMPLO PRUEBA", "ANA EJEMPLO PRUEBA"),
    ("ANA FECHADENACIMIENTO EJEMPLO PRUEBA SEXO: H", "ANA EJEMPLO PRUEBA"),  # variantes de OCR de la etiqueta
    ("ANA FECHA DE NAC. 1990-01-01 EJEMPLO PRUEBA", "ANA EJEMPLO PRUEBA"),
    ("ANA , EJEMPLO | PRUEBA 7X1", "ANA EJEMPLO PRUEBA"),                     # signos y palabras con digitos
    ("MARIA DE LA CRUZ 01/01/1990 SEXO M LOPEZ", "MARIA DE LA CRUZ LOPEZ"),   # "DE LA" se queda
    ("PEÑA 12/03/1990 NUÑEZ SEXO M JOSÉ", "PEÑA NUÑEZ JOSÉ"),                 # Ñ y acentos
])
def test_limpia_lo_que_se_cuela_de_la_otra_columna(leido, esperado):
    assert limpiar_nombre_columnas(leido) == esperado


@pytest.mark.parametrize("nombre", [
    "MARIA DE LA CRUZ LOPEZ",        # DE y LA sueltas son parte del apellido
    "JOSE DEL RIO PEREZ",
    "ANA DE LOS SANTOS",
    "ÑUÑEZ PEÑA GÜEMES ANA",         # Ñ y Ü cuentan como letras
    "JOSÉ MUÑOZ Y GÓMEZ",            # la "Y" de los apellidos compuestos tampoco se quita
    "Ana Ejemplo Prueba",
])
def test_un_nombre_limpio_sale_intacto(nombre):
    assert limpiar_nombre_columnas(nombre) is None


@pytest.mark.parametrize("leido", ["01/01/1990 SEXO M", "ANA 01/01/1990", "", None, "X 1990 Y"])
def test_si_no_queda_un_nombre_valido_se_deja_como_estaba(leido):
    assert limpiar_nombre_columnas(leido) is None


# --- Fallo 2: posicion 17 de la CURP ---

def test_fecha_dd_mm_aaaa_con_dia_menor_o_igual_que_12_contra_la_curp():
    # Caso ambiguo: 05/03/1990 es el 5 de marzo (DD/MM/AAAA), nunca el 3 de mayo
    assert normalizar_fecha("05/03/1990") == "1990-03-05"
    fecha = normalizar_fecha("05/03/1990")
    _, bien = evaluar_reglas({"curp": "AEPA900305MDFXXX01", "fecha_nacimiento": fecha}, {}, CREDENCIAL, hoy=date(2026, 10, 12))
    assert "curp_coincide_nacimiento" in bien.cumplidas
    _, mal = evaluar_reglas({"curp": "AEPA900503MDFXXX01", "fecha_nacimiento": fecha}, {}, CREDENCIAL, hoy=date(2026, 10, 12))
    assert "curp_coincide_nacimiento" in mal.incumplidas  # dia y mes cambiados: si es un fallo de verdad


@pytest.mark.parametrize("curp, fecha, esperada", [
    ("AEPA900101MDFXXXO1", "1990-01-01", "AEPA900101MDFXXX01"),   # antes de 2000: O -> 0
    ("AEPA900101MDFXXXI1", "01/01/1990", "AEPA900101MDFXXX11"),   # I -> 1, con la fecha en DD/MM/AAAA
    ("AEPA050101MDFXXX01", "2005-01-01", "AEPA050101MDFXXXO1"),   # desde 2000: 0 -> O
    ("AEPA900101MDFXXX01", "1990-01-01", None),                    # ya es un digito: nada que corregir
    ("AEPA900101MDFXXXX1", "1990-01-01", None),                    # X no es una confusion de la lista: se deja
    ("AEPA900101MDFXXXO1", "1991-01-01", None),                    # 5-10 no cuadran con la fecha: no se toca
    ("AEPA900101MDFXXXO1", None, None),
])
def test_siglo_de_la_curp(curp, fecha, esperada):
    assert corregir_siglo_curp({"curp": curp, "fecha_nacimiento": fecha}) == esperada


def test_solo_la_credencial_y_solo_la_curp():
    datos = {"curp": "AEPA900101MDFXXXO1", "fecha_nacimiento": "1990-01-01", "clave_elector": "EJPRAN90010199M1O1",
             "nombre_completo": "ANA 01/01/1990 EJEMPLO SEXO M PRUEBA"}
    assert corregir_lectura_ine(datos, "pasaporte") == (datos, set())
    corregidos, campos = corregir_lectura_ine(datos, "credencial_elector")
    assert campos == {"curp", "nombre_completo"}
    assert corregidos["clave_elector"] == datos["clave_elector"]  # otros campos, igual


def test_con_otro_caracter_en_la_posicion_17_el_aviso_sigue():
    datos = {"curp": "AEPA900101MDFXXXX1", "fecha_nacimiento": "1990-01-01"}
    corregidos, campos = corregir_lectura_ine(datos, "credencial_elector")
    assert campos == set()
    _, reglas = evaluar_reglas(corregidos, {}, CREDENCIAL, hoy=date(2026, 10, 12))
    assert "curp_coincide_nacimiento" in reglas.incumplidas


# --- Servicio: confianza honesta (VAL-002 para que el revisor lo compruebe) ---

def test_el_servicio_corrige_y_limita_la_confianza():
    texto = ("CREDENCIAL PARA VOTAR\nNOMBRE FECHA DE NACIMIENTO\n01/01/1990\nANA\nEJEMPLO SEXO M\nPRUEBA\nCURP\n"
             "AEPA900101MDFXXXO1\nCLAVE DE ELECTOR\nEJPRAN90010199M101\nDOMICILIO\nCALLE FICTICIA 123\nVIGENCIA\n2029")
    doc = DocumentoPreparado("id", Modalidad.imagen, [Pagina(1, texto=texto)], "credencial_elector")
    datos = {"nombre_completo": "ANA 01/01/1990 EJEMPLO SEXO M PRUEBA", "curp": "AEPA900101MDFXXXO1",
             # la fecha ya normalizada a ISO, como la devuelve el proveedor real (normalizar_fecha)
             "clave_elector": "EJPRAN90010199M101", "fecha_nacimiento": "1990-01-01", "domicilio": "CALLE FICTICIA 123",
             "vigencia": "2029"}
    analisis = analizar(doc, folio="CLI-2026-000000", referencia=REFERENCIA, ahora=AHORA,
                        enrutador=EnrutadorFalso(ProveedorFalso("ollama", tipo="credencial_elector", datos=datos)))
    r = analisis.resultado
    assert r.datos_extraidos["nombre_completo"] == "ANA EJEMPLO PRUEBA"
    assert r.datos_extraidos["curp"] == "AEPA900101MDFXXX01"
    for campo in ("nombre_completo", "curp"):
        assert r.nivel_confianza_por_campo[campo] <= CONFIANZA_MAXIMA_CORREGIDO < 1.0
    alertas, reglas = evaluar_reglas(r.datos_extraidos, r.nivel_confianza_por_campo, CREDENCIAL, hoy=date(2026, 10, 12))
    assert {(a.codigo, a.campo) for a in alertas} >= {("VAL-002", "nombre_completo"), ("VAL-002", "curp")}
    assert "curp_coincide_nacimiento" in reglas.cumplidas  # ya no salta el aviso de la CURP
    assert r.nivel_confianza_por_campo["clave_elector"] == 1.0  # los demas no cambian


# --- Nombre cortado: confianza honesta (ADR-007) ---

from app.modulos.motor_ia.confianza import TOPE_NOMBRE_CORTADO, confianzas_de_campos, normalizar_texto  # noqa: E402

TEXTO_INE = normalizar_texto("NOMBRE\nANA\nEJEMPLO\nPRUEBA\nMARIA DE LA CRUZ\nCURP\nAEPA900101MDFXXX01")


@pytest.mark.parametrize("tipo", ["credencial_elector", "pasaporte"])
def test_nombre_de_una_palabra_queda_en_0_6_aunque_aparezca(tipo):
    ficha = configuracion.obtener(tipo)
    confianzas = confianzas_de_campos({"nombre_completo": "EJEMPLO"}, ficha, TEXTO_INE)
    assert confianzas["nombre_completo"] == TOPE_NOMBRE_CORTADO
    alertas, _ = evaluar_reglas({"nombre_completo": "EJEMPLO"}, confianzas, ficha, hoy=date(2026, 10, 12))
    assert ("VAL-002", "nombre_completo") in {(a.codigo, a.campo) for a in alertas}


@pytest.mark.parametrize("nombre", ["ANA EJEMPLO", "MARIA DE LA CRUZ"])
def test_nombre_de_dos_palabras_o_mas_sin_cambios(nombre):
    texto = normalizar_texto(f"NOMBRE\n{nombre}")
    confianzas = confianzas_de_campos({"nombre_completo": nombre}, CREDENCIAL, texto)
    assert confianzas["nombre_completo"] == 1.0


def test_el_tope_no_toca_otros_tipos_ni_otros_campos():
    comprobante = configuracion.obtener("comprobante_domicilio")
    texto = normalizar_texto("TITULAR\nEJEMPLO\nDOMICILIO\nCALLE")
    confianzas = confianzas_de_campos({"nombre_titular": "EJEMPLO", "domicilio": "CALLE"}, comprobante, texto)
    assert confianzas["nombre_titular"] == 1.0 and confianzas["domicilio"] == 1.0
