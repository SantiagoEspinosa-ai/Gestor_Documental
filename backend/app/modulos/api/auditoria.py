"""Router de auditoria: GET /api/v1/auditoria (solo admin; forma `EntradaAuditoria`, ADR-006 1.5)."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import auditoria
from app.core.db import get_sesion
from app.core.modelos import Usuario
from app.core.seguridad import requiere_rol

router = APIRouter(prefix="/api/v1/auditoria", tags=["auditoria"])


class EntradaAuditoria(BaseModel):
    id: int
    usuario: str | None
    accion: str
    folio: str | None
    documento_id: str | None
    detalle: dict[str, Any]
    modelo: str | None
    version_prompt: str | None
    creado_en: datetime


class PaginaAuditoria(BaseModel):
    """La paginacion aun no esta en endpoints.md ("lista de EntradaAuditoria"): pendiente de PERSONA_3."""
    elementos: list[EntradaAuditoria]
    total: int
    pagina: int
    tamano_pagina: int


@router.get("", response_model=PaginaAuditoria)
def listar(folio: str | None = None, pagina: int = Query(1, ge=1),
           tamano_pagina: int = Query(50, ge=1, le=100), sesion: Session = Depends(get_sesion),
           _: Usuario = Depends(requiere_rol("admin"))) -> PaginaAuditoria:
    filas, total = auditoria.listar(sesion, folio, pagina, tamano_pagina)
    elementos = [
        EntradaAuditoria(id=f.id, usuario=f.usuario, accion=f.accion, folio=f.folio,
                         documento_id=str(f.documento_id) if f.documento_id else None,
                         detalle=f.detalle or {}, modelo=f.modelo, version_prompt=f.version_prompt,
                         creado_en=f.creado_en)
        for f in filas
    ]
    return PaginaAuditoria(elementos=elementos, total=total, pagina=pagina, tamano_pagina=tamano_pagina)
