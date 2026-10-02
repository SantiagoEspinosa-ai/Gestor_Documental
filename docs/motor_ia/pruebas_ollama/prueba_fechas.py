"""
Cierre de la condicion 1 (fechas): el modelo devuelve las fechas tal como aparecen y el codigo las
normaliza DD/MM/AAAA -> AAAA-MM-DD. Imagenes nuevas (todo inventado) con una fecha de dia > 12
(25/07/2031) y una ambigua (10/05/2024). A y B a 1000 px, 2 ejecuciones cada una.
NO es codigo del repo. Solo Ollama local.

Uso: python -u prueba_fechas.py --modelo qwen2.5vl:3b --sin-think
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date

import jinja2
from PIL import Image

import prueba_ollama as base
from prueba_ollama import AQUI, VigilanteRam, configuracion, llamar, ram_libre_gb

# Datos inventados de este juego de imagenes (los demas campos, como en la prueba anterior).
FECHAS_DOCUMENTO = {  # como aparecen impresas
    "fecha_nacimiento": "01/01/1990",
    "fecha_expedicion": "10/05/2024",   # ambigua: dia y mes <= 12
    "fecha_vencimiento": "25/07/2031",  # dia > 12: solo cabe una lectura
}
ESPERADO = {**base.ESPERADO, "fecha_nacimiento": "1990-01-01", "fecha_expedicion": "2024-05-10",
            "fecha_vencimiento": "2031-07-25"}
CAMPOS_FECHA = tuple(FECHAS_DOCUMENTO)

_DMA = re.compile(r"^(\d{1,2})[/.\- ](\d{1,2})[/.\- ](\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def normalizar_fecha(valor) -> str | None:
    """DD/MM/AAAA (separador / . - o espacio) -> AAAA-MM-DD. ISO valido se deja igual.
    Devuelve None si no es una fecha reconocible o no existe (p. ej. 31/02/2024)."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if m := _ISO.match(texto):
        anio, mes, dia = map(int, m.groups())
    elif m := _DMA.match(texto):
        dia, mes, anio = map(int, m.groups())
    else:
        return None
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


def _autotest_normalizar():
    casos = {"25/07/2031": "2031-07-25", "10/05/2024": "2024-05-10", "1/1/1990": "1990-01-01",
             "10.05.2024": "2024-05-10", "10-05-2024": "2024-05-10", "2024-05-10": "2024-05-10",
             "31/02/2024": None, "2024/05/10": None, "mayo 2024": None, None: None, 20240510: None}
    for entrada, esperado in casos.items():
        assert normalizar_fecha(entrada) == esperado, (entrada, normalizar_fecha(entrada), esperado)


def generar_imagenes_fechas():
    """Reutiliza el dibujo de prueba_ollama cambiando solo las fechas y la MRZ."""
    base.FILAS = [(et, FECHAS_DOCUMENTO.get({"Fecha de nacimiento / Date of birth": "fecha_nacimiento",
                                             "Fecha de expedicion / Date of issue": "fecha_expedicion",
                                             "Fecha de caducidad / Date of expiry": "fecha_vencimiento"}.get(et), va))
                  for et, va in base.FILAS]
    base.MRZ = (base._mrz("P<XXXEJEMPLO<PRUEBA<<ANA"), base._mrz("X1234567P0XXX9001017F3107251"))
    originales = base.generar_imagenes(AQUI / "imagenes_fechas")
    reescaladas = {}
    for nombre, ruta in originales.items():
        img = Image.open(ruta)
        destino = ruta.with_name(f"{ruta.stem}_1000px.jpg")
        if destino.exists():
            reescaladas[nombre] = destino
            continue
        img.resize((1000, round(img.height * 1000 / img.width)), Image.LANCZOS).save(destino, quality=85)
        reescaladas[nombre] = destino
    return reescaladas


