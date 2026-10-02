"""
Diagnostico: el modelo lee de verdad la imagen inventada? Pide una transcripcion literal
(sin JSON y con JSON), con tope de tokens y vigilante de RAM. NO es codigo del repo.

Uso: python -u diagnostico_transcripcion.py --modelo gemma4:e2b
"""
import argparse
import base64
import json
import time
from pathlib import Path

import httpx

from prueba_ollama import AQUI, VigilanteRam, ram_libre_gb

p = argparse.ArgumentParser()
p.add_argument("--modelo", default="gemma4:e2b")
p.add_argument("--imagen", default="A")
p.add_argument("--max-tokens", type=int, default=400)
args = p.parse_args()

vigilante = VigilanteRam(args.modelo, 1.0, print)
vigilante.start()
print(f"RAM libre inicial {ram_libre_gb():.2f} GB")

imagen = next((AQUI / "imagenes").glob(f"pasaporte_inventado_{args.imagen}.*"))
salida = AQUI / "resultados" / args.modelo.replace(":", "_") / "respuestas"
salida.mkdir(parents=True, exist_ok=True)
b64 = base64.b64encode(imagen.read_bytes()).decode()

for fmt in (None, "json"):
    pregunta = "Transcribe literalmente el texto que ves en esta imagen."
    if fmt:
        pregunta += ' Devuelve un JSON {"texto": "..."}.'
    cuerpo = {"model": args.modelo, "stream": False, "think": False, "keep_alive": "5m",
              "options": {"temperature": 0, "num_predict": args.max_tokens},
              "messages": [{"role": "user", "content": pregunta, "images": [b64]}]}
    if fmt:
        cuerpo["format"] = fmt
    t = time.perf_counter()
    r = httpx.post("http://localhost:11434/api/chat", json=cuerpo, timeout=600).json()
    print(f"\n=== format={fmt or 'texto'} | {time.perf_counter() - t:.1f} s | tokens_prompt={r.get('prompt_eval_count')} "
          f"| tokens_generados={r.get('eval_count')} | fin={r.get('done_reason')}")
    print(r.get("message", {}).get("content", "")[:1200])
    (salida / f"diag_transcripcion_{args.imagen}_{fmt or 'texto'}.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nRAM libre minima {vigilante.minimo:.2f} GB")
