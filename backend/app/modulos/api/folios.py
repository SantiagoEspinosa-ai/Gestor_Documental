"""Router de folios: POST /api/v1/folios, GET /api/v1/folios, GET /api/v1/folios/{folio} y su resumen.md."""
from fastapi import APIRouter, Depends, Query, Response
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
    return expediente.enmascarar(expediente.obtener_expediente(sesion, folio))  # ADR-010 A3


@router.get("/{folio}/resumen.md", response_class=Response,
            responses={200: {"content": {"text/markdown": {}}, "description": "Resumen del expediente en Markdown"}})
def resumen_md(folio: str, sesion: Session = Depends(get_sesion), _: Usuario = Depends(usuario_actual)) -> Response:
    """Cualquier rol. 404 RESUMEN_NO_DISPONIBLE si aun no se ha generado; 404 FOLIO_NO_ENCONTRADO si no existe."""
    return Response(content=expediente.obtener_resumen(sesion, folio), media_type=expediente.TIPO_RESUMEN)
