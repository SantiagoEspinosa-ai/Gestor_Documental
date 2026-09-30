"""Registro de acciones en la tabla `auditoria` (ADR-006 1.5).

`registrar` solo hace `add`: el commit es de quien llama, para que la accion y su auditoria se
guarden en la misma transaccion. El detalle nunca lleva contrasenas, tokens ni datos sin enmascarar.
"""
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.modelos import ACCIONES_AUDITORIA, Auditoria


def registrar(sesion: Session, accion: str, usuario: str | None = None, folio: str | None = None,
              documento_id: uuid.UUID | None = None, detalle: dict[str, Any] | None = None,
              modelo: str | None = None, version_prompt: str | None = None) -> Auditoria:
    if accion not in ACCIONES_AUDITORIA:
        raise ValueError(f"Accion de auditoria desconocida: {accion}")
    fila = Auditoria(usuario=usuario, accion=accion, folio=folio, documento_id=documento_id,
                     detalle=detalle or {}, modelo=modelo, version_prompt=version_prompt)
    sesion.add(fila)
    return fila


def listar(sesion: Session, folio: str | None = None, pagina: int = 1,
           tamano_pagina: int = 50) -> tuple[list[Auditoria], int]:
    """Pagina del registro, del mas reciente al mas antiguo (creado_en desc, id desc), y el total."""
    filtros = [Auditoria.folio == folio] if folio else []
    total = sesion.scalar(select(func.count()).select_from(Auditoria).where(*filtros))
    filas = sesion.scalars(select(Auditoria).where(*filtros)
                           .order_by(Auditoria.creado_en.desc(), Auditoria.id.desc())
                           .offset((pagina - 1) * tamano_pagina).limit(tamano_pagina))
    return list(filas), total
