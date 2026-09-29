"""
CONTRATO 1 - JSON de resultado por documento.
Fuente de verdad para backend, frontend e integradores externos.
Cambios solo mediante ADR y aviso al equipo.
Nombres de campo: snake_case en espanol, identicos a la presentacion.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severidad(str, Enum):
    informativa = "informativa"
    preventiva = "preventiva"
    critica = "critica"
    bloqueante = "bloqueante"  # impide la aprobacion


class Recomendacion(str, Enum):
    aprobar = "aprobar"
    revision_manual = "revision_manual"
    rechazar = "rechazar"


class EstadoAnalisis(str, Enum):
    pendiente = "pendiente"
    procesando = "procesando"
    completado = "completado"
    error = "error"


class Alerta(BaseModel):
    codigo: str = Field(..., examples=["ALR-001"])
    mensaje: str
    severidad: Severidad
    confianza: float = Field(..., ge=0, le=1)
    campo: str | None = None
    resuelta_por_revisor: bool = False


class Reglas(BaseModel):
    cumplidas: list[str] = []
    incumplidas: list[str] = []


class FechaYModelo(BaseModel):
    fecha_analisis: datetime  # ISO 8601
    proveedor: str            # p. ej. "ollama"
    modelo: str               # p. ej. "llama3.2-vision:11b"
    version_prompt: str       # p. ej. "extraccion_pasaporte@v1"


class ReferenciaArchivoOriginal(BaseModel):
    nombre_archivo: str
    ruta: str                 # clave en S3
    hash: str                 # SHA-256


class ResultadoDocumento(BaseModel):
    folio_solicitud: str = Field(..., examples=["ONB-2026-000001"])
    identificador_unico_documento: str  # UUID
    tipo_documental_declarado: str | None
    tipo_documental_detectado: str | None
    confianza_clasificacion: float | None = Field(None, ge=0, le=1)
    datos_extraidos: dict[str, Any] = {}
    nivel_confianza_por_campo: dict[str, float] = {}
    evidencia_por_campo: dict[str, str] = {}  # "pagina_1", "pagina_2:seccion_superior"
    reglas_cumplidas_e_incumplidas: Reglas = Reglas()
    alertas_encontradas: list[Alerta] = []
    recomendacion: Recomendacion | None = None
    estado_analisis: EstadoAnalisis = EstadoAnalisis.pendiente
    fecha_y_modelo_utilizado: FechaYModelo | None = None
    referencia_archivo_original: ReferenciaArchivoOriginal


class ComparacionCampo(BaseModel):
    campo: str
    coincide: bool
    valores: dict[str, Any]  # {identificador_unico_documento: valor}


class ResultadoExpediente(BaseModel):
    folio: str
    proceso: str
    estado_general: str  # en_revision | aprobado | rechazado
    documentos: list[ResultadoDocumento]
    comparaciones: list[ComparacionCampo] = []
    alertas_expediente: list[Alerta] = []
    recomendacion_global: Recomendacion | None = None
    decision_humana: str | None = None
    ruta_resumen_md: str | None = None
