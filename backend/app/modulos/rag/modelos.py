"""
Tabla de la memoria de folios (H14, ADR-010 C4). Vive en rag y no en core/modelos.py: solo la usa este modulo.
La migracion la escribe la plataforma (PERSONA_1); mientras no exista, solo se crea en los tests.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MemoriaFolio(Base):
    __tablename__ = "memoria_folios"

    folio: Mapped[str] = mapped_column(String(30), ForeignKey("folios.folio"), primary_key=True)
    resumen_md: Mapped[str] = mapped_column(Text)       # el resumen.md tal como lo genera la plataforma, enmascarado
    fragmento: Mapped[str] = mapped_column(Text)        # lo que devuelve fragmento_resumen
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
