"""
Reglas deterministas de un documento (PERSONA_2): VAL-001, VAL-002, VAL-004 y REG-{id} de la ficha.
Funcion pura, sin BD, S3 ni modelo: la usan `orquestador.procesar_documento` y la plataforma tras cada
correccion (D3). Firma acordada con PERSONA_1: docs/motor_ia/SPEC_CONFIGURACION.md, seccion 11.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError

from app.modulos.configuracion.servicio import ErrorConfiguracion, Regla, TipoDocumental, TipoRegla
from app.schemas.resultado import Alerta, Reglas, Severidad

CONFIANZA_ALERTA = 1.0  # alertas deterministas
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURP = re.compile(r"^[A-Z]{4}(\d{2})(\d{2})(\d{2})[HM][A-Z]{5}([A-Z0-9])\d$")


def evaluar_reglas(datos_extraidos: Mapping[str, Any], confianzas: Mapping[str, float],
                   ficha: TipoDocumental | Mapping[str, Any], *, hoy: date) -> tuple[list[Alerta], Reglas]:
    """VAL-001 (obligatorio vacio), VAL-004 (opcional vacio), VAL-002 (con valor y confianza < minimo) y
    REG-{id} (regla incumplida). Una regla sobre un campo vacio no se evalua ni se lista (D8), salvo las de
    tipo `obligatorio`. Cada regla se evalua tal cual esta escrita (D9). Un valor que no tiene el formato del
    campo (fecha no ISO, anio no entero) incumple sus reglas, sin fallar."""
    ficha = _ficha(ficha)
    alertas: list[Alerta] = []

    def alerta(codigo: str, severidad: Severidad, mensaje: str, campo: str) -> None:
        if not any(a.codigo == codigo and a.campo == campo for a in alertas):  # ADR-006, 1.3
            alertas.append(Alerta(codigo=codigo, mensaje=mensaje, severidad=severidad,
                                  confianza=CONFIANZA_ALERTA, campo=campo))

    for nombre, campo in ficha.campos.items():
        if _vacio(datos_extraidos.get(nombre)):
            if campo.obligatorio:
                alerta("VAL-001", Severidad.critica, f"Falta el campo obligatorio '{nombre}'", nombre)
            else:
                alerta("VAL-004", Severidad.informativa, f"El campo opcional '{nombre}' esta vacio", nombre)
        elif (confianza := float(confianzas.get(nombre) or 0.0)) < ficha.confianza_minima_campo:
            alerta("VAL-002", Severidad.preventiva,
                   f"Confianza del campo '{nombre}' ({confianza:.2f}) menor que el minimo "
                   f"({ficha.confianza_minima_campo:.2f})", nombre)

    reglas = Reglas()
    for regla in ficha.reglas:
        cumple = _evaluar(regla, datos_extraidos, confianzas, ficha, hoy)
        if cumple is None:
            continue
        if cumple:
            reglas.cumplidas.append(regla.id)
        else:
            reglas.incumplidas.append(regla.id)
            alerta(f"REG-{regla.id}", regla.severidad, regla.mensaje, regla.campo)
    return alertas, reglas


def _ficha(ficha: TipoDocumental | Mapping[str, Any]) -> TipoDocumental:
    if isinstance(ficha, TipoDocumental):
        return ficha
    try:
        return TipoDocumental.model_validate(dict(ficha))
    except ValidationError as e:
        raise ErrorConfiguracion([f"ficha invalida: {err['msg']}" for err in e.errors()]) from e


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _fecha(valor: Any) -> date | None:
    if not isinstance(valor, str) or not _ISO.match(valor):
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _anio(valor: Any) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and re.fullmatch(r"\d{4}", valor.strip()):
        return int(valor)
    return None


def _evaluar(regla: Regla, datos: Mapping[str, Any], confianzas: Mapping[str, float], ficha: TipoDocumental,
             hoy: date) -> bool | None:
    """True cumplida, False incumplida, None no evaluable (campo vacio, D8)."""
    valor = datos.get(regla.campo)
    if regla.tipo is TipoRegla.obligatorio:
        return not _vacio(valor)
    if _vacio(valor):
        return None
    if regla.tipo is TipoRegla.patron:
        return isinstance(valor, str) and re.fullmatch(ficha.campos[regla.campo].patron, valor) is not None
    if regla.tipo is TipoRegla.confianza_minima:
        return float(confianzas.get(regla.campo) or 0.0) >= ficha.confianza_minima_campo
    if regla.tipo is TipoRegla.anio_mayor_o_igual_actual:
        anio = _anio(valor)
        return anio is not None and anio >= hoy.year
    if regla.tipo in (TipoRegla.fecha_posterior_a_hoy, TipoRegla.fecha_posterior_a_hoy_mas_dias,
                      TipoRegla.fecha_no_anterior_a_hoy_menos_dias):
        fecha = _fecha(valor)
        if fecha is None:
            return False  # fecha no normalizable: incumple, sin fallar (lleva ademas VAL-002 con confianza 0)
        if regla.tipo is TipoRegla.fecha_posterior_a_hoy:
            return fecha > hoy
        if regla.tipo is TipoRegla.fecha_posterior_a_hoy_mas_dias:
            return fecha > hoy + timedelta(days=regla.dias)
        return fecha >= hoy - timedelta(days=regla.dias)
    # Coherencia entre dos campos: si alguno esta vacio o no tiene el formato esperado, no se evalua (ya
    # tienen sus propias alertas: VAL-00x, REG de patron o de fecha).
    relacionado = datos.get(regla.campo_relacionado)
    if regla.tipo is TipoRegla.curp_coincide_con_fecha:
        m = _CURP.match(valor) if isinstance(valor, str) else None
        fecha = _fecha(relacionado)
        if m is None or fecha is None:
            return None
        aa, mm, dd, siglo = m.groups()
        # posicion 17 de la CURP: digito si nacio antes de 2000, letra si nacio despues
        return (aa, mm, dd) == (f"{fecha.year % 100:02d}", f"{fecha.month:02d}", f"{fecha.day:02d}") and (
            siglo.isdigit() == (fecha.year < 2000))
    if regla.tipo is TipoRegla.fecha_anterior_a_campo:
        antes, despues = _fecha(valor), _fecha(relacionado)
        if antes is None or despues is None:
            return None
        return antes < despues
    raise ValueError(f"tipo de regla sin evaluador: {regla.tipo.value}")  # nuevo en el cargador y no aqui
