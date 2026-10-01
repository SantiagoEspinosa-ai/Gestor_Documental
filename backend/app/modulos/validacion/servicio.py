"""API publica del modulo validacion (ADR-005: los demas modulos solo importan este fichero).

Modulo compartido: PERSONA_1 aporta las comparaciones entre documentos (`comparaciones.py`) y
PERSONA_2 las reglas del documento (`reglas.py`). Este servicio lo amplian los dos.
"""
from app.modulos.validacion.comparaciones import DocumentoComparable
from app.modulos.validacion.comparaciones import comparar as _comparar
from app.schemas.resultado import ComparacionCampo

__all__ = ["DocumentoComparable", "comparar"]


def comparar(documentos: list[DocumentoComparable], fichas: list[dict] | dict[str, dict]) -> list[ComparacionCampo]:
    """Compara los campos que piden las fichas entre los documentos del folio.

    `documentos`: los del folio en estado `completado`, con su tipo efectivo y sus `datos_extraidos`.
    `fichas`: las fichas de tipos documentales (lista con `nombre`, o diccionario por nombre).
    """
    por_nombre = fichas if isinstance(fichas, dict) else {f["nombre"]: f for f in fichas}
    return _comparar(documentos, por_nombre)