def prompt_v2b() -> str:
    cuerpo = (AQUI / "prompts_borrador" / "extraccion_v2b.md").read_text(encoding="utf-8").split("---", 2)[2]
    ficha = configuracion.obtener("pasaporte")
    esquema = "\n".join(f"- {n}: {c.tipo.value}, {'obligatorio' if c.obligatorio else 'opcional'}"
                        for n, c in ficha.campos.items())
    return jinja2.Template(cuerpo).render(tipo_documental="pasaporte", esquema_campos=esquema,
                                          contenido="--- pagina_1 ---\n(sin texto extraido)").strip()


def evaluar(contenido: str) -> dict:
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as e:
        return {"json_valido": False, "error": str(e)}
    ext = datos.get("datos_extraidos") or {}
    fechas = {}
    for c in CAMPOS_FECHA:
        crudo = ext.get(c)
        norm = normalizar_fecha(crudo)
        fechas[c] = {"crudo": crudo, "tal_como_aparece": crudo == FECHAS_DOCUMENTO[c],
                     "normalizado": norm, "ok": norm == ESPERADO[c]}
    otros = {c: {"valor": ext.get(c), "ok": str(ext.get(c) or "").strip().upper() == e.upper()}
             for c, e in ESPERADO.items() if c not in CAMPOS_FECHA}
    return {
        "json_valido": True,
        "fechas_ok_tras_normalizar": sum(f["ok"] for f in fechas.values()),
        "fechas_tal_como_aparecen": sum(f["tal_como_aparece"] for f in fechas.values()),
        "aciertos_totales": sum(f["ok"] for f in fechas.values()) + sum(o["ok"] for o in otros.values()),
        "fechas": fechas,
        "otros": otros,
        "confianzas": sorted({v for v in (datos.get("nivel_confianza_por_campo") or {}).values()}, key=str),
        "evidencias": sorted({str(v) for v in (datos.get("evidencia_por_campo") or {}).values()}),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", default="qwen2.5vl:3b")
    p.add_argument("--sin-think", action="store_true")
    args = p.parse_args()

    _autotest_normalizar()
    imagenes = generar_imagenes_fechas()
    configuracion.cargar()
    prompt = prompt_v2b()

    carpeta = AQUI / "resultados" / (args.modelo.replace(":", "_") + "_fechas")
    (carpeta / "respuestas").mkdir(parents=True, exist_ok=True)
    (carpeta / "prompt_enviado.txt").write_text(prompt, encoding="utf-8")
    log_fichero = (carpeta / "log.txt").open("w", encoding="utf-8")

    def log(msg: str):
        linea = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linea, flush=True)
        log_fichero.write(linea + "\n")
        log_fichero.flush()

    log(f"Modelo {args.modelo} | prompt v2b | RAM libre inicial {ram_libre_gb():.2f} GB | autotest normalizar OK")
    vigilante = VigilanteRam(args.modelo, 1.0, log)
    vigilante.start()

    resumen = []
    for nombre, imagen in imagenes.items():
        for rep in (1, 2):
            log(f"{nombre}_1000px ejecucion {rep} ...")
            try:
                respuesta, segundos = llamar("http://localhost:11434", args.modelo, prompt, imagen, not args.sin_think)
            except Exception as e:  # noqa: BLE001 - spike
                log(f"ERROR {type(e).__name__}: {e}")
                resumen.append({"escenario": nombre, "ejecucion": rep, "error": str(e)})
                continue
            (carpeta / "respuestas" / f"{nombre}_1000px_{rep}.json").write_text(
                json.dumps(respuesta, ensure_ascii=False, indent=2), encoding="utf-8")
            fila = {"escenario": f"{nombre}_1000px", "ejecucion": rep, "segundos_total": round(segundos, 1),
                    **evaluar(respuesta.get("message", {}).get("content", ""))}
            resumen.append(fila)
            crudos = {c: f["crudo"] for c, f in fila.get("fechas", {}).items()}
            log(f"  {fila['segundos_total']} s | fechas ok tras normalizar {fila.get('fechas_ok_tras_normalizar')}/3 "
                f"| tal como aparecen {fila.get('fechas_tal_como_aparecen')}/3 | total {fila.get('aciertos_totales')}/7 "
                f"| crudo {crudos}")

    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Fin. RAM libre minima {vigilante.minimo:.2f} GB")


if __name__ == "__main__":
    main()
