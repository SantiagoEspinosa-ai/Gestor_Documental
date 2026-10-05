"""Router de tipos documentales: GET /api/v1/tipos-documentales (forma `TipoDocumental`, ADR-006 1.5)."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.modelos import Usuario
from app.core.seguridad import usuario_actual
from app.modulos.ingesta import servicio as ingesta

router = APIRouter(prefix="/api/v1/tipos-documentales", tags=["tipos-documentales"])


class CampoTipo(BaseModel):
    tipo: str
    obligatorio: bool
    sensible: bool  # ADR-010 (A6): la API lo enmascara; siempre presente
    # Opcional pero nunca null (`patron?: string` en contrato.ts): solo aparece si la ficha lo define. El
    # None por defecto no se valida ni se envia (exclude_unset), y el openapi lo da como string no requerido
    patron: str = None  # type: ignore[assignment]


class TipoDocumental(BaseModel):
    nombre: str
    nombre_visible: str
    categoria: str
    descripcion: str
    formatos_permitidos: list[str]
    campos: dict[str, CampoTipo]
    confianza_minima_clasificacion: float
    confianza_minima_campo: float
    reglas: list[dict[str, Any]]
    comparaciones: dict[str, list[str]]


# exclude_unset: `patron` no aparece en los campos que no lo definen
@router.get("", response_model=list[TipoDocumental], response_model_exclude_unset=True)
def listar(_: Usuario = Depends(usuario_actual)) -> list[TipoDocumental]:
    return [TipoDocumental.model_validate(ficha) for ficha in ingesta.listar_tipos()]
