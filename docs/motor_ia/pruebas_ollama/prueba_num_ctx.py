"""
Medida de num_ctx para visión: tokens de 1 y de 4 paginas A4 (1000x1414 px, inventadas) con el prompt
real extraccion_v2 y, en el peor caso, 20 000 caracteres de texto. num_predict=1: solo interesa la
lectura del prompt (prompt_eval_count). NO es codigo del backend. Solo Ollama local.

Uso: python -u prueba_num_ctx.py --modelo qwen2.5vl:3b --num-ctx 16384
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import time

import httpx
from PIL import Image, ImageDraw

from prueba_ollama import AQUI, VigilanteRam, _fuente, configuracion, ram_libre_gb
from app.modulos.motor_ia.interfaces import Pagina
from app.modulos.motor_ia.prompts import formatear_contenido, formatear_esquema, renderizar


def pagina_a4(n: int) -> bytes:
    """Pagina A4 inventada a 1000 px de ancho con el pasaporte de prueba incrustado."""
    lienzo = Image.new("RGB", (1000, 1414), "white")
    pasaporte = Image.open(AQUI / "imagenes" / "pasaporte_inventado_A.png").resize((900, 638))
    lienzo.paste(pasaporte, (50, 120))
    ImageDraw.Draw(lienzo).text((50, 40), f"DOCUMENTO DE MUESTRA - PAGINA {n}", font=_fuente("arialbd.ttf", 32), fill="black")
    salida = io.BytesIO()
    lienzo.save(salida, format="PNG")
    return salida.getvalue()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="qwen2.5vl:3b")
    p.add_argument("--num-ctx", type=int, default=16384)
    args = p.parse_args()

    configuracion.cargar()
    esquema = formatear_esquema(configuracion.obtener("pasaporte"))
    relleno = ("Texto de relleno inventado para medir el contexto. " * 400)[:20000]
    escenarios = {
        "1_pagina_sin_texto": (1, [Pagina(1, None)]),
        "4_paginas_20000_caracteres": (4, [Pagina(i, relleno[(i - 1) * 5000:i * 5000]) for i in range(1, 5)]),
    }

    vigilante = VigilanteRam(args.modelo, 1.0, print)
    vigilante.start()
    print(f"RAM libre inicial {ram_libre_gb():.2f} GB | num_ctx {args.num_ctx}")
    resumen = {"modelo": args.modelo, "num_ctx": args.num_ctx, "escenarios": {}}
    for nombre, (n_paginas, paginas) in escenarios.items():
        prompt, _ = renderizar("extraccion", tipo_documental="pasaporte",
                               contenido=formatear_contenido(paginas), esquema_campos=esquema)
        cuerpo = {"model": args.modelo, "stream": False, "keep_alive": "5m",
                  "options": {"temperature": 0, "num_predict": 1, "num_ctx": args.num_ctx},
                  "messages": [{"role": "user", "content": prompt,
                                "images": [base64.b64encode(pagina_a4(i)).decode() for i in range(1, n_paginas + 1)]}]}
        t = time.perf_counter()
        r = httpx.post("http://localhost:11434/api/chat", json=cuerpo, timeout=1800).json()
        fila = {"paginas": n_paginas, "caracteres_prompt": len(prompt), "tokens_prompt": r.get("prompt_eval_count"),
                "segundos": round(time.perf_counter() - t, 1), "error": r.get("error")}
        resumen["escenarios"][nombre] = fila
        print(nombre, fila, flush=True)
    resumen["ram_libre_min_gb"] = round(vigilante.minimo, 2)
    destino = AQUI / "resultados" / (args.modelo.replace(":", "_") + "_num_ctx")
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RAM libre minima", resumen["ram_libre_min_gb"], "GB")


if __name__ == "__main__":
    main()
