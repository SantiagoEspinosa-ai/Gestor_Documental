"""
Diagnostico minimo de vision: una imagen con 'HOLA' grande sobre blanco. Si el modelo no la lee,
la vision esta rota en este entorno (no es un problema de calidad). NO es codigo del repo.
Uso: python -u diagnostico_hola.py --modelo gemma4:e2b [--sin-think]
"""
import argparse, base64, json, time
import httpx
from PIL import Image, ImageDraw
from prueba_ollama import AQUI, VigilanteRam, _fuente, ram_libre_gb

p = argparse.ArgumentParser()
p.add_argument("--modelo", default="gemma4:e2b")
p.add_argument("--sin-think", action="store_true", help="no enviar el parametro think (modelos sin razonamiento)")
args = p.parse_args()

ruta = AQUI / "imagenes" / "hola.png"
if not ruta.exists():
    img = Image.new("RGB", (800, 400), "white")
    ImageDraw.Draw(img).text((170, 110), "HOLA", font=_fuente("arialbd.ttf", 160), fill="black")
    img.save(ruta)

VigilanteRam(args.modelo, 1.0, print).start()
print(f"RAM libre inicial {ram_libre_gb():.2f} GB")
cuerpo = {"model": args.modelo, "stream": False, "keep_alive": "5m",
          "options": {"temperature": 0, "num_predict": 50},
          "messages": [{"role": "user", "content": "Que palabra aparece en esta imagen? Responde solo con la palabra.",
                        "images": [base64.b64encode(ruta.read_bytes()).decode()]}]}
if not args.sin_think:
    cuerpo["think"] = False
t = time.perf_counter()
r = httpx.post("http://localhost:11434/api/chat", json=cuerpo, timeout=600).json()
contenido = r.get("message", {}).get("content", r.get("error", ""))
print(f"{args.modelo} | {time.perf_counter() - t:.1f} s | tokens_prompt={r.get('prompt_eval_count')} | respuesta: {contenido!r}")
print("LEE LA IMAGEN" if "HOLA" in contenido.upper() else "NO LEE LA IMAGEN")
salida = AQUI / "resultados" / args.modelo.replace(":", "_") / "respuestas"
salida.mkdir(parents=True, exist_ok=True)
(salida / "diag_hola.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
