"""
CONTRATO 3 - Interfaz interna del motor de IA y del orquestador.
Cambiar de proveedor NO debe alterar el flujo: todo proveedor implementa ProveedorLLM.
Cambios solo mediante ADR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class Tarea(str, Enum):
    clasificacion = "clasificacion"
    extraccion = "extraccion"
    validacion = "validacion"


class Modalidad(str, Enum):
    pdf_digital = "pdf_digital"
    pdf_escaneado = "pdf_escaneado"
    imagen = "imagen"


@dataclass
class Pagina:
    numero: int                      # 1-based
    texto: str | None = None         # texto extraido (digital u OCR)
    imagen_png: bytes | None = None  # render de la pagina para modelos de vision


@dataclass
class DocumentoPreparado:
    """Salida del orquestador: entrada comun para todas las tareas de IA."""
    identificador_unico_documento: str
    modalidad: Modalidad
    paginas: list[Pagina]
    tipo_documental_declarado: str | None = None
    contexto_rag: list[str] = field(default_factory=list)  # fragmentos de la base de conocimiento


@dataclass
class ResultadoClasificacion:
    tipo_documental_detectado: str
    confianza: float
    razonamiento: str = ""


@dataclass
class ResultadoExtraccion:
    datos_extraidos: dict[str, Any]
    nivel_confianza_por_campo: dict[str, float]
    evidencia_por_campo: dict[str, str]
    observaciones_visuales: list[str] = field(default_factory=list)  # calidad, recortes, alteraciones (extra)


class ProveedorLLM(Protocol):
    nombre: str
    modelo: str
    soporta_vision: bool

    def clasificar(self, doc: DocumentoPreparado, tipos_posibles: list[str], prompt: str) -> ResultadoClasificacion: ...

    def extraer(self, doc: DocumentoPreparado, esquema_campos: dict[str, Any], prompt: str) -> ResultadoExtraccion: ...


class Enrutador(Protocol):
    """Lee config/modelos.yaml y devuelve el proveedor para una tarea y tipo documental."""

    def obtener(self, tarea: Tarea, tipo_documental: str | None = None) -> ProveedorLLM: ...

    def respaldo(self, tarea: Tarea, tipo_documental: str | None = None) -> ProveedorLLM | None: ...
