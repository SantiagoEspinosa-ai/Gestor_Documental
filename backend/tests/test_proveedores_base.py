"""Tests de motor_ia/proveedores/base.py con respuestas guardadas en tests/respuestas_modelo/. Sin modelo."""
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.interfaces import Modalidad, Pagina, ResultadoExtraccion
from app.modulos.motor_ia.proveedores.base import (
    DESCONOCIDO,
    MARCA_RECORTE,
    RespuestaNoValida,
    combinar_lotes,
    limpiar_json,
    lotes_de_paginas,
    normalizar_fecha,
    parsear_clasificacion,
    parsear_extraccion,
    postprocesar_clasificacion,
    postprocesar_extraccion,
    recortar_texto,
    reducir_imagen,
    timeout_vision,
)

RESPUESTAS = Path(__file__).parent / "respuestas_modelo"
TIPOS = ["comprobante_domicilio", "credencial_elector", "pasaporte"]


def contenido(nombre: str) -> str:
    return json.loads((RESPUESTAS / f"{nombre}.json").read_text(encoding="utf-8"))["message"]["content"]


def esquema(tipo: str) -> dict:
    return {n: c.model_dump(mode="json") for n, c in configuracion.cargar()[tipo].campos.items()}


def png(ancho: int, alto: int) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), (200, 200, 200)).save(salida, format="PNG")
    return salida.getvalue()


# --- normalizar_fecha (los 11 casos de docs/motor_ia/pruebas_ollama/prueba_fechas.py) ---

@pytest.mark.parametrize("entrada, esperado", [
    ("25/07/2031", "2031-07-25"), ("10/05/2024", "2024-05-10"), ("1/1/1990", "1990-01-01"),
    ("10.05.2024", "2024-05-10"), ("10-05-2024", "2024-05-10"), ("2024-05-10", "2024-05-10"),
    ("31/02/2024", None), ("2024/05/10", None), ("mayo 2024", None), (None, None), (20240510, None),
])
def test_normalizar_fecha(entrada, esperado):
    assert normalizar_fecha(entrada) == esperado


# --- limpiar y parsear ---

@pytest.mark.parametrize("texto", [
    '{"a": 1}', '```json\n{"a": 1}\n```', 'Aqui tienes:\n{"a": 1}\nGracias', '```\n{"a": 1}```',
])
def test_limpiar_json(texto):
    assert json.loads(limpiar_json(texto)) == {"a": 1}


def test_parsear_respuestas_guardadas():
    assert parsear_extraccion(contenido("texto_gemma4_extraccion_pasaporte_ok")).datos_extraidos["sexo"] == "F"
    assert parsear_clasificacion(contenido("texto_gemma4_clasificacion_pasaporte")).confianza == 0.95


@pytest.mark.parametrize("texto, mensaje", [
    ("no soy un JSON", "no es un JSON valido"),
    ("[1, 2]", "debe ser un objeto"),
    ('{"datos_extraidos": {}, "nivel_confianza_por_campo": {}}', "evidencia_por_campo"),
    ('{"datos_extraidos": [], "nivel_confianza_por_campo": {}, "evidencia_por_campo": {}}', "datos_extraidos"),
])
def test_parsear_extraccion_invalida(texto, mensaje):
    with pytest.raises(RespuestaNoValida, match=mensaje):
        parsear_extraccion(texto)


def test_parsear_clasificacion_sin_confianza():
    with pytest.raises(RespuestaNoValida, match="confianza"):
        parsear_clasificacion('{"tipo_documental_detectado": "pasaporte"}')


def test_observaciones_como_texto_o_nulas():
    base = '{"datos_extraidos": {}, "nivel_confianza_por_campo": {}, "evidencia_por_campo": {}, "observaciones_visuales": %s}'
    assert parsear_extraccion(base % '"legible"').observaciones_visuales == ["legible"]
    assert parsear_extraccion(base % "null").observaciones_visuales == []


# --- postprocesar_extraccion con respuestas reales ---

def test_texto_gemma4_siete_de_siete():
    r = postprocesar_extraccion(parsear_extraccion(contenido("texto_gemma4_extraccion_pasaporte_ok")),
                                esquema("pasaporte"), Modalidad.pdf_digital, [1])
    assert r.datos_extraidos == {
        "nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": "X1234567P", "fecha_nacimiento": "1990-01-01",
        "fecha_expedicion": "2024-05-10", "fecha_vencimiento": "2034-05-09", "nacionalidad": "PAIS FICTICIO",
        "sexo": "F",
    }
    # En texto se conserva el detalle de la evidencia.
    assert r.evidencia_por_campo["fecha_vencimiento"] == "pagina_1:Fecha de caducidad"
    assert r.nivel_confianza_por_campo["numero_pasaporte"] == 1.0


