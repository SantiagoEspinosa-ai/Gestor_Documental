"""Nombre de la INE y del pasaporte (fix/nombre-ine-columnas, segunda tanda): ruido en los extremos, nombre desde la
MRZ y comparacion entre documentos sin depender del orden. Datos ficticios."""
from datetime import date

import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.confianza import (
    VerificacionMrz,
    coincide_con_nombre_mrz,
    confianzas_de_campos,
    nombre_segun_mrz,
    normalizar_texto,
)
from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.motor_ia.proveedores.base import CONFIANZA_MAXIMA_CORREGIDO, corregir_lectura_ine, limpiar_ruido_nombre
from app.modulos.motor_ia.servicio import analizar
from app.modulos.orquestador.mrz import Mrz
from app.modulos.validacion import servicio as validacion
from tests.test_servicio_motor import AHORA, REFERENCIA, EnrutadorFalso, ProveedorFalso

PASAPORTE = configuracion.obtener("pasaporte")


# --- 1. Ruido al principio o al final del nombre ---

@pytest.mark.parametrize("leido, esperado", [
    ("ANA EJEMPLO PRUEBA ee", "ANA EJEMPLO PRUEBA"),         # ruido en minusculas al final
    ("ANA EJEMPLO PRUEBA É", "ANA EJEMPLO PRUEBA"),           # letra suelta acentuada al final
    ("Al ANA EJEMPLO PRUEBA", "ANA EJEMPLO PRUEBA"),          # al principio
    ("ANA EJEMPLO PRUEBA ©", "ANA EJEMPLO PRUEBA"),           # un resto sin letras
    ("ANA EJEMPLO PRUEBA ee É", "ANA EJEMPLO PRUEBA"),        # varios seguidos en el extremo
])
def test_quita_el_ruido_de_los_extremos(leido, esperado):
    assert limpiar_ruido_nombre(leido) == esperado


@pytest.mark.parametrize("nombre", [
    "JOSÉ MUÑOZ Y GÓMEZ",            # la "Y" en medio se conserva
    "MARIA DE LA CRUZ LOPEZ",        # "DE LA" se conserva
    "ANA ee EJEMPLO PRUEBA",         # en medio nunca se quita
    "Ana Ejemplo Prueba",            # todo en "Tipo Titulo": no es ruido
    "ANA EJEMPLO",                   # nunca deja menos de 2 palabras
    "ANA É",
])
def test_no_toca_lo_que_no_es_ruido_en_un_extremo(nombre):
    assert limpiar_ruido_nombre(nombre) is None


def test_solo_ine_y_pasaporte_y_con_el_tope():
    datos = {"nombre_completo": "ANA EJEMPLO PRUEBA ee"}
    assert corregir_lectura_ine(datos, "comprobante_domicilio") == (datos, set())
    for tipo in ("credencial_elector", "pasaporte"):
        corregidos, campos = corregir_lectura_ine(datos, tipo)
        assert corregidos["nombre_completo"] == "ANA EJEMPLO PRUEBA" and "nombre_completo" in campos


# --- 2. Pasaporte: el nombre desde la MRZ ---

LINEA1 = "P<UTOEJEMPLO<PRUEBA<<ANA<<<<<<<<<<<<<<<<<<<<"


def mrz(compuesto: bool = True, nombre=("EJEMPLO PRUEBA", "ANA")) -> VerificacionMrz:
    return VerificacionMrz("ZX0000001", "900101", "310930", "F", {"compuesto": compuesto, "numero_documento": True,
                           "fecha_nacimiento": True, "fecha_vencimiento": True}, 1, nombre)


def test_la_linea_1_trae_apellidos_y_nombres():
    assert len(LINEA1) == 44
    assert Mrz(LINEA1, "<" * 44).apellidos_y_nombres == ("EJEMPLO PRUEBA", "ANA")
    assert Mrz("P<UTO" + "<" * 39, "<" * 44).apellidos_y_nombres is None


@pytest.mark.parametrize("nombre", ["ANA EJEMPLO PRUEBA", "EJEMPLO PRUEBA ANA", "ÁNA EJEMPLO PRUEBA"])
def test_si_coincide_con_la_mrz_el_nombre_sale_verificado(nombre):
    # Sin importar el orden ni los acentos (la MRZ no los tiene); aunque no este tal cual en el texto
    texto = normalizar_texto("PASAPORTE\nAPELLIDOS EJEMPLO\nNOMBRES ANA")
    assert coincide_con_nombre_mrz(nombre, mrz())
    assert confianzas_de_campos({"nombre_completo": nombre}, PASAPORTE, texto, mrz())["nombre_completo"] == 1.0


def test_sin_compuesto_valido_no_se_usa_el_nombre_de_la_mrz():
    assert not coincide_con_nombre_mrz("ANA EJEMPLO PRUEBA", mrz(compuesto=False))
    assert nombre_segun_mrz("ANA EJEMPLO PRUEBA XX", mrz(compuesto=False)) is None


@pytest.mark.parametrize("leido, esperado", [
    ("ANA EJEMPLO PRUEBA XQ", "ANA EJEMPLO PRUEBA"),          # palabra de mas: se quita
    ("ÁNA EJEMPLO PRUEBA é", "ÁNA EJEMPLO PRUEBA"),           # conserva el acento y el orden del texto
    ("EJEMPLO XQ PRUEBA ANA", "EJEMPLO PRUEBA ANA"),          # tambien en medio, si la MRZ lo dice
    ("ANA EJEMPLO PRUEBA", None),                             # ya coincide: nada que quitar
    ("ANA EJEMPLO", None),                                    # le falta una palabra: no se toca
    ("ANA EJEMPLO PRUEVA", None),                             # una palabra distinta: no se toca
])
def test_nombre_con_ruido_y_mrz_valida(leido, esperado):
    assert nombre_segun_mrz(leido, mrz()) == esperado


def test_el_servicio_usa_la_mrz_con_el_tope():
    texto = "PASAPORTE\nANA EJEMPLO PRUEBA XQ\nP<UTOEJEMPLO<PRUEBA<<ANA"
    doc = DocumentoPreparado("id", Modalidad.imagen, [Pagina(1, texto=texto)], "pasaporte")
    datos = {"nombre_completo": "ANA EJEMPLO PRUEBA XQ", "numero_pasaporte": "ZX0000001", "fecha_nacimiento": "1990-01-01",
             "fecha_expedicion": "2021-09-30", "fecha_vencimiento": "2031-09-30", "nacionalidad": "UTOPICA", "sexo": "F"}
    analisis = analizar(doc, folio="CLI-2026-000000", referencia=REFERENCIA, ahora=AHORA, mrz=mrz(),
                        enrutador=EnrutadorFalso(ProveedorFalso("ollama", tipo="pasaporte", datos=datos)))
    r = analisis.resultado
    assert r.datos_extraidos["nombre_completo"] == "ANA EJEMPLO PRUEBA"
    assert r.nivel_confianza_por_campo["nombre_completo"] <= CONFIANZA_MAXIMA_CORREGIDO
    alertas, _ = validacion.evaluar_reglas(r.datos_extraidos, r.nivel_confianza_por_campo, PASAPORTE, hoy=date(2026, 10, 12))
    assert ("VAL-002", "nombre_completo") in {(a.codigo, a.campo) for a in alertas}
