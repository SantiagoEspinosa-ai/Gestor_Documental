"""Tests de validacion.recomendar_documento (recomendacion por documento, PERSONA_2). Datos ficticios."""
from datetime import datetime, timezone

import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.validacion import servicio as validacion
from app.schemas.resultado import (Alerta, EstadoAnalisis, Recomendacion, ReferenciaArchivoOriginal,
                                   ResultadoDocumento, Severidad)

DATOS = {"nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": "ZX0000001", "fecha_nacimiento": "1990-01-01",
         "fecha_expedicion": "2021-09-30", "fecha_vencimiento": "2031-09-30", "nacionalidad": "UTOPICA", "sexo": "F"}


def resultado(**cambios) -> ResultadoDocumento:
    base = dict(
        folio_solicitud="ONB-2026-000001", identificador_unico_documento="00000000-0000-4000-8000-000000000001",
        tipo_documental_declarado="pasaporte", tipo_documental_detectado="pasaporte", confianza_clasificacion=1.0,
        datos_extraidos=dict(DATOS), nivel_confianza_por_campo=dict.fromkeys(DATOS, 1.0),
        estado_analisis=EstadoAnalisis.completado, alertas_encontradas=[],
        referencia_archivo_original=ReferenciaArchivoOriginal(nombre_archivo="p.pdf", ruta="local://p.pdf", hash="0" * 64),
    )
    return ResultadoDocumento(**{**base, **cambios})


def alerta(codigo, severidad, aplica=None, campo=None):
    return Alerta(codigo=codigo, mensaje="m", severidad=severidad, confianza=1.0, campo=campo, aplica=aplica)


@pytest.fixture(scope="module")
def ficha():
    return configuracion.obtener("pasaporte")


def recomendar(r, ficha):
    return validacion.recomendar_documento(r, ficha)


def test_todo_correcto_aprobar(ficha):
    assert recomendar(resultado(), ficha) is Recomendacion.aprobar


def test_acepta_la_ficha_como_dict(ficha):
    assert recomendar(resultado(), ficha.model_dump(mode="json")) is Recomendacion.aprobar


@pytest.mark.parametrize("estado", [EstadoAnalisis.error, EstadoAnalisis.pendiente, EstadoAnalisis.procesando])
def test_sin_completar_revision(estado, ficha):
    assert recomendar(resultado(estado_analisis=estado), ficha) is Recomendacion.revision_manual


def test_sin_ficha_revision():
    assert recomendar(resultado(tipo_documental_detectado="desconocido"), None) is Recomendacion.revision_manual


@pytest.mark.parametrize("severidad", [Severidad.critica, Severidad.bloqueante])
def test_alerta_critica_o_bloqueante_sin_revisar_o_confirmada_revision(severidad, ficha):
    for aplica in (None, True):
        r = resultado(alertas_encontradas=[alerta("REG-vigencia_documento", severidad, aplica)])
        assert recomendar(r, ficha) is Recomendacion.revision_manual


def test_falso_positivo_no_frena(ficha):
    r = resultado(alertas_encontradas=[alerta("CLS-001", Severidad.critica, aplica=False)])
    assert recomendar(r, ficha) is Recomendacion.aprobar


@pytest.mark.parametrize("severidad", [Severidad.preventiva, Severidad.informativa])
def test_preventivas_e_informativas_no_frenan(severidad, ficha):
    r = resultado(alertas_encontradas=[alerta("VAL-004", severidad, campo="sexo")])
    assert recomendar(r, ficha) is Recomendacion.aprobar


def test_confianza_de_clasificacion_baja_o_ausente_revision(ficha):
    assert recomendar(resultado(confianza_clasificacion=0.84), ficha) is Recomendacion.revision_manual
    assert recomendar(resultado(confianza_clasificacion=None), ficha) is Recomendacion.revision_manual
    assert recomendar(resultado(confianza_clasificacion=0.85), ficha) is Recomendacion.aprobar  # el minimo pasa


def test_campo_con_valor_y_confianza_baja_revision(ficha):
    r = resultado(nivel_confianza_por_campo={**dict.fromkeys(DATOS, 1.0), "nombre_completo": 0.4})
    assert recomendar(r, ficha) is Recomendacion.revision_manual


def test_campo_vacio_no_cuenta_en_las_confianzas(ficha):
    # el opcional vacio lleva VAL-004 (informativa) y confianza 0: no frena
    r = resultado(datos_extraidos={**DATOS, "sexo": None}, nivel_confianza_por_campo={**dict.fromkeys(DATOS, 1.0), "sexo": 0.0})
    assert recomendar(r, ficha) is Recomendacion.aprobar


def test_nunca_recomienda_rechazar_d1(ficha):
    # el peor caso posible: vencido, critica, confianzas bajas
    r = resultado(confianza_clasificacion=0.0, nivel_confianza_por_campo=dict.fromkeys(DATOS, 0.0),
                  alertas_encontradas=[alerta("REG-vigencia_documento", Severidad.bloqueante),
                                       alerta("CLS-001", Severidad.critica)])
    assert recomendar(r, ficha) is Recomendacion.revision_manual


def test_tipo_confirmado_con_confianza_1_aprobar(ficha):
    r = resultado(tipo_documental_confirmado="pasaporte", tipo_documental_detectado=None, confianza_clasificacion=1.0)
    assert recomendar(r, ficha) is Recomendacion.aprobar
