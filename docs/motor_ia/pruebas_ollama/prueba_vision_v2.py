"""
Cierre de la vision: qwen2.5vl:3b con el borrador de prompt v2 (prompts_borrador/extraccion_v2.md).
Escenarios: A y B originales (2 ejecuciones cada uno) y B reescalada a 1000 y 800 px de ancho
(2 ejecuciones cada una). NO es codigo del repo. Datos inventados; solo Ollama local.

Uso: python -u prueba_vision_v2.py --modelo qwen2.5vl:3b --sin-think
"""
from __future__ import annotations

import argparse
import json
import re
import time

import jinja2
from PIL import Image

from prueba_ollama import AQUI, ESPERADO, VigilanteRam, configuracion, generar_imagenes, llamar, ram_libre_gb

EVIDENCIA_VALIDA = re.compile(r"^pagina_[1-9]\d*(:(seccion_superior|seccion_central|seccion_inferior|mrz))?$")
FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAMPOS_FECHA = ("fecha_nacimiento", "fecha_expedicion", "fecha_vencimiento")


def prompt_v2() -> str:
    texto = (AQUI / "prompts_borrador" / "extraccion_v2.md").read_text(encoding="utf-8")
    cuerpo = texto.split("---", 2)[2]
    ficha = configuracion.obtener("pasaporte")
    esquema = "\n".join(
        f"- {n}: {c.tipo.value}, {'obligatorio' if c.obligatorio else 'opcional'}" for n, c in ficha.campos.items()
    )
    # Modalidad imagen sin OCR (Tesseract no esta instalado): el contenido de texto va vacio.
    return jinja2.Template(cuerpo).render(tipo_documental="pasaporte", esquema_campos=esquema,
                                          contenido="--- pagina_1 ---\n(sin texto extraido)").strip()


def reescalar(origen, ancho: int):
    destino = origen.with_name(f"{origen.stem}_{ancho}px.jpg")
    if destino.exists():
        return destino
    img = Image.open(origen)
    img.resize((ancho, round(img.height * ancho / img.width)), Image.LANCZOS).save(destino, quality=85)
    return destino


def evaluar(contenido: str) -> dict:
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as e:
        return {"json_valido": False, "error": str(e)}
    ext = datos.get("datos_extraidos") or {}
    conf = datos.get("nivel_confianza_por_campo") or {}
    evi = datos.get("evidencia_por_campo") or {}
    campos = {c: {"valor": ext.get(c), "ok": str(ext.get(c) or "").strip().upper() == e.upper(),
                  "confianza": conf.get(c), "evidencia": evi.get(c)} for c, e in ESPERADO.items()}
    return {
        "json_valido": True,
        "aciertos": sum(v["ok"] for v in campos.values()),
        "fechas_iso": sum(bool(FECHA_ISO.match(str(ext.get(c) or ""))) for c in CAMPOS_FECHA),
        "evidencias_validas": sum(bool(EVIDENCIA_VALIDA.match(str(v["evidencia"] or ""))) for v in campos.values()),
        "confianzas": sorted({v["confianza"] for v in campos.values()}, key=str),
        "campos": campos,
        "observaciones_visuales": datos.get("observaciones_visuales"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="qwen2.5vl:3b")
    p.add_argument("--sin-think", action="store_true")
    args = p.parse_args()

    imagenes = generar_imagenes(AQUI / "imagenes")
    escenarios = {"A": imagenes["A"], "B": imagenes["B"],
                  "B_1000px": reescalar(imagenes["B"], 1000), "B_800px": reescalar(imagenes["B"], 800)}

    carpeta = AQUI / "resultados" / (args.modelo.replace(":", "_") + "_v2")
    (carpeta / "respuestas").mkdir(parents=True, exist_ok=True)
    log_fichero = (carpeta / "log.txt").open("w", encoding="utf-8")

    def log(msg: str):
        linea = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linea, flush=True)
        log_fichero.write(linea + "\n")
        log_fichero.flush()

    configuracion.cargar()
    prompt = prompt_v2()
    (carpeta / "prompt_enviado.txt").write_text(prompt, encoding="utf-8")

    log(f"Modelo {args.modelo} | prompt v2 borrador | RAM libre inicial {ram_libre_gb():.2f} GB")
    vigilante = VigilanteRam(args.modelo, 1.0, log)
    vigilante.start()

    resumen = []
    for nombre, imagen in escenarios.items():
        tam = Image.open(imagen).size
        for rep in (1, 2):
            log(f"{nombre} {tam[0]}x{tam[1]} ejecucion {rep} ...")
            try:
                respuesta, segundos = llamar("http://localhost:11434", args.modelo, prompt, imagen, not args.sin_think)
            except Exception as e:  # noqa: BLE001 - spike
                log(f"ERROR {type(e).__name__}: {e}")
                resumen.append({"escenario": nombre, "ejecucion": rep, "error": str(e)})
                continue
            (carpeta / "respuestas" / f"{nombre}_{rep}.json").write_text(
                json.dumps(respuesta, ensure_ascii=False, indent=2), encoding="utf-8")
            fila = {"escenario": nombre, "ejecucion": rep, "tamano": f"{tam[0]}x{tam[1]}",
                    "segundos_total": round(segundos, 1), "tokens_prompt": respuesta.get("prompt_eval_count"),
                    "carga_s": round(respuesta.get("load_duration", 0) / 1e9, 1),
                    **evaluar(respuesta.get("message", {}).get("content", ""))}
            resumen.append(fila)
            log(f"  {fila['segundos_total']} s | aciertos {fila.get('aciertos')}/7 | fechas ISO {fila.get('fechas_iso')}/3 "
                f"| evidencias validas {fila.get('evidencias_validas')}/7 | confianzas {fila.get('confianzas')}")

    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Fin. RAM libre minima {vigilante.minimo:.2f} GB")


if __name__ == "__main__":
    main()
