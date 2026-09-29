from fastapi import FastAPI

app = FastAPI(title="Gestor Documental Inteligente", version="0.1.0")


@app.get("/salud")
def salud() -> dict:
    return {"estado": "ok"}


# TODO PERSONA_1: incluir routers de app/modulos/api (auth, folios, documentos, procesos, webhooks)