def test_vision_qwen_fechas_tal_cual_se_normalizan_y_sobran_campos():
    r = postprocesar_extraccion(parsear_extraccion(contenido("vision_qwen_extraccion_fechas_tal_cual")),
                                esquema("pasaporte"), Modalidad.imagen, [1])
    assert (r.datos_extraidos["fecha_nacimiento"], r.datos_extraidos["fecha_expedicion"],
            r.datos_extraidos["fecha_vencimiento"]) == ("1990-01-01", "2024-05-10", "2031-07-25")
    assert "tipo" not in r.datos_extraidos and "pais_emisor" not in r.datos_extraidos
    assert set(r.evidencia_por_campo.values()) == {"pagina_1"}  # en vision se descarta la seccion


def test_vision_qwen_foto_degradada():
    r = postprocesar_extraccion(parsear_extraccion(contenido("vision_qwen_extraccion_foto_degradada")),
                                esquema("pasaporte"), Modalidad.imagen, [1])
    assert r.datos_extraidos["fecha_vencimiento"] == "2031-07-25"
    assert r.datos_extraidos["nombre_completo"] == "ANA EJEMPLO PRUEBA"


@pytest.mark.parametrize("nombre", ["vision_qwen_extraccion_evidencia_invalida",
                                    "vision_qwen_extraccion_evidencia_sin_pagina"])
def test_evidencia_invalida_se_descarta(nombre):
    r = postprocesar_extraccion(parsear_extraccion(contenido(nombre)), esquema("pasaporte"), Modalidad.imagen, [1])
    assert r.evidencia_por_campo == {}
    assert r.datos_extraidos["numero_pasaporte"] == "X1234567P"


def test_fecha_ya_convertida_con_dia_y_mes_intercambiados_no_se_puede_detectar():
    # Limitacion conocida: por eso el prompt v2 pide las fechas tal como aparecen.
    r = postprocesar_extraccion(parsear_extraccion(contenido("vision_qwen_extraccion_evidencia_sin_pagina")),
                                esquema("pasaporte"), Modalidad.imagen, [1])
    assert r.datos_extraidos["fecha_expedicion"] == "2024-10-05"


def _respuesta(datos: dict, confianzas: dict | None = None, evidencias: dict | None = None):
    return parsear_extraccion(json.dumps({"datos_extraidos": datos, "nivel_confianza_por_campo": confianzas or {},
                                          "evidencia_por_campo": evidencias or {}}))


def test_fecha_no_normalizable_conserva_el_texto_con_confianza_cero():
    r = postprocesar_extraccion(_respuesta({"fecha_vencimiento": "mayo 2034"}, {"fecha_vencimiento": 0.9}),
                                esquema("pasaporte"), Modalidad.pdf_digital, [1])
    assert r.datos_extraidos["fecha_vencimiento"] == "mayo 2034"
    assert r.nivel_confianza_por_campo["fecha_vencimiento"] == 0.0


@pytest.mark.parametrize("valor, esperado, confianza", [
    ("2031", 2031, 0.9), (2031, 2031, 0.9), ("2021 - 2031", "2021 - 2031", 0.0), ("31", "31", 0.0),
])
def test_anio(valor, esperado, confianza):
    r = postprocesar_extraccion(_respuesta({"vigencia": valor}, {"vigencia": 0.9}),
                                esquema("credencial_elector"), Modalidad.pdf_digital, [1])
    assert r.datos_extraidos["vigencia"] == esperado
    assert r.nivel_confianza_por_campo["vigencia"] == confianza


@pytest.mark.parametrize("valor, esperado", [(1.5, 1.0), (-1, 0.0), ("0.7", 0.7), (None, 0.0), (True, 0.0), ("alta", 0.0)])
def test_confianza_se_limita_a_cero_uno(valor, esperado):
    r = postprocesar_extraccion(_respuesta({"sexo": "F"}, {"sexo": valor}), esquema("pasaporte"),
                                Modalidad.pdf_digital, [1])
    assert r.nivel_confianza_por_campo["sexo"] == esperado


def test_campos_nulos_o_ausentes_y_valores_no_texto():
    r = postprocesar_extraccion(_respuesta({"sexo": "  ", "numero_pasaporte": 123456789}, {"sexo": 0.9},
                                           {"sexo": "pagina_1"}), esquema("pasaporte"), Modalidad.pdf_digital, [1])
    assert r.datos_extraidos["sexo"] is None and r.nivel_confianza_por_campo["sexo"] == 0.0
    assert "sexo" not in r.evidencia_por_campo
    assert r.datos_extraidos["numero_pasaporte"] == "123456789"
    assert r.datos_extraidos["nombre_completo"] is None  # ausente en la respuesta
    assert set(r.datos_extraidos) == set(esquema("pasaporte"))


