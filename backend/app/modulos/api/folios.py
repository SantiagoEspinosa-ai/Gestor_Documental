"""Router de folios: POST /api/v1/folios, GET /api/v1/folios y GET /api/v1/folios/{folio}."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_sesion
from app.core.modelos import Usuario
from app.core.seguridad import requiere_rol, usuario_actual
from app.modulos.expediente import servicio as expediente
from app.schemas.resultado import EstadoGeneral, ResultadoExpediente, ResumenFolio

router = APIRouter(prefix="/api/v1/folios", tags=["folios"])


class FolioEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proceso: str
    referencia_externa: str | None = Field(None, max_length=100)


class FolioCreado(BaseModel):
    folio: str
    estado_general: EstadoGeneral


class PaginaFolios(BaseModel):
    """Respuesta de GET /folios (Contrato 2); no forma parte del Contrato 1."""
    elementos: list[ResumenFolio]
    total: int
    pagina: int
    tamano_pagina: int


@router.post("", status_code=201, response_model=FolioCreado)
def crear(entrada: FolioEntrada, sesion: Session = Depends(get_sesion),
          usuario: Usuario = Depends(requiere_rol("integrador", "revisor"))) -> FolioCreado:
    folio = expediente.crear_folio(sesion, entrada.proceso, entrada.referencia_externa, usuario.usuario)
    return FolioCreado(folio=folio.folio, estado_general=folio.estado_general)


@router.get("", response_model=PaginaFolios)
def listar(proceso: str | None = None, estado_general: EstadoGeneral | None = None,
           pagina: int = Query(1, ge=1), tamano_pagina: int = Query(20, ge=1, le=100),
           sesion: Session = Depends(get_sesion),
           _: Usuario = Depends(requiere_rol("revisor", "admin"))) -> PaginaFolios:
    elementos, total = expediente.listar_folios(sesion, proceso, estado_general, pagina, tamano_pagina)
    return PaginaFolios(elementos=elementos, total=total, pagina=pagina, tamano_pagina=tamano_pagina)


@router.get("/{folio}", response_model=ResultadoExpediente)
def obtener(folio: str, sesion: Session = Depends(get_sesion),
            _: Usuario = Depends(usuario_actual)) -> ResultadoExpediente:
    return expediente.obtener_expediente(sesion, folio)
