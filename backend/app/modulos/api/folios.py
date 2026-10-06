"""Router de folios: POST /api/v1/folios, GET /api/v1/folios, GET /api/v1/folios/{folio}, su resumen.md y
sus antecedentes (H16, ADR-010 C)."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_sesion
from app.core.modelos import Usuario
from app.core.seguridad import requiere_rol, usuario_actual
from app.modulos.expediente import servicio as expediente
from app.modulos.rag import servicio as rag
from app.schemas.resultado import DecisionHumana, EstadoGeneral, ResultadoExpediente, ResumenFolio

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


class Antecedente(BaseModel):
    """Elemento de GET /folios/{folio}/antecedentes (ADR-010 C4); no forma parte del Contrato 1."""
    folio: str
    fecha_solicitud: datetime | None
    estado_general: EstadoGeneral
    decision_humana: DecisionHumana | None
    fecha_decision: datetime | None
    fragmento_resumen: str | None  # de la memoria de folios, ya enmascarado; null si no esta indexado


class RespuestaAntecedentes(BaseModel):
    """ADR-010 C3: siempre 200; `permitido: false` con su motivo y la lista vacia si no se pueden buscar."""
    permitido: bool
    motivo: Literal["proceso_sin_antecedentes", "folio_sin_referencia"] | None
    elementos: list[Antecedente]


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


@router.get("/{folio}/antecedentes", response_model=RespuestaAntecedentes)
def antecedentes(folio: str, sesion: Session = Depends(get_sesion),
                 _: Usuario = Depends(requiere_rol("revisor", "admin"))) -> RespuestaAntecedentes:
    """ADR-010 C: revisor y admin (C5). El router decide `permitido` y `motivo` (C3), `expediente` elige los
    folios con SQL (C2) y la memoria de folios da el fragmento de cada uno (C4)."""
    motivo = expediente.motivo_sin_antecedentes(sesion, folio)
    if motivo:
        return RespuestaAntecedentes(permitido=False, motivo=motivo, elementos=[])
    elementos = [Antecedente(folio=f.folio, fecha_solicitud=f.creado_en, estado_general=EstadoGeneral(f.estado_general),
                             decision_humana=DecisionHumana(f.decision) if f.decision else None,
                             fecha_decision=f.decision_fecha, fragmento_resumen=rag.fragmento_resumen(f.folio, sesion=sesion))
                 for f in expediente.listar_antecedentes(sesion, folio)]
    return RespuestaAntecedentes(permitido=True, motivo=None, elementos=elementos)
