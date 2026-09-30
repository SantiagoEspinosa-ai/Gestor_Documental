"""
Prueba rapida (spike) de Ollama con los prompts reales del repo. NO es codigo del repo.
Todos los datos son inventados. Solo llama a Ollama local; nada sale de la maquina.

Uso (con el venv del backend, desde esta carpeta):
  python prueba_ollama.py --modelo gemma4:e2b
  python prueba_ollama.py --solo-imagenes
  python prueba_ollama.py --modelo qwen2.5vl:3b --sin-think [--modo texto]
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import io
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import jinja2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# docs/motor_ia/pruebas_ollama/prueba_ollama.py -> raiz del repo
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "backend"))
from app.modulos.configuracion import servicio as configuracion  # noqa: E402

AQUI = Path(__file__).resolve().parent

# Valores inventados de la imagen: son la "verdad" para comparar la extraccion.
ESPERADO = {
    "nombre_completo": "ANA EJEMPLO PRUEBA",
    "numero_pasaporte": "X1234567P",
    "fecha_nacimiento": "1990-01-01",
    "fecha_expedicion": "2024-05-10",
    "fecha_vencimiento": "2034-05-09",
    "nacionalidad": "PAIS FICTICIO",
    "sexo": "F",
}


# ---------------------------------------------------------------- imagenes

def _fuente(nombre: str, tam: int):
    for ruta in (f"C:/Windows/Fonts/{nombre}", nombre):
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            pass
    return ImageFont.load_default(size=tam)


def _mrz(texto: str) -> str:
    return (texto + "<" * 44)[:44]


FILAS = [
    ("Tipo / Type", "P"), ("Pais emisor / Issuing country", "XXX"),
    ("Numero de pasaporte / Passport No.", ESPERADO["numero_pasaporte"]),
    ("Apellidos y nombre / Surname and given names", ESPERADO["nombre_completo"]),
    ("Nacionalidad / Nationality", ESPERADO["nacionalidad"]),
    ("Fecha de nacimiento / Date of birth", "01/01/1990"), ("Sexo / Sex", ESPERADO["sexo"]),
    ("Fecha de expedicion / Date of issue", "10/05/2024"),
    ("Fecha de caducidad / Date of expiry", "09/05/2034"),
]
MRZ = (_mrz("P<XXXEJEMPLO<PRUEBA<<ANA"), _mrz("X1234567P0XXX9001017F3405097"))

# Texto de la imagen A tal como lo sacaria PyMuPDF de un pdf_digital (modo --modo texto).
TEXTO_A = "\n".join(
    ["PASAPORTE / PASSPORT", "DOCUMENTO DE MUESTRA - SIN VALIDEZ", "FOTO"]
    + [linea for fila in FILAS for linea in fila]
    + list(MRZ)
)


def generar_imagenes(destino: Path) -> dict[str, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1200, 850), (236, 240, 232))
    d = ImageDraw.Draw(img)
    titulo, etiqueta, valor, mono = _fuente("arialbd.ttf", 34), _fuente("arial.ttf", 18), _fuente("arialbd.ttf", 26), _fuente("cour.ttf", 30)

    d.rectangle([20, 20, 1180, 830], outline=(90, 110, 90), width=4)
    d.text((60, 45), "PASAPORTE / PASSPORT", font=titulo, fill=(40, 60, 40))
    d.text((760, 55), "DOCUMENTO DE MUESTRA - SIN VALIDEZ", font=etiqueta, fill=(160, 40, 40))
    d.rectangle([60, 130, 330, 470], fill=(190, 195, 190), outline=(120, 120, 120), width=2)
    d.text((140, 290), "FOTO", font=titulo, fill=(120, 120, 120))

    y = 130
    for et, va in FILAS:
        d.text((370, y), et, font=etiqueta, fill=(80, 90, 80))
        d.text((370, y + 20), va, font=valor, fill=(10, 10, 10))
        y += 58

    d.rectangle([20, 700, 1180, 830], fill=(250, 250, 250))
    d.text((45, 715), MRZ[0], font=mono, fill=(0, 0, 0))
    d.text((45, 765), MRZ[1], font=mono, fill=(0, 0, 0))

    a = destino / "pasaporte_inventado_A.png"
    b = destino / "pasaporte_inventado_B.jpg"
    if a.exists() and b.exists():
        return {"A": a, "B": b}  # no regenerar: B lleva ruido aleatorio y las imagenes estan versionadas
    img.save(a)

    # Variante B: foto de movil simulada (rotacion, desenfoque, ruido, JPEG de baja calidad).
    random.seed(7)
    b_img = img.rotate(3, expand=True, fillcolor=(70, 70, 70), resample=Image.BICUBIC)
    b_img = b_img.filter(ImageFilter.GaussianBlur(1.3))
    ruido = Image.effect_noise(b_img.size, 25).convert("RGB")
    b_img = Image.blend(b_img, ruido, 0.12)
    b_img.save(b, quality=55)
    return {"A": a, "B": b}


# ---------------------------------------------------------------- prompts

def renderizar(id_prompt: str, **variables) -> str:
    texto = (REPO / "prompts" / f"{id_prompt}_v1.md").read_text(encoding="utf-8")
    cuerpo = texto.split("---", 2)[2] if texto.startswith("---") else texto  # quita el frontmatter
    return jinja2.Template(cuerpo).render(**variables).strip()


def prompt_clasificacion() -> str:
    tipos = "\n".join(
        f"- {t.nombre}: {t.descripcion} Caracteristicas: {'; '.join(t.caracteristicas_esperadas)}"
        for t in configuracion.listar()
    )
    return renderizar("clasificacion", tipos_posibles=tipos, contexto_rag="(vacio)")


def prompt_extraccion() -> str:
    ficha = configuracion.obtener("pasaporte")
    esquema = "\n".join(
        f"- {n}: {c.tipo.value}, {'obligatorio' if c.obligatorio else 'opcional'}" for n, c in ficha.campos.items()
    )
    return renderizar("extraccion", tipo_documental="pasaporte", esquema_campos=esquema)


# ---------------------------------------------------------------- RAM

class _Memoria(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def ram_libre_gb() -> float:
    m = _Memoria()
    m.dwLength = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1024**3


class VigilanteRam(threading.Thread):
    """Si la RAM libre baja del umbral, detiene el modelo en Ollama y aborta la prueba."""

    def __init__(self, modelo: str, umbral_gb: float, log):
        super().__init__(daemon=True)
        self.modelo, self.umbral, self.log = modelo, umbral_gb, log
        self.minimo = ram_libre_gb()

    def run(self):
        while True:
            libre = ram_libre_gb()
            self.minimo = min(self.minimo, libre)
            if libre < self.umbral:
                self.log(f"!! RAM libre {libre:.2f} GB < {self.umbral} GB: se detiene el modelo y se aborta")
                subprocess.run(["ollama", "stop", self.modelo], capture_output=True, timeout=60)
                os._exit(3)
            time.sleep(1)


# ---------------------------------------------------------------- ejecucion

def llamar(base_url: str, modelo: str, prompt: str, imagen: Path | None, think: bool = True) -> tuple[dict, float]:
    mensaje = {"role": "user", "content": prompt}
    if imagen is not None:
        mensaje["images"] = [base64.b64encode(imagen.read_bytes()).decode()]
    else:
        mensaje["content"] = f"{prompt}\n\nContenido del documento (texto extraido):\n--- pagina_1 ---\n{TEXTO_A}"
    cuerpo = {
        "model": modelo,
        "messages": [mensaje],
        "format": "json",
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0, "num_predict": 800},
    }
    if think:
        cuerpo["think"] = False   # gemma4 razona por defecto; aqui solo queremos el JSON
    inicio = time.perf_counter()
    r = httpx.post(f"{base_url}/api/chat", json=cuerpo, timeout=900)
    r.raise_for_status()
    return r.json(), time.perf_counter() - inicio


def evaluar(tarea: str, contenido: str) -> dict:
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as e:
        return {"json_valido": False, "error": str(e)}
    res = {"json_valido": True}
    if tarea == "clasificacion":
        res["claves_ok"] = {"tipo_documental_detectado", "confianza", "razonamiento"} <= datos.keys()
        res["tipo_detectado"] = datos.get("tipo_documental_detectado")
        res["confianza"] = datos.get("confianza")
        res["acierto"] = datos.get("tipo_documental_detectado") == "pasaporte"
    else:
        claves = {"datos_extraidos", "nivel_confianza_por_campo", "evidencia_por_campo"}
        res["claves_ok"] = claves <= datos.keys()
        extraidos = datos.get("datos_extraidos") or {}
        confianzas = datos.get("nivel_confianza_por_campo") or {}
        evidencias = datos.get("evidencia_por_campo") or {}
        campos = {}
        for campo, esperado in ESPERADO.items():
            valor = extraidos.get(campo)
            campos[campo] = {
                "valor": valor,
                "ok": str(valor or "").strip().upper() == esperado.upper(),
                "confianza": confianzas.get(campo),
                "evidencia": evidencias.get(campo),
            }
        res["campos"] = campos
        res["aciertos"] = sum(c["ok"] for c in campos.values())
        res["observaciones_visuales"] = datos.get("observaciones_visuales")
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="gemma4:e2b")
    p.add_argument("--base-url", default="http://localhost:11434")
    p.add_argument("--umbral-ram-gb", type=float, default=1.0)
    p.add_argument("--solo-imagenes", action="store_true")
    p.add_argument("--modo", choices=["imagen", "texto"], default="imagen", help="texto = TEXTO_A como string, sin imagen")
    p.add_argument("--sin-think", action="store_true", help="no enviar el parametro think (modelos sin razonamiento)")
    args = p.parse_args()

    imagenes = generar_imagenes(AQUI / "imagenes")
    if args.solo_imagenes:
        print("Imagenes:", *imagenes.values(), sep="\n  ")
        return

    carpeta = AQUI / "resultados" / (args.modelo.replace(":", "_") + ("_texto" if args.modo == "texto" else ""))
    (carpeta / "respuestas").mkdir(parents=True, exist_ok=True)
    log_fichero = (carpeta / "log.txt").open("w", encoding="utf-8")

    def log(msg: str):
        linea = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linea, flush=True)
        log_fichero.write(linea + "\n")
        log_fichero.flush()

    log(f"Modelo {args.modelo} | modo {args.modo} | RAM libre inicial {ram_libre_gb():.2f} GB | umbral {args.umbral_ram_gb} GB")
    vigilante = VigilanteRam(args.modelo, args.umbral_ram_gb, log)
    vigilante.start()

    configuracion.cargar()
    prompts = {"clasificacion": prompt_clasificacion(), "extraccion": prompt_extraccion()}
    (carpeta / "prompts_enviados.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")

    ejecuciones = [
        (1, "clasificacion", "A", "frio"), (2, "clasificacion", "A", "caliente"),
        (3, "extraccion", "A", "caliente"), (4, "extraccion", "A", "repeticion"),
    ]
    if args.modo == "imagen":
        ejecuciones.append((5, "extraccion", "B", "foto degradada"))
    resumen = []
    for n, tarea, variante, nota in ejecuciones:
        log(f"#{n} {tarea} {args.modo} {variante} ({nota}) ...")
        try:
            respuesta, segundos = llamar(args.base_url, args.modelo, prompts[tarea],
                                         imagenes[variante] if args.modo == "imagen" else None, not args.sin_think)
        except Exception as e:  # noqa: BLE001 - spike: registrar y seguir
            log(f"#{n} ERROR: {type(e).__name__}: {e}")
            resumen.append({"n": n, "tarea": tarea, "variante": variante, "error": f"{type(e).__name__}: {e}"})
            continue
        contenido = respuesta.get("message", {}).get("content", "")
        (carpeta / "respuestas" / f"{n}_{tarea}_{variante}.json").write_text(
            json.dumps(respuesta, ensure_ascii=False, indent=2), encoding="utf-8")
        ns = 1e9
        fila = {
            "n": n, "tarea": tarea, "variante": variante, "nota": nota,
            "segundos_total": round(segundos, 1),
            "carga_s": round(respuesta.get("load_duration", 0) / ns, 1),
            "lectura_prompt_s": round(respuesta.get("prompt_eval_duration", 0) / ns, 1),
            "tokens_prompt": respuesta.get("prompt_eval_count"),
            "generacion_s": round(respuesta.get("eval_duration", 0) / ns, 1),
            "tokens_generados": respuesta.get("eval_count"),
            "ram_libre_min_gb": round(vigilante.minimo, 2),
            **evaluar(tarea, contenido),
        }
        resumen.append(fila)
        log(f"#{n} ok en {fila['segundos_total']} s | json_valido={fila['json_valido']} | "
            f"{'acierto=' + str(fila.get('acierto')) if tarea == 'clasificacion' else 'aciertos=' + str(fila.get('aciertos')) + '/7'}")

    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Fin. RAM libre minima {vigilante.minimo:.2f} GB. Resumen en {carpeta / 'resumen.json'}")


if __name__ == "__main__":
    main()
