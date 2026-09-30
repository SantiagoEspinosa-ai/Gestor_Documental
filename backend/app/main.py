from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.config import get_settings
from app.core.db import SesionLocal, get_engine
from app.core.errores import registrar_manejadores
from app.core.procesos import leer_procesos, sincronizar_procesos
from app.modulos.api import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: configuracion.cargar() de PERSONA_2 cuando su modulo este en main
    procesos = leer_procesos(get_settings().config_dir)
    sesion = SesionLocal(bind=get_engine())
    try:
        sincronizar_procesos(sesion, procesos)
    except (OperationalError, ProgrammingError) as e:
        raise RuntimeError("No se pudo cargar procesos.yaml en BD: ejecuta 'alembic upgrade head' "
                           "antes de arrancar") from e
    finally:
        sesion.close()
    yield


app = FastAPI(title="Gestor Documental Inteligente", version="0.1.0", lifespan=lifespan)
registrar_manejadores(app)
app.include_router(auth.router)


@app.get("/salud")
def salud() -> dict:
    return {"estado": "ok"}


# TODO PERSONA_1: incluir routers de app/modulos/api (folios, documentos, procesos, webhooks)
