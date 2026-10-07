"""Router de documentos: subir un original, consultar su resultado, pedir la URL del original y revelar
un dato sensible (ADR-010 A4)."""
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.almacenamiento import Almacenamiento, get_almacenamiento
from app.core.config import get_settings
from app.core.db import get_sesion
from app.core.errores import ErrorApi
from app.core.modelos import Usuario
from app.core.seguridad import requiere_rol, usuario_actual
from app.modulos.ingesta import servicio as ingesta
from app.schemas.resultado import EstadoAnalisis, ResultadoDocumento

router = APIRouter(prefix="/api/v1", tags=["documentos"])


class DocumentoAceptado(BaseModel):
    identificador_unico_documento: str
    estado_analisis: EstadoAnalisis


class UrlOriginal(BaseModel):
    url: str


class RevelarEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campo: str = Field(min_length=1, max_length=100)
    motivo: str | None = Field(None, min_length=3, max_length=200)  # ADR-010 A4c, opcional


class DatoRevelado(BaseModel):
    campo: str
    valor: Any


# def (no async): la BD es sincrona y FastAPI la ejecuta en un hilo sin bloquear el bucle
@router.post("/folios/{folio}/documentos", status_code=202, response_model=DocumentoAceptado)
def subir(folio: str, background_tasks: BackgroundTasks, archivo: UploadFile = File(...),
          tipo_declarado: str | None = Form(None), sesion: Session = Depends(get_sesion),
          almacenamiento: Almacenamiento = Depends(get_almacenamiento),
          usuario: Usuario = Depends(requiere_rol("integrador", "revisor"))) -> DocumentoAceptado:
    # ADR-012: subir al folio de otro integrador da 404, antes de leer el fichero
    ingesta.exigir_folio_visible(sesion, folio, usuario)
    maximo_mb = get_settings().tamano_maximo_archivo_mb
    limite = maximo_mb * 1024 * 1024
    datos = archivo.file.read(limite + 1)  # nunca mas de limite + 1 bytes en memoria
    if len(datos) > limite:
        raise ErrorApi(413, "ARCHIVO_DEMASIADO_GRANDE", f"El archivo supera {maximo_mb} MB")

    documento = ingesta.ingestar(sesion, almacenamiento, folio, archivo.filename or "", datos,
                                 tipo_declarado or None, usuario.usuario)
    background_tasks.add_task(ingesta.procesar_documento, documento.id)
    return DocumentoAceptado(identificador_unico_documento=str(documento.id),
                             estado_analisis=EstadoAnalisis.pendiente)


@router.get("/documentos/{documento_id}", response_model=ResultadoDocumento)
def obtener(documento_id: str, sesion: Session = Depends(get_sesion),
            usuario: Usuario = Depends(usuario_actual)) -> ResultadoDocumento:
    # ADR-010 A3 (enmascarado) y ADR-012 (el documento de un folio de otro integrador da 404)
    return ingesta.enmascarar(ingesta.obtener_resultado(sesion, documento_id, usuario))


@router.get("/documentos/{documento_id}/original", response_model=UrlOriginal)
def original(documento_id: str, sesion: Session = Depends(get_sesion),
             almacenamiento: Almacenamiento = Depends(get_almacenamiento),
             usuario: Usuario = Depends(requiere_rol("revisor", "admin"))) -> UrlOriginal:
    # Deja original_visto en la auditoria (sin datos del contenido)
    return UrlOriginal(url=ingesta.url_original(sesion, almacenamiento, documento_id, usuario.usuario))


@router.post("/documentos/{documento_id}/revelar", response_model=DatoRevelado)
def revelar(documento_id: str, entrada: RevelarEntrada, response: Response, sesion: Session = Depends(get_sesion),
            usuario: Usuario = Depends(requiere_rol("revisor", "admin"))) -> DatoRevelado:
    """ADR-010 A4: POST y no GET porque deja auditoria; la respuesta no se guarda en ninguna cache."""
    valor = ingesta.revelar_dato(sesion, documento_id, entrada.campo, usuario.usuario, entrada.motivo)
    response.headers["Cache-Control"] = "no-store"
    return DatoRevelado(campo=entrada.campo, valor=valor)
