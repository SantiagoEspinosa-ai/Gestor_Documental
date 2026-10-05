"""
API publica del modulo orquestador: lo unico que importan los demas modulos (ADR-005).
"""
from app.modulos.orquestador.modalidad import FormatoNoSoportado, detectar
from app.modulos.orquestador.mrz import Mrz, buscar_mrz, validar_digitos
from app.modulos.orquestador.preparador import preparar
from app.modulos.orquestador.procesamiento import procesar_documento

__all__ = ["FormatoNoSoportado", "Mrz", "buscar_mrz", "detectar", "preparar", "procesar_documento", "validar_digitos"]
