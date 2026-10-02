"""
Recomendacion POR DOCUMENTO (PERSONA_2), segun docs/contratos/codigos_alertas.md. Funcion pura.
Nunca recomienda `rechazar` (D1, aceptado en el PR #13): la IA recomienda y la decision es humana (regla 9).
La recomendacion GLOBAL del expediente es de PERSONA_1 (`expediente/recomendacion.py`) y sigue las mismas reglas.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modulos.configuracion.servicio import TipoDocumental
from app.modulos.validacion.reglas import _ficha, _vacio
from app.schemas.resultado import EstadoAnalisis, Recomendacion, ResultadoDocumento, Severidad

_FRENAN = {Severidad.critica, Severidad.bloqueante}


def recomendar_documento(resultado: ResultadoDocumento,
                         ficha: TipoDocumental | Mapping[str, Any] | None) -> Recomendacion:
    """`aprobar` si el analisis esta `completado`, no hay alertas criticas ni bloqueantes (salvo las marcadas
    como falso positivo, `aplica=False`) y las confianzas estan sobre el minimo de la ficha: la de clasificacion
    y la de cada campo con valor (los vacios ya llevan VAL-001/VAL-004). Si no, `revision_manual`.
    `ficha`: la del tipo con el que se extrajo; sin ficha (p. ej. `desconocido` sin tipo declarado), revision."""
    if resultado.estado_analisis is not EstadoAnalisis.completado or ficha is None:
        return Recomendacion.revision_manual
    ficha = _ficha(ficha)
    if any(a.severidad in _FRENAN and a.aplica is not False for a in resultado.alertas_encontradas):
        return Recomendacion.revision_manual
    clasificacion = resultado.confianza_clasificacion
    if clasificacion is None or clasificacion < ficha.confianza_minima_clasificacion:
        return Recomendacion.revision_manual
    for campo in ficha.campos:
        if not _vacio(resultado.datos_extraidos.get(campo)) and \
                float(resultado.nivel_confianza_por_campo.get(campo) or 0.0) < ficha.confianza_minima_campo:
            return Recomendacion.revision_manual
    return Recomendacion.aprobar
