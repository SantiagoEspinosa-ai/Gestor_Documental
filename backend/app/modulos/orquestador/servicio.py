"""
API publica del modulo orquestador: lo unico que importan los demas modulos (ADR-005).
"""
from app.modulos.orquestador.modalidad import FormatoNoSoportado, detectar
from app.modulos.orquestador.preparador import preparar

__all__ = ["FormatoNoSoportado", "detectar", "preparar"]
