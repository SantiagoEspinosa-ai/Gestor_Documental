"""Router de documentos: subir un original, consultar su resultado y pedir la URL del original."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel
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


# def (no async): la BD es sincrona y FastAPI la ejecuta en un hilo sin bloquear el bucle
@router.post("/folios/{folio}/documentos", status_code=202, response_model=DocumentoAceptado)
def subir(folio: str, background_tasks: BackgroundTasks, archivo: UploadFile = File(...),
          tipo_declarado: str | None = Form(None), sesion: Session = Depends(get_sesion),
          almacenamiento: Almacenamiento = Depends(get_almacenamiento),
          usuario: Usuario = Depends(requiere_rol("integrador", "revisor"))) -> DocumentoAceptado:
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
            _: Usuario = Depends(usuario_actual)) -> ResultadoDocumento:
    return ingesta.obtener_resultado(sesion, documento_id)


@router.get("/documentos/{documento_id}/original", response_model=UrlOriginal)
def original(documento_id: str, sesion: Session = Depends(get_sesion),
             almacenamiento: Almacenamiento = Depends(get_almacenamiento),
             _: Usuario = Depends(requiere_rol("revisor", "admin"))) -> UrlOriginal:
    # Sin auditoria por ahora: el "mostrar" auditado es de la etapa 3
    return UrlOriginal(url=ingesta.url_original(sesion, almacenamiento, documento_id))