@pytest.mark.parametrize("vacio", ["", " ", "   ", "\t\n", "  "])
@pytest.mark.parametrize("tipo, campo", [("pasaporte", "nacionalidad"), ("pasaporte", "fecha_expedicion"),
                                         ("credencial_elector", "vigencia")])
def test_textos_vacios_o_solo_espacios_pasan_a_null(vacio, tipo, campo):
    # Acordado con PERSONA_3: asi VAL-001 (obligatorio) y VAL-004 (opcional) los ven como ausentes.
    r = postprocesar_extraccion(_respuesta({campo: vacio}, {campo: 0.9}, {campo: "pagina_1"}), esquema(tipo),
                                Modalidad.pdf_digital, [1])
    assert r.datos_extraidos[campo] is None
    assert r.nivel_confianza_por_campo[campo] == 0.0
    assert campo not in r.evidencia_por_campo


@pytest.mark.parametrize("evidencia, esperada", [
    ("pagina_2", "pagina_6"),              # relativa a las imagenes del lote -> pagina real
    ("pagina_6:seccion_central", "pagina_6"),
    ("pagina_9", None),
    ("pagina_0", None),
])
def test_evidencia_en_un_lote(evidencia, esperada):
    r = postprocesar_extraccion(_respuesta({"sexo": "F"}, {"sexo": 1}, {"sexo": evidencia}), esquema("pasaporte"),
                                Modalidad.pdf_escaneado, [5, 6, 7, 8])
    assert r.evidencia_por_campo.get("sexo") == esperada


# --- combinar_lotes ---

def test_combinar_lotes():
    lote1 = ResultadoExtraccion({"a": None, "b": "B1", "c": "C1", "d": "D1"}, {"a": 0, "b": 0.9, "c": 0.9, "d": 0.5},
                                {"b": "pagina_3", "c": "pagina_2"}, ["legible"])
    lote2 = ResultadoExtraccion({"a": "A2", "b": "B2", "c": "C2", "d": "D2"}, {"a": 0.8, "b": 0.9, "c": 0.9, "d": 0.6},
                                {"a": "pagina_5", "b": "pagina_1"}, ["legible", "sombra"])
    r = combinar_lotes([lote1, lote2])
    assert r.datos_extraidos == {"a": "A2", "b": "B2", "c": "C1", "d": "D1"}
    assert r.evidencia_por_campo == {"a": "pagina_5", "b": "pagina_1", "c": "pagina_2"}
    assert r.nivel_confianza_por_campo["d"] == 0.5  # sin evidencia en ningun lote: primer valor no nulo
    assert r.observaciones_visuales == ["legible", "sombra"]


# --- postprocesar_clasificacion ---

def test_clasificacion_respuestas_guardadas():
    r = postprocesar_clasificacion(parsear_clasificacion(contenido("texto_gemma4_clasificacion_pasaporte")), TIPOS)
    assert (r.tipo_documental_detectado, r.confianza) == ("pasaporte", 0.95)
    r = postprocesar_clasificacion(parsear_clasificacion(contenido("vision_gemma4_clasificacion_desconocido")), TIPOS)
    assert (r.tipo_documental_detectado, r.confianza) == (DESCONOCIDO, 0.1)


@pytest.mark.parametrize("tipo, esperado, confianza", [
    ("PASAPORTE", "pasaporte", 0.9), ("factura", DESCONOCIDO, 0.0), (" credencial_elector ", "credencial_elector", 0.9),
])
def test_clasificacion_tipos(tipo, esperado, confianza):
    r = postprocesar_clasificacion(parsear_clasificacion(json.dumps({"tipo_documental_detectado": tipo,
                                                                      "confianza": 0.9})), TIPOS)
    assert (r.tipo_documental_detectado, r.confianza) == (esperado, confianza)


# --- Imagenes, lotes y texto ---

def test_reducir_imagen():
    reducida = Image.open(io.BytesIO(reducir_imagen(png(2000, 1000))))
    assert reducida.size == (1000, 500)
    pequena = png(800, 600)
    assert reducir_imagen(pequena) is pequena


