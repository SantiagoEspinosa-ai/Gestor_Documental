"""Comparacion de campos entre los documentos de un folio (logica pura, sin BD).

Que se compara: `comparaciones` de las fichas YAML (`credencial_elector: {pasaporte: [nombre_completo]}`),
uniendo los dos sentidos. Para comparar se normaliza: mayusculas, sin acentos, espacios colapsados;
los campos de tipo `fecha` se comparan como fecha si se pueden leer. Los valores vacios no participan.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.schemas.resultado import ComparacionCampo

_FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


@dataclass
class DocumentoComparable:
    id: str
    tipo: str | None  # tipo efectivo: confirmado > detectado > declarado
    datos: dict[str, Any] = field(default_factory=dict)


def normalizar_texto(valor: Any) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos).strip().upper()


def _normalizar_fecha(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    for formato in _FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return normalizar_texto(valor)  # ilegible como fecha: se compara como texto


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _relaciones(fichas: dict[str, dict]) -> dict[str, set[frozenset[str]]]:
    """campo -> pares de tipos que lo comparan (sin sentido: A-B es lo mismo que B-A)."""
    relaciones: dict[str, set[frozenset[str]]] = {}
    for tipo, ficha in fichas.items():
        for otro, campos in (ficha.get("comparaciones") or {}).items():
            for campo in campos or []:
                relaciones.setdefault(campo, set()).add(frozenset((tipo, otro)))
    return relaciones


def _tipo_campo(fichas: dict[str, dict], tipo: str, campo: str) -> str | None:
    return ((fichas.get(tipo) or {}).get("campos") or {}).get(campo, {}).get("tipo")


def comparar(documentos: list[DocumentoComparable], fichas: dict[str, dict]) -> list[ComparacionCampo]:
    """Un ComparacionCampo por campo con al menos 2 valores en tipos relacionados, ordenado por campo."""
    comparaciones = []
    for campo, pares in sorted(_relaciones(fichas).items()):
        con_valor = [d for d in documentos if d.tipo and not _vacio(d.datos.get(campo))]
        tipos_con_valor = {d.tipo for d in con_valor}
        # Participan los tipos de un par cuyos dos lados tienen valor (o el mismo tipo dos veces)
        tipos = {t for par in pares if par <= tipos_con_valor for t in par}
        participantes = [d for d in con_valor if d.tipo in tipos]
        if len(participantes) < 2:
            continue
        normalizados = {
            (_normalizar_fecha(d.datos[campo]) if _tipo_campo(fichas, d.tipo, campo) == "fecha"
             else normalizar_texto(d.datos[campo]))
            for d in participantes
        }
        comparaciones.append(ComparacionCampo(
            campo=campo, coincide=len(normalizados) == 1,
            valores={d.id: d.datos[campo] for d in participantes}))
    return comparaciones
