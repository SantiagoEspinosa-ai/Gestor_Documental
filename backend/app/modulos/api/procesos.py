"""Router de procesos: GET /api/v1/procesos (Contrato 2, forma `Proceso` del ADR-006 1.2)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_sesion
from app.core.modelos import Usuario
from app.core.procesos import listar_procesos
from app.core.seguridad import requiere_rol

router = APIRouter(prefix="/api/v1/procesos", tags=["procesos"])


class Proceso(BaseModel):
    nombre: str
    prefijo_folio: str
    tipos_requeridos: list[str]
    tipos_opcionales: list[str]
    permitir_antecedentes: bool
    caducidad_antecedentes_dias: int
    # Solo para admin e integrador; al revisor no se le envian (ni siquiera como null)
    webhook_url: str | None = None
    modelos: str | None = None


_SOLO_CONFIGURACION = {"webhook_url", "modelos"}


# response_model_exclude_unset: los campos que no se asignan (webhook_url y modelos para el
# revisor) no aparecen en la respuesta; un webhook_url nulo asignado a un admin si aparece
@router.get("", response_model=list[Proceso], response_model_exclude_unset=True)
def listar(sesion: Session = Depends(get_sesion),
           usuario: Usuario = Depends(requiere_rol("admin", "integrador", "revisor"))) -> list[Proceso]:
    campos = set(Proceso.model_fields)
    if usuario.rol == "revisor":
        campos -= _SOLO_CONFIGURACION
    return [Proceso(**{c: getattr(p, c) for c in campos}) for p in listar_procesos(sesion)]
