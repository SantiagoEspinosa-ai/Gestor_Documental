from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.config import get_settings
from app.core.cors import CorsDesdeSettings
from app.core.db import SesionLocal, get_engine
from app.core.errores import registrar_manejadores
from app.core.procesos import leer_procesos, sincronizar_procesos
from app.modulos.api import auditoria, auth, documentos, folios, procesos, revision, tipos_documentales
from app.modulos.configuracion import servicio as configuracion


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Settings al arrancar: un CORS_ORIGENES con "*" (u otro valor invalido) impide arrancar
    config_dir = get_settings().config_dir
    # Fichas primero: si alguna es invalida, ErrorConfiguracion con todos los errores y no arranca
    configuracion.cargar(config_dir)
    procesos_yaml = leer_procesos(config_dir, {t.nombre for t in configuracion.listar()})
    sesion = SesionLocal(bind=get_engine())
    try:
        sincronizar_procesos(sesion, procesos_yaml)
    except (OperationalError, ProgrammingError) as e:
        raise RuntimeError("No se pudo cargar procesos.yaml en BD: ejecuta 'alembic upgrade head' "
                           "antes de arrancar") from e
    finally:
        sesion.close()
    yield


app = FastAPI(title="Gestor Documental Inteligente", version="0.1.0", lifespan=lifespan)
registrar_manejadores(app)
app.add_middleware(CorsDesdeSettings)
app.include_router(auth.router)
app.include_router(folios.router)
app.include_router(documentos.router)
app.include_router(procesos.router)
app.include_router(tipos_documentales.router)
app.include_router(auditoria.router)
app.include_router(revision.router)


@app.get("/salud")
def salud() -> dict:
    return {"estado": "ok"}


# TODO PERSONA_1: incluir routers de app/modulos/api (webhooks, etapa 3)
