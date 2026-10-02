"""Tests de validacion.evaluar_reglas (reglas.py, PERSONA_2). Pura: sin BD, S3 ni modelo. Datos ficticios."""
from datetime import date

import pytest

from app.modulos.configuracion.servicio import ErrorConfiguracion, TipoDocumental
from app.modulos.validacion import servicio as validacion
from app.schemas.resultado import Reglas

HOY = date(2026, 9, 30)


def regla(id, tipo, campo, severidad="critica", **extra):
    return {"id": id, "tipo": tipo, "campo": campo, "severidad": severidad, "mensaje": f"Mensaje {id}", **extra}


FICHA = {
    "nombre": "tipo_prueba", "nombre_visible": "Tipo de prueba", "categoria": "identificacion",
    "descripcion": "Ficha ficticia para los tests", "caracteristicas_esperadas": ["Titulo"],
    "formatos_permitidos": ["pdf"],
    "campos": {
        "nombre_completo": {"tipo": "texto", "obligatorio": True},
        "curp": {"tipo": "texto", "obligatorio": True, "patron": "^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[A-Z0-9][0-9]$"},
        "fecha_nacimiento": {"tipo": "fecha", "obligatorio": True},
        "fecha_expedicion": {"tipo": "fecha", "obligatorio": False},
        "fecha_vencimiento": {"tipo": "fecha", "obligatorio": True},
        "fecha_emision": {"tipo": "fecha", "obligatorio": False},
        "vigencia": {"tipo": "anio", "obligatorio": False},
        "sexo": {"tipo": "texto", "obligatorio": False},
    },
    "confianza_minima_clasificacion": 0.85,
    "confianza_minima_campo": 0.80,
    "reglas": [
        regla("vigencia_documento", "fecha_posterior_a_hoy", "fecha_vencimiento", "bloqueante"),
        regla("vigencia_proxima", "fecha_posterior_a_hoy_mas_dias", "fecha_vencimiento", "preventiva", dias=90),
        regla("antiguedad_maxima", "fecha_no_anterior_a_hoy_menos_dias", "fecha_emision", dias=90),
        regla("vigencia_anio", "anio_mayor_o_igual_actual", "vigencia", "bloqueante"),
        regla("formato_curp", "patron", "curp"),
        regla("curp_coincide_nacimiento", "curp_coincide_con_fecha", "curp", campo_relacionado="fecha_nacimiento"),
        regla("nacimiento_antes_de_expedicion", "fecha_anterior_a_campo", "fecha_nacimiento",
              campo_relacionado="fecha_expedicion"),
        regla("sexo_obligatorio", "obligatorio", "sexo", "preventiva"),
        regla("sexo_verificado", "confianza_minima", "sexo", "preventiva"),
    ],
}
DATOS = {"nombre_completo": "ANA EJEMPLO PRUEBA", "curp": "AEPA900101MDFXXX01", "fecha_nacimiento": "1990-01-01",
         "fecha_expedicion": "2021-09-30", "fecha_vencimiento": "2031-09-30", "fecha_emision": "2026-09-15",
         "vigencia": 2029, "sexo": "F"}
CONFIANZAS = dict.fromkeys(DATOS, 1.0)


def evaluar(datos=None, confianzas=None, ficha=None, hoy=HOY):
    return validacion.evaluar_reglas(DATOS if datos is None else datos,
                                     CONFIANZAS if confianzas is None else confianzas,
                                     FICHA if ficha is None else ficha, hoy=hoy)


def codigos(alertas):
    return [(a.codigo, a.severidad.value, a.campo) for a in alertas]


def test_todo_correcto_sin_alertas_y_todas_las_reglas_cumplidas():
    alertas, reglas = evaluar()
    assert alertas == []
    assert reglas == Reglas(cumplidas=[r["id"] for r in FICHA["reglas"]], incumplidas=[])


def test_acepta_la_ficha_como_tipo_documental_o_como_dict():
    assert evaluar(ficha=TipoDocumental.model_validate(FICHA)) == evaluar(ficha=FICHA)


