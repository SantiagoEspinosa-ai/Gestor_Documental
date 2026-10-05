"""
Calienta los modelos de Ollama antes de la demo: los carga en memoria para que el primer documento no pague la
carga (~21 s con gemma4:e2b en CPU; spec, seccion 13). No analiza ningun documento ni envia datos.

Uso (desde backend/, o en el contenedor del backend):
    python -m app.modulos.motor_ia.calentar            # modelo de texto (el camino habitual)
    python -m app.modulos.motor_ia.calentar --vision   # tambien el de vision (con OLLAMA_MAX_LOADED_MODELS=1
                                                       # descarga el de texto: usar solo si la demo empieza con fotos)
Lee el .env de la raiz del repo (el entorno real tiene prioridad). Salida 0 si todos cargan; 1 si alguno falla.
Es un punto de entrada: ningun modulo lo importa.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from app.modulos.motor_ia.enrutador import ErrorEnrutador, crear_enrutador
from app.modulos.motor_ia.interfaces import Tarea
from app.modulos.motor_ia.proveedores.base import KEEP_ALIVE

RAIZ_REPO = Path(__file__).resolve().parents[4]
TIMEOUT_CARGA_S = 300  # cargar un modelo en CPU tarda decenas de segundos


def calentar(base_url: str, modelos: list[str], cliente: httpx.Client | None = None) -> dict[str, float | str]:
    """Carga cada modelo con una peticion vacia (`/api/generate` sin prompt) y lo deja `KEEP_ALIVE` en memoria.
    Devuelve {modelo: segundos} o {modelo: "error: ..."}."""
    cliente = cliente or httpx.Client()
    resultado: dict[str, float | str] = {}
    for modelo in modelos:
        inicio = time.perf_counter()
        try:
            r = cliente.post(f"{base_url.rstrip('/')}/api/generate", json={"model": modelo, "keep_alive": KEEP_ALIVE},
                             timeout=TIMEOUT_CARGA_S)
            r.raise_for_status()
            resultado[modelo] = round(time.perf_counter() - inicio, 1)
        except httpx.HTTPError as e:
            resultado[modelo] = f"error: {type(e).__name__}"
    return resultado


def ejecutar(argv: list[str] | None = None, *, cliente: httpx.Client | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.modulos.motor_ia.calentar", description=__doc__.split("\n")[1])
    p.add_argument("--vision", action="store_true", help="carga tambien el modelo de vision")
    args = p.parse_args(argv)
    load_dotenv(RAIZ_REPO / ".env", override=False)
    try:
        proveedor = crear_enrutador().obtener(Tarea.extraccion, None)
    except ErrorEnrutador as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not hasattr(proveedor, "modelo_texto"):
        print(f"El proveedor '{proveedor.nombre}' no es local: no hay nada que calentar", file=sys.stderr)
        return 0
    modelos = [proveedor.modelo_texto] + ([proveedor.modelo_vision] if args.vision else [])
    resultado = calentar(proveedor.base_url, modelos, cliente)
    for modelo, valor in resultado.items():
        print(f"{modelo}: {valor if isinstance(valor, str) else f'cargado en {valor} s'}", file=sys.stderr)
    return 0 if all(not isinstance(v, str) for v in resultado.values()) else 1


if __name__ == "__main__":
    sys.exit(ejecutar())
