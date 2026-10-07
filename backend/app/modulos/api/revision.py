"""Router de las acciones del revisor (E2.6): resolver alertas; despues, corregir datos, confirmar
clasificacion y decidir el folio. Solo rol revisor. La logica esta en `expediente.servicio`.

Todas las respuestas salen enmascaradas (ADR-010 A3 y A5), tambien la de PATCH datos aunque el revisor
acabe de escribir el valor: el valor real solo se pide con POST /documentos/{id}/revelar.
"""
from typing import Any

import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy.orm import Session

from app.core.db import get_sesion
from app.core.modelos import Usuario
from app.core.seguridad import requiere_rol
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import servicio as ingesta
from app.schemas.resultado import DecisionHumana, ResultadoDocumento, ResultadoExpediente

router = APIRouter(prefix="/api/v1", tags=["revision"])


class ResolverAlertaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aplica: StrictBool  # obligatorio y booleano de verdad ("si" o 1 no valen)
    comentario: str | None = Field(None, max_length=1000)


@router.post("/documentos/{documento_id}/alertas/{alerta_id}/resolver", response_model=ResultadoDocumento)
def resolver_alerta_documento(documento_id: str, alerta_id: str, entrada: ResolverAlertaEntrada,
                              sesion: Session = Depends(get_sesion),
                              usuario: Usuario = Depends(requiere_rol("revisor"))) -> ResultadoDocumento:
    return ingesta.enmascarar(expediente.resolver_alerta_documento(sesion, documento_id, alerta_id, entrada.aplica,
                                                                   entrada.comentario, usuario.usuario))


@router.post("/folios/{folio}/alertas/{alerta_id}/resolver", response_model=ResultadoExpediente)
def resolver_alerta_expediente(folio: str, alerta_id: str, entrada: ResolverAlertaEntrada,
                               sesion: Session = Depends(get_sesion),
                               usuario: Usuario = Depends(requiere_rol("revisor"))) -> ResultadoExpediente:
    return expediente.enmascarar(expediente.resolver_alerta_expediente(sesion, folio, alerta_id, entrada.aplica,
                                                                       entrada.comentario, usuario.usuario))


@router.patch("/documentos/{documento_id}/datos", response_model=ResultadoDocumento)
def corregir_datos(documento_id: str, cambios: dict[str, Any] = Body(...),
                   sesion: Session = Depends(get_sesion),
                   usuario: Usuario = Depends(requiere_rol("revisor"))) -> ResultadoDocumento:
    """Cuerpo `{campo: valor}`; los campos y valores los valida el servicio contra la ficha."""
    return ingesta.enmascarar(expediente.corregir_datos(sesion, documento_id, cambios, usuario.usuario))


class ConfirmarClasificacionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_documental: str = Field(min_length=1, max_length=50)


@router.post("/documentos/{documento_id}/confirmar-clasificacion", response_model=ResultadoDocumento)
def confirmar_clasificacion(documento_id: str, entrada: ConfirmarClasificacionEntrada,
                            background_tasks: BackgroundTasks, sesion: Session = Depends(get_sesion),
                            usuario: Usuario = Depends(requiere_rol("revisor"))) -> ResultadoDocumento:
    resultado, reprocesar = expediente.confirmar_clasificacion(sesion, documento_id, entrada.tipo_documental,
                                                               usuario.usuario)
    if reprocesar:  # version N+1 con el tipo confirmado (ADR-006 2.5); la anterior se conserva
        background_tasks.add_task(ingesta.procesar_documento, uuid.UUID(resultado.identificador_unico_documento),
                                  tipo_confirmado=entrada.tipo_documental)
    return ingesta.enmascarar(resultado)


class RetirarEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=3, max_length=200)  # obligatorio; se guarda tapado (ADR-013)


@router.post("/documentos/{documento_id}/retirar", response_model=ResultadoDocumento)
def retirar_documento(documento_id: str, entrada: RetirarEntrada, sesion: Session = Depends(get_sesion),
                      usuario: Usuario = Depends(requiere_rol("revisor", "admin"))) -> ResultadoDocumento:
    """ADR-013: el documento deja de contar para el folio; nada se borra."""
    return ingesta.enmascarar(expediente.retirar_documento(sesion, documento_id, entrada.motivo, usuario.usuario))


@router.post("/documentos/{documento_id}/restaurar", response_model=ResultadoDocumento)
def restaurar_documento(documento_id: str, sesion: Session = Depends(get_sesion),
                        usuario: Usuario = Depends(requiere_rol("revisor", "admin"))) -> ResultadoDocumento:
    """ADR-013: deshace la retirada; sin cuerpo."""
    return ingesta.enmascarar(expediente.restaurar_documento(sesion, documento_id, usuario.usuario))


class DecisionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: DecisionHumana
    comentario: str | None = Field(None, max_length=1000)


@router.post("/folios/{folio}/decision", response_model=ResultadoExpediente)
def decidir_folio(folio: str, entrada: DecisionEntrada, sesion: Session = Depends(get_sesion),
                  usuario: Usuario = Depends(requiere_rol("revisor"))) -> ResultadoExpediente:
    return expediente.enmascarar(expediente.decidir_folio(sesion, folio, entrada.decision, entrada.comentario,
                                                          usuario.usuario))
