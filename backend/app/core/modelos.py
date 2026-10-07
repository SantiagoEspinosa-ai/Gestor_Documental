"""Modelos de BD (SQLAlchemy 2) de la plataforma.

Tablas del prompt de PERSONA_1 con los cambios de ADR-004 (referencia y fecha del expediente),
ADR-006 bloques 1 y 2 (alertas con id y revision, alertas de expediente, tipo confirmado,
resultados versionados) y ADR-006 G (decision del folio).

Los valores permitidos se aplican con CHECK sobre columnas String, no con Enum nativo de Postgres.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint, Uuid, false, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.schemas.resultado import DecisionHumana, EstadoAnalisis, EstadoGeneral, Severidad

# JSONB en PostgreSQL, JSON en el resto (SQLite en los tests)
Json = JSON().with_variant(JSONB(), "postgresql")

ROLES = ("admin", "revisor", "integrador")
ESTADOS_FOLIO = tuple(e.value for e in EstadoGeneral)
DECISIONES = tuple(e.value for e in DecisionHumana)

# ADR-006 1.5, ADR-010 A4 (dato_revelado) y original_visto (post-MVP). Sin CHECK en BD: anadir una accion no necesita migracion
ACCIONES_AUDITORIA = (
    "login", "folio_creado", "documento_subido", "documento_procesado", "dato_corregido",
    "clasificacion_confirmada", "alerta_resuelta", "decision_tomada", "dato_revelado",
    "original_visto",
)


def _en(columna: str, valores) -> str:
    """Condicion SQL `columna IN (...)` a partir de una tupla o de un Enum."""
    if isinstance(valores, type) and issubclass(valores, Enum):
        valores = [e.value for e in valores]
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


def _creado_en() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint(_en("rol", ROLES), name="ck_usuarios_rol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(100), unique=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    creado_en: Mapped[datetime] = _creado_en()


class Proceso(Base):
    """Se rellena desde config/procesos.yaml al arrancar (tarea 4)."""
    __tablename__ = "procesos"

    nombre: Mapped[str] = mapped_column(String(50), primary_key=True)
    prefijo_folio: Mapped[str] = mapped_column(String(10), unique=True)
    tipos_requeridos: Mapped[list[str]] = mapped_column(Json, default=list)
    tipos_opcionales: Mapped[list[str]] = mapped_column(Json, default=list)
    permitir_antecedentes: Mapped[bool] = mapped_column(Boolean, default=False)
    caducidad_antecedentes_dias: Mapped[int] = mapped_column(Integer)
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    modelos: Mapped[str] = mapped_column(String(50), default="default", server_default="default")


class SecuenciaFolio(Base):
    """Ultimo numero de folio por (proceso, anio). Se incrementa con un solo INSERT ... ON CONFLICT."""
    __tablename__ = "secuencias_folio"

    proceso: Mapped[str] = mapped_column(ForeignKey("procesos.nombre"), primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo: Mapped[int] = mapped_column(Integer)


class Folio(Base):
    __tablename__ = "folios"
    __table_args__ = (
        UniqueConstraint("proceso", "anio", "secuencia", name="uq_folios_proceso_anio_secuencia"),
        CheckConstraint(_en("estado_general", ESTADOS_FOLIO), name="ck_folios_estado_general"),
        CheckConstraint(f"decision IS NULL OR {_en('decision', DECISIONES)}", name="ck_folios_decision"),
    )

    folio: Mapped[str] = mapped_column(String(30), primary_key=True)
    proceso: Mapped[str] = mapped_column(ForeignKey("procesos.nombre"))
    anio: Mapped[int] = mapped_column(Integer)
    secuencia: Mapped[int] = mapped_column(Integer)
    estado_general: Mapped[str] = mapped_column(String(20), default="en_revision",
                                                server_default="en_revision")
    referencia_externa: Mapped[str | None] = mapped_column(String(100))  # ADR-004
    creado_en: Mapped[datetime] = _creado_en()  # ADR-004: fecha_solicitud
    # ADR-006 G: tras la decision el folio queda cerrado
    decision: Mapped[str | None] = mapped_column(String(10))
    decision_comentario: Mapped[str | None] = mapped_column(Text)
    decision_usuario: Mapped[str | None] = mapped_column(String(100))
    decision_fecha: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (
        CheckConstraint(_en("estado_analisis", EstadoAnalisis), name="ck_documentos_estado_analisis"),
        Index("ix_documentos_folio_hash", "folio", "hash_sha256"),  # duplicados en el folio
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(ForeignKey("folios.folio"))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    ruta_s3: Mapped[str] = mapped_column(String(500))
    hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    tipo_declarado: Mapped[str | None] = mapped_column(String(50))
    tipo_documental_confirmado: Mapped[str | None] = mapped_column(String(50))  # ADR-006 2.5
    estado_analisis: Mapped[str] = mapped_column(String(20), default=EstadoAnalisis.pendiente.value,
                                                 server_default=EstadoAnalisis.pendiente.value)
    creado_en: Mapped[datetime] = _creado_en()


class Resultado(Base):
    """Nunca se sobrescribe: una fila por version; la vigente es la de version mayor (ADR-006 2.5)."""
    __tablename__ = "resultados"
    __table_args__ = (UniqueConstraint("documento_id", "version", name="uq_resultados_documento_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id"))
    version: Mapped[int] = mapped_column(Integer)
    json: Mapped[dict[str, Any]] = mapped_column(Json)  # ResultadoDocumento
    creado_en: Mapped[datetime] = _creado_en()


class AlertaBD(Base):
    """documento_id NULL = alerta de expediente (ADR-006 2.1). id = Alerta.id (ADR-006 1.3)."""
    __tablename__ = "alertas"
    __table_args__ = (CheckConstraint(_en("severidad", Severidad), name="ck_alertas_severidad"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    folio: Mapped[str] = mapped_column(ForeignKey("folios.folio"), index=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(30))
    severidad: Mapped[str] = mapped_column(String(20))
    mensaje: Mapped[str] = mapped_column(Text)
    confianza: Mapped[float] = mapped_column(Float)
    campo: Mapped[str | None] = mapped_column(String(100))
    # NULL = alerta de plataforma (DUP, EXP, CMP); N = alerta del motor de la version N del resultado.
    # Al reprocesar solo se muestran las del motor de la version mayor
    version_resultado: Mapped[int | None] = mapped_column(Integer, index=True)
    resuelta_por_revisor: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # ADR-006 2.2: aplica NULL = sin revisar
    aplica: Mapped[bool | None] = mapped_column(Boolean)
    comentario: Mapped[str | None] = mapped_column(Text)
    resuelta_por: Mapped[str | None] = mapped_column(String(100))
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = _creado_en()


class Correccion(Base):
    __tablename__ = "correcciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id"))
    campo: Mapped[str] = mapped_column(String(100))
    valor_anterior: Mapped[Any] = mapped_column(Json)  # texto, fecha o numero
    valor_nuevo: Mapped[Any] = mapped_column(Json)
    # Version del Resultado sobre la que se hizo: solo se aplica a esa version (al reprocesar con otro
    # tipo, las correcciones viejas no caen sobre una ficha distinta)
    version_resultado: Mapped[int] = mapped_column(Integer, server_default="1")
    usuario: Mapped[str] = mapped_column(String(100))
    creado_en: Mapped[datetime] = _creado_en()


class Auditoria(Base):
    """folio y documento_id sin FK: la auditoria no bloquea borrados ni orden de insercion."""
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str | None] = mapped_column(String(100))
    accion: Mapped[str] = mapped_column(String(50))  # ver ACCIONES_AUDITORIA
    folio: Mapped[str | None] = mapped_column(String(30), index=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detalle: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    modelo: Mapped[str | None] = mapped_column(String(100))
    version_prompt: Mapped[str | None] = mapped_column(String(100))
    creado_en: Mapped[datetime] = _creado_en()