def test_ficha_invalida_es_error_de_configuracion():
    with pytest.raises(ErrorConfiguracion):
        evaluar(ficha={**FICHA, "campos": {}})


# --- VAL-001, VAL-002, VAL-004 ---

def test_obligatorio_vacio_val_001_y_opcional_vacio_val_004():
    datos = {**DATOS, "nombre_completo": None, "fecha_expedicion": "   "}
    alertas, _ = evaluar(datos)
    assert ("VAL-001", "critica", "nombre_completo") in codigos(alertas)
    assert ("VAL-004", "informativa", "fecha_expedicion") in codigos(alertas)


def test_campo_ausente_cuenta_como_vacio():
    datos = {k: v for k, v in DATOS.items() if k != "curp"}
    alertas, _ = evaluar(datos)
    assert ("VAL-001", "critica", "curp") in codigos(alertas)


def test_val_002_solo_en_campos_con_valor():
    confianzas = {**CONFIANZAS, "nombre_completo": 0.79, "sexo": 0.8}
    alertas, _ = evaluar(confianzas=confianzas)
    assert codigos(alertas) == [("VAL-002", "preventiva", "nombre_completo")]  # 0,80 no es menor que el minimo
    alertas, _ = evaluar({**DATOS, "nombre_completo": None}, {**CONFIANZAS, "nombre_completo": 0.0})
    assert [c for c in codigos(alertas) if c[2] == "nombre_completo"] == [("VAL-001", "critica", "nombre_completo")]


def test_campo_sin_confianza_cuenta_como_0():
    alertas, _ = evaluar(confianzas={k: v for k, v in CONFIANZAS.items() if k != "sexo"})
    assert ("VAL-002", "preventiva", "sexo") in codigos(alertas)


def test_campo_corregido_con_confianza_1_no_lleva_val_002():
    alertas, _ = evaluar({**DATOS, "sexo": "M"}, {**CONFIANZAS, "sexo": 1.0})
    assert alertas == []


def test_solo_emite_val_001_002_004_y_reg():
    datos = {**DATOS, "nombre_completo": None, "fecha_expedicion": None, "fecha_vencimiento": "2026-09-01",
             "curp": "AEPA9O0101MDFXXX01"}
    alertas, _ = evaluar(datos, dict.fromkeys(DATOS, 0.5))
    assert {a.codigo.split("-")[0] for a in alertas} <= {"VAL", "REG"}
    assert not {a.codigo for a in alertas} & {"VAL-003"}
    assert all(a.confianza == 1.0 and a.id is None and a.aplica is None and a.campo for a in alertas)


def test_orden_val_por_campos_y_despues_reg_por_reglas():
    datos = {**DATOS, "nombre_completo": None, "fecha_vencimiento": "2026-09-01"}
    alertas, _ = evaluar(datos)
    assert [a.codigo for a in alertas] == ["VAL-001", "REG-vigencia_documento", "REG-vigencia_proxima"]


# --- Tipos de regla ---

@pytest.mark.parametrize("vencimiento, documento, proxima", [
    ("2026-10-01", True, False),     # manana: vigente, pero vence en menos de 90 dias
    ("2026-09-30", False, False),    # hoy: ya no es posterior a hoy
    ("2026-12-29", True, False),     # hoy + 90: no es posterior a hoy + 90
    ("2026-12-30", True, True),
])
def test_fechas_posteriores_a_hoy_en_la_frontera(vencimiento, documento, proxima):
    _, reglas = evaluar({**DATOS, "fecha_vencimiento": vencimiento})
    assert ("vigencia_documento" in reglas.cumplidas, "vigencia_proxima" in reglas.cumplidas) == (documento, proxima)


def test_pasaporte_vencido_incumple_las_dos_reglas_de_vigencia_d9():
    alertas, reglas = evaluar({**DATOS, "fecha_vencimiento": "2025-01-01"})
    assert {"vigencia_documento", "vigencia_proxima"} <= set(reglas.incumplidas)
    assert [(a.codigo, a.severidad.value, a.mensaje) for a in alertas] == [
        ("REG-vigencia_documento", "bloqueante", "Mensaje vigencia_documento"),
        ("REG-vigencia_proxima", "preventiva", "Mensaje vigencia_proxima")]


