"""Recomendacion GLOBAL del expediente (logica pura, sin BD).

La recomendacion POR DOCUMENTO la da el motor de PERSONA_2 (`ResultadoDocumento.recomendacion`) y la
plataforma no la toca. La global se calcula al vuelo y nunca se guarda.

Nunca devuelve `rechazar`: la IA recomienda y la decision final del expediente es humana (regla 9 de
CLAUDE.md). Como mucho pide `revision_manual`.
"""
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.schemas.resultado import Alerta, EstadoAnalisis, Recomendacion, Severidad

_SEVERIDADES_QUE_FRENAN = {Severidad.critica, Severidad.bloqueante}


@dataclass
class DocumentoParaRecomendar:
    estado: EstadoAnalisis
    tipo: str | None  # tipo efectivo: confirmado > detectado > declarado
    confianza_clasificacion: float | None = None
    confianza_por_campo: dict[str, float] = field(default_factory=dict)


def _confianzas_suficientes(doc: DocumentoParaRecomendar, ficha: dict) -> bool:
    minima_clasificacion = ficha.get("confianza_minima_clasificacion") or 0.0
    minima_campo = ficha.get("confianza_minima_campo") or 0.0
    if doc.confianza_clasificacion is None or doc.confianza_clasificacion < minima_clasificacion:
        return False
    # Un campo corregido por el revisor vale 1.0 (ADR-006 2.4): siempre pasa
    return all(confianza >= minima_campo for confianza in doc.confianza_por_campo.values())


def calcular_recomendacion_global(documentos: list[DocumentoParaRecomendar], alertas: Iterable[Alerta],
                                  fichas: dict[str, dict]) -> Recomendacion:
    """Reglas en orden; la primera que se cumple pide `revision_manual`. Si ninguna, `aprobar`.

    a) Sin documentos, o alguno `pendiente`, `procesando` o `error`.
    b) Alguna alerta critica o bloqueante con `aplica` distinto de False (NULL = sin revisar, True =
       confirmada). Decision del usuario: una critica o bloqueante marcada `aplica=False` (falso
       positivo) no cuenta. Las preventivas e informativas no cuentan nunca.
    c) Algun documento sin ficha para su tipo efectivo, sin `confianza_clasificacion`, o con ella o con
       algun campo por debajo de los minimos de la ficha (ADR-007: confianzas calculadas por el codigo).
    """
    if not documentos or any(d.estado != EstadoAnalisis.completado for d in documentos):
        return Recomendacion.revision_manual
    if any(a.severidad in _SEVERIDADES_QUE_FRENAN and a.aplica is not False for a in alertas):
        return Recomendacion.revision_manual
    for doc in documentos:
        ficha = fichas.get(doc.tipo) if doc.tipo else None
        if ficha is None or not _confianzas_suficientes(doc, ficha):
            return Recomendacion.revision_manual
    return Recomendacion.aprobar
