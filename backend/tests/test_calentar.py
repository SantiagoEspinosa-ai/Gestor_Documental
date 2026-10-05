"""Tests de motor_ia/calentar.py sin Ollama: el HTTP es falso. No envia datos de documentos."""
import json

import httpx

from app.modulos.motor_ia import calentar
from app.modulos.motor_ia.proveedores.base import KEEP_ALIVE, NUM_CTX


def cliente(respuesta=200, peticiones=None):
    def manejar(peticion: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append((peticion.url.path, peticion.read()))
        return httpx.Response(respuesta, json={"done": True})
    return httpx.Client(transport=httpx.MockTransport(manejar))


def test_carga_cada_modelo_sin_prompt_y_con_keep_alive():
    peticiones = []
    r = calentar.calentar("http://ollama:11434/", ["texto:1", "vision:1"], cliente(peticiones=peticiones))
    assert set(r) == {"texto:1", "vision:1"} and all(isinstance(v, float) for v in r.values())
    assert [ruta for ruta, _ in peticiones] == ["/api/generate", "/api/generate"]
    cuerpo = json.loads(peticiones[0][1])
    assert cuerpo["keep_alive"] == KEEP_ALIVE and "prompt" not in cuerpo
    # Mismo contexto que el motor: si no, Ollama recarga el modelo en la primera peticion real (prueba H10)
    assert cuerpo["options"] == {"num_ctx": NUM_CTX}


def test_error_http_se_informa_sin_lanzar():
    r = calentar.calentar("http://ollama:11434", ["no_descargado:1"], cliente(404))
    assert r == {"no_descargado:1": "error: HTTPStatusError"}


def test_ejecutar_usa_el_modelo_de_texto_del_enrutador(monkeypatch):
    class Proveedor:
        nombre, base_url, modelo_texto, modelo_vision = "ollama", "http://ollama:11434", "texto:1", "vision:1"

    class Enrutador:
        def obtener(self, tarea, tipo=None):
            return Proveedor()

    monkeypatch.setattr(calentar, "crear_enrutador", lambda: Enrutador())
    monkeypatch.setattr(calentar, "load_dotenv", lambda *a, **k: None)
    peticiones = []
    assert calentar.ejecutar([], cliente=cliente(peticiones=peticiones)) == 0
    assert len(peticiones) == 1 and b"texto:1" in peticiones[0][1]
    peticiones.clear()
    assert calentar.ejecutar(["--vision"], cliente=cliente(peticiones=peticiones)) == 0
    assert len(peticiones) == 2
    assert calentar.ejecutar([], cliente=cliente(500)) == 1