@pytest.mark.parametrize("emision, cumple", [("2026-07-02", True), ("2026-07-01", False)])  # hoy - 90 = 2026-07-02
def test_antiguedad_maxima_en_la_frontera(emision, cumple):
    _, reglas = evaluar({**DATOS, "fecha_emision": emision})
    assert ("antiguedad_maxima" in reglas.cumplidas) is cumple


@pytest.mark.parametrize("vigencia, cumple", [(2026, True), (2025, False), ("2027", True), ("2021 - 2029", False)])
def test_anio_mayor_o_igual_actual(vigencia, cumple):
    _, reglas = evaluar({**DATOS, "vigencia": vigencia})
    assert ("vigencia_anio" in reglas.cumplidas) is cumple


def test_patron():
    _, reglas = evaluar({**DATOS, "curp": "AEPA9O0101MDFXXX01"})  # O en lugar de 0
    assert "formato_curp" in reglas.incumplidas


def test_obligatorio_y_confianza_minima_como_reglas():
    alertas, reglas = evaluar({**DATOS, "sexo": None})
    assert "sexo_obligatorio" in reglas.incumplidas and "sexo_verificado" not in reglas.cumplidas + reglas.incumplidas
    _, reglas = evaluar(confianzas={**CONFIANZAS, "sexo": 0.5})
    assert "sexo_verificado" in reglas.incumplidas


def test_regla_sobre_campo_vacio_no_se_evalua_ni_se_lista_d8():
    _, reglas = evaluar({**DATOS, "fecha_emision": None, "vigencia": None})
    listadas = reglas.cumplidas + reglas.incumplidas
    assert "antiguedad_maxima" not in listadas and "vigencia_anio" not in listadas


def test_fecha_no_normalizable_incumple_sus_reglas_sin_fallar():
    alertas, reglas = evaluar({**DATOS, "fecha_vencimiento": "mayo 2034"}, {**CONFIANZAS, "fecha_vencimiento": 0.0})
    assert {"vigencia_documento", "vigencia_proxima"} <= set(reglas.incumplidas)
    assert ("VAL-002", "preventiva", "fecha_vencimiento") in codigos(alertas)


# --- Coherencia ---

@pytest.mark.parametrize("curp, nacimiento, cumple", [
    ("AEPA900101MDFXXX01", "1990-01-01", True),
    ("AEPA000101MDFXXX01", "1990-01-01", False),   # fallo real del bloque 3 (extremo)
    ("AEPA000101MDFXXXA1", "2000-01-01", True),    # nacida en 2000: posicion 17 es letra
    ("AEPA000101MDFXXX01", "2000-01-01", False),   # mismo AAMMDD pero siglo equivocado
])
def test_curp_coincide_con_la_fecha_de_nacimiento(curp, nacimiento, cumple):
    _, reglas = evaluar({**DATOS, "curp": curp, "fecha_nacimiento": nacimiento})
    assert ("curp_coincide_nacimiento" in reglas.cumplidas) is cumple


def test_coherencia_no_se_evalua_si_un_campo_no_tiene_formato():
    _, reglas = evaluar({**DATOS, "curp": "AEPA9O0101MDFXXX01"})
    assert "curp_coincide_nacimiento" not in reglas.cumplidas + reglas.incumplidas
    _, reglas = evaluar({**DATOS, "fecha_expedicion": None})
    assert "nacimiento_antes_de_expedicion" not in reglas.cumplidas + reglas.incumplidas


def test_fecha_anterior_a_campo():
    alertas, reglas = evaluar({**DATOS, "fecha_nacimiento": "2021-09-30"})  # fallo real del bloque 3 (dificil)
    assert "nacimiento_antes_de_expedicion" in reglas.incumplidas
    assert ("REG-nacimiento_antes_de_expedicion", "critica", "fecha_nacimiento") in codigos(alertas)


def test_es_pura_y_reproducible():
    assert evaluar() == evaluar()
    datos = dict(DATOS)
    evaluar(datos)
    assert datos == DATOS
