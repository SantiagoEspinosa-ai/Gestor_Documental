"""
API publica del modulo rag (ADR-005): lo unico que importan los demas modulos.
Memoria de folios (H14, ADR-010 C4): `indexar_resumen` y `fragmento_resumen`. Sin embeddings (spec, seccion 16).
"""
from app.modulos.rag.memoria import LIMITE_FRAGMENTO, fragmento_resumen, indexar_resumen

__all__ = ["LIMITE_FRAGMENTO", "fragmento_resumen", "indexar_resumen"]
