"""
CONTRATO 1 - JSON de resultado por documento.
Fuente de verdad para backend, frontend e integradores externos.
Cambios solo mediante ADR y aviso al equipo.
Nombres de campo: snake_case en espanol, identicos a la presentacion.
Ampliado por ADR-004 y ADR-006 (2026-09-30): campos nuevos opcionales o con valor por defecto.
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


class FaseAnalisis(str, Enum):  # ADR-014: en que va un analisis en curso (solo en memoria; nunca en BD)
    en_cola = "en_cola"            # esperando a que termine el anterior (un analisis cada vez)
    preparando = "preparando"
    ocr = "ocr"                    # OCR o capa de texto del PDF
    clasificando = "clasificando"
    vision = "vision"              # el modelo de vision lee las imagenes (lo mas lento en CPU)
    extrayendo = "extrayendo"


class EstadoGeneral(str, Enum):  # ADR-006, K
    en_revision = "en_revision"
    aprobado = "aprobado"    # folio cerrado (ADR-006, G)
    rechazado = "rechazado"  # folio cerrado (ADR-006, G)


class DecisionHumana(str, Enum):  # ADR-006, K: mismos valores que POST /folios/{folio}/decision
    aprobar = "aprobar"
    rechazar = "rechazar"


class Alerta(BaseModel):
    id: str | None = None  # ADR-006, 1.3: lo asigna la plataforma al guardar; el motor no lo rellena
    codigo: str = Field(..., examples=["ALR-001"])
    mensaje: str
    severidad: Severidad
    confianza: float = Field(..., ge=0, le=1)
    campo: str | None = None
    resuelta_por_revisor: bool = False
    # ADR-006, 2.2: resultado de la revision. aplica=None -> sin revisar; aplica=False -> falso positivo
    aplica: bool | None = None
    comentario_revisor: str | None = None
    resuelta_por: str | None = None      # usuario de la aplicacion
    resuelta_en: datetime | None = None


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


class Correccion(BaseModel):  # ADR-006, 2.4
    campo: str
    valor_anterior: Any = None
    valor_nuevo: Any = None
    usuario: str
    fecha: datetime


class Retirada(BaseModel):  # ADR-013: documento retirado del folio (no cuenta; nada se borra)
    en: datetime
    por: str
    motivo: str               # ya tapado (enmascarar_texto)


class ResultadoDocumento(BaseModel):
    folio_solicitud: str = Field(..., examples=["ONB-2026-000001"])
    identificador_unico_documento: str  # UUID
    tipo_documental_declarado: str | None
    tipo_documental_detectado: str | None
    tipo_documental_confirmado: str | None = None  # ADR-006, 2.5: lo fija el revisor
    confianza_clasificacion: float | None = Field(None, ge=0, le=1)  # la calcula el codigo, no el modelo (ADR-007)
    datos_extraidos: dict[str, Any] = {}  # con las correcciones ya aplicadas (ADR-006, 2.4)
    nivel_confianza_por_campo: dict[str, float] = {}  # la calcula el codigo, no el modelo (ADR-007); campo corregido -> 1.0
    evidencia_por_campo: dict[str, str] = {}  # "pagina_1", "pagina_2:seccion_superior", "correccion_revisor"
    reglas_cumplidas_e_incumplidas: Reglas = Reglas()
    alertas_encontradas: list[Alerta] = []
    correcciones: list[Correccion] = []  # ADR-006, 2.4
    recomendacion: Recomendacion | None = None
    estado_analisis: EstadoAnalisis = EstadoAnalisis.pendiente
    fecha_y_modelo_utilizado: FechaYModelo | None = None
    referencia_archivo_original: ReferenciaArchivoOriginal
    retirado: Retirada | None = None  # ADR-013: lo rellena la plataforma desde la BD; el motor no lo toca
    # ADR-014: solo con estado pendiente o procesando (None en completado y error). La rellena la plataforma
    # desde su registro en memoria; el motor no la devuelve
    fase_analisis: FaseAnalisis | None = None


class ComparacionCampo(BaseModel):
    campo: str
    coincide: bool
    valores: dict[str, Any]  # {identificador_unico_documento: valor}


class ResultadoExpediente(BaseModel):
    folio: str
    proceso: str
    referencia_externa: str | None = None   # ADR-004: id opaco del integrador, nunca el nombre
    fecha_solicitud: datetime | None = None # ADR-004: = folios.creado_en
    estado_general: EstadoGeneral  # ADR-006, K
    documentos: list[ResultadoDocumento]
    comparaciones: list[ComparacionCampo] = []
    alertas_expediente: list[Alerta] = []  # EXP-001 y CMP-001 (ADR-006, 2.3)
    recomendacion_global: Recomendacion | None = None
    decision_humana: DecisionHumana | None = None  # ADR-006, K
    # ADR-006, G: datos de la decision; tras ella el folio queda cerrado
    comentario_decision: str | None = None
    usuario_decision: str | None = None
    fecha_decision: datetime | None = None
    ruta_resumen_md: str | None = None


class ResumenFolio(BaseModel):  # ADR-006, 1.1: elemento de GET /folios
    folio: str
    proceso: str
    estado_general: EstadoGeneral
    recomendacion_global: Recomendacion | None = None
    n_documentos: int = 0
    n_bloqueantes_sin_resolver: int = 0
    fecha_solicitud: datetime | None = None  # = folios.creado_en (ADR-004)
    referencia_externa: str | None = None  # ADR-008; = folios.referencia_externa (id opaco, ADR-004)