def test_lotes_de_paginas():
    paginas = [Pagina(i, imagen_png=b"x") for i in range(1, 10)] + [Pagina(10, texto="solo texto")]
    assert [[p.numero for p in lote] for lote in lotes_de_paginas(paginas)] == [[1, 2, 3, 4], [5, 6, 7, 8], [9]]
    assert lotes_de_paginas([Pagina(1, texto="t")]) == [[]]


def test_recortar_texto():
    paginas = [Pagina(1, "a" * 6), Pagina(2, "b" * 6), Pagina(3, "c" * 6), Pagina(4, None)]
    iguales, recortado = recortar_texto(paginas, 18)
    assert iguales == paginas and recortado is False
    salida, recortado = recortar_texto(paginas, 10)
    assert recortado is True
    assert [p.texto for p in salida] == ["a" * 6, f"bbbb\n{MARCA_RECORTE}", "", None]
    assert [p.numero for p in salida] == [1, 2, 3, 4]


def test_timeout_vision():
    assert timeout_vision(4) == 660 and timeout_vision(1) == 210 and timeout_vision(0) == 210


# --- Regla de texto suficiente y reintento con vision ---

def test_tiene_texto_suficiente():
    from app.modulos.motor_ia.proveedores.base import tiene_texto_suficiente
    suficiente = "X" * 30
    assert tiene_texto_suficiente([Pagina(1, suficiente), Pagina(2, " ".join(suficiente))])
    assert not tiene_texto_suficiente([Pagina(1, suficiente), Pagina(2, "X" * 29)])
    assert not tiene_texto_suficiente([Pagina(1, None)]) and not tiene_texto_suficiente([])


@pytest.mark.parametrize("vacios, reintento", [(0, False), (1, False), (2, True), (4, True)])
def test_necesita_reintento_vision_con_la_mitad_o_mas_de_obligatorios_vacios(vacios, reintento):
    from app.modulos.motor_ia.proveedores.base import necesita_reintento_vision, obligatorios_vacios
    obligatorios = ["nombre_completo", "numero_pasaporte", "fecha_nacimiento", "fecha_vencimiento"]
    datos = {c: (None if i < vacios else "valor") for i, c in enumerate(obligatorios)}
    resultado = ResultadoExtraccion({**datos, "sexo": None}, {}, {})
    assert obligatorios_vacios(resultado, esquema("pasaporte")) == (vacios, 4)
    assert necesita_reintento_vision(resultado, esquema("pasaporte")) is reintento


def test_combinar_texto_y_vision():
    from app.modulos.motor_ia.proveedores.base import combinar_texto_y_vision
    texto = ResultadoExtraccion({"a": "A-texto", "b": "B-texto", "c": None}, {"a": 0.9, "b": 0.8, "c": 0},
                                {"a": "pagina_1:detalle", "b": "pagina_1"}, ["texto"])
    vision = ResultadoExtraccion({"a": "A-vision", "b": None, "c": None}, {"a": 0.9, "b": 0, "c": 0},
                                 {"a": "pagina_1"}, ["vision"])
    r = combinar_texto_y_vision(texto, vision)
    assert r.datos_extraidos == {"a": "A-vision", "b": "B-texto", "c": None}
    assert r.evidencia_por_campo == {"a": "pagina_1", "b": "pagina_1"}
    assert r.nivel_confianza_por_campo["b"] == 0.8 and r.observaciones_visuales == ["vision", "texto"]


# --- Senal 4 de OCR pobre: formato invalido ---

@pytest.mark.parametrize("tipo, datos, invalidos", [
    ("pasaporte", {"numero_pasaporte": "X00000015UTO9001011F", "fecha_vencimiento": "2031-09-30"}, ["numero_pasaporte"]),
    ("pasaporte", {"numero_pasaporte": "ZX0000001", "fecha_vencimiento": "3009/2021"}, ["fecha_vencimiento"]),
    ("pasaporte", {"numero_pasaporte": "2X0000001", "fecha_vencimiento": "2031-09-30"}, []),  # cumple el patron
    ("credencial_elector", {"curp": "AEPA9O0101MDFXXX01", "vigencia": "2029"}, ["curp"]),
    ("credencial_elector", {"curp": "AEPA900101MDFXXX01", "vigencia": "2021 - 2029"}, ["vigencia"]),
    ("credencial_elector", {"curp": None, "vigencia": None}, []),                              # vacios: no son formato
])
def test_campos_con_formato_invalido(tipo, datos, invalidos):
    from app.modulos.motor_ia.proveedores.base import campos_con_formato_invalido
    r = postprocesar_extraccion(_respuesta(datos, {c: 0.9 for c in datos}), esquema(tipo), Modalidad.pdf_digital, [1])
    assert campos_con_formato_invalido(r, esquema(tipo)) == invalidos
