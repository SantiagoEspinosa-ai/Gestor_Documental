"""
Evaluacion completa del motor IA con los fixtures de PERSONA_3 (fixtures/generados/, datos ficticios).
Compara cada campo con INDICE.md. NO es codigo del backend: no cambia el motor ni el enrutador.

Bloques (un modelo cada vez):
  1 - ruta "auto" (regla del enrutador) en todos los documentos + 3 casos de CLS-001 (tipo declarado equivocado).
  2 - ruta "vision" (modelo de vision forzado) en escaneado y foto.

Modos:
  lanzar   (en el equipo) arranca el contenedor del backend para un bloque y vigila la RAM: si baja de
           1 GB, descarga los modelos y para. Al terminar genera el informe.
  trabajar (dentro del contenedor) ejecuta los casos pendientes y guarda cada resultado al terminarlo.
  informe  regenera resultados/evaluacion/informe.md y resumen.json con lo que haya.

Uso (desde la raiz del repo, con Docker Desktop y Ollama en marcha):
  python docs/motor_ia/pruebas_ollama/evaluar_fixtures.py lanzar --bloque 1
  python docs/motor_ia/pruebas_ollama/evaluar_fixtures.py lanzar --bloque 2
  python docs/motor_ia/pruebas_ollama/evaluar_fixtures.py informe
Opciones: --casos sano,vencido (filtra; por defecto todos los de INDICE.md salvo duplicado, asi que los
fixtures _dificil entran solos), --solo <id> (un caso concreto), --repetir (vuelve a ejecutar los ya hechos).
Reanudable: los casos con resultado guardado se saltan; los que acabaron en excepcion se repiten.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent                 # docs/motor_ia/pruebas_ollama
# Raiz del repo en el equipo. En el contenedor el script esta en /evaluacion y las rutas llegan por parametro.
REPO = AQUI.parents[2] if len(AQUI.parents) > 2 else AQUI
SALIDA_POR_DEFECTO = AQUI / "resultados" / "evaluacion"
FIXTURES_POR_DEFECTO = REPO / "fixtures" / "generados"
OLLAMA_EQUIPO = "http://localhost:11434"
MODELOS = ("gemma4:e2b", "qwen2.5vl:3b")
UMBRAL_ABORTAR_GB = 1.0
MARGEN_GB = {1: 4.5, 2: 5.8}                           # RAM libre minima para arrancar cada bloque
FOLIO = "CLI-2026-000000"
CASOS_CLS = [  # (archivo, tipo declarado equivocado)
    ("credencial_elector_sano_digital.pdf", "pasaporte"),
    ("pasaporte_sano_foto.jpg", "credencial_elector"),
    ("comprobante_domicilio_sano_escaneado.pdf", "pasaporte"),
]
CRITERIOS = [  # (ruta, modalidad, minimo de aciertos sobre 51, bloquea)
    ("auto", "digital", 49, True),
    ("auto", "escaneado", 47, True),
    ("auto", "foto", 47, True),
    ("vision", "escaneado", 40, False),
    ("vision", "foto", 40, False),
]


# ------------------------------------------------------------------ INDICE.md y casos

def leer_indice(fixtures: Path, casos: set[str] | None = None) -> dict[str, dict]:
    """{archivo: {caso, tipo, modalidad, campos: {campo: valor ISO}}}, sin el caso duplicado."""
    documentos, actual = {}, None
    for linea in (fixtures / "INDICE.md").read_text(encoding="utf-8").splitlines():
        if m := re.match(r"^### (\S+) / (\S+)$", linea):
            actual = {"caso": m[1], "tipo": m[2], "campos": {}, "archivos": []}
        elif linea.startswith("## ") or linea.startswith("### Folio"):
            actual = None
        elif actual is None:
            continue
        elif "Archivos:" in linea:
            actual["archivos"] = re.findall(r"`([^`]+)`", linea.split("Archivos:")[1])
        elif m := re.match(r"^\| `(\w+)` \| (.+) \|$", linea):
            actual["campos"][m[1]] = m[2].strip()
        if actual is not None and actual["archivos"] and actual["caso"] != "duplicado":
            for archivo in actual["archivos"]:
                documentos[archivo] = actual
    salida = {}
    for archivo, d in documentos.items():
        if casos and d["caso"] not in casos:
            continue
        modalidad = re.search(r"_(digital|escaneado|foto)\.", archivo)[1]
        salida[archivo] = {"caso": d["caso"], "tipo": d["tipo"], "modalidad": modalidad, "campos": dict(d["campos"])}
    return salida


def casos_del_bloque(bloque: int, indice: dict[str, dict]) -> list[dict]:
    casos = []
    if bloque == 1:
        for archivo, d in sorted(indice.items()):
            casos.append({"id": f"auto__{Path(archivo).stem}", "ruta": "auto", "archivo": archivo,
                          "declarado": d["tipo"], "clasificacion_equivocada": False})
        for archivo, declarado in CASOS_CLS:
            if archivo in indice:
                casos.append({"id": f"cls__{Path(archivo).stem}__como_{declarado}", "ruta": "auto",
                              "archivo": archivo, "declarado": declarado, "clasificacion_equivocada": True})
    else:
        for archivo, d in sorted(indice.items()):
            if d["modalidad"] in ("escaneado", "foto"):
                casos.append({"id": f"vision__{Path(archivo).stem}", "ruta": "vision", "archivo": archivo,
                              "declarado": d["tipo"], "clasificacion_equivocada": False})
    return casos


def pendientes(casos: list[dict], salida: Path, repetir: bool, solo: str | None = None) -> list[dict]:
    if solo:
        casos = [c for c in casos if c["id"] == solo]
    if repetir:
        return casos
    hechos = set()
    for ruta in salida.glob("*.json"):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(datos, dict) and "medida" in datos and not datos["medida"].get("excepcion"):
            hechos.add(datos["medida"]["id"])
    return [c for c in casos if c["id"] not in hechos]


def normalizar(valor) -> str:
    plano = unicodedata.normalize("NFKD", "" if valor is None else str(valor)).encode("ascii", "ignore").decode()
    return " ".join(plano.upper().split())


# ------------------------------------------------------------------ modo trabajar (contenedor)

def trabajar(args) -> None:
    sys.path.insert(0, "/app")
    import hashlib

    from app.modulos.configuracion import servicio as configuracion
    from app.modulos.motor_ia.enrutador import crear_enrutador
    from app.modulos.motor_ia.proveedores.ollama import OllamaProvider
    from app.modulos.motor_ia.servicio import analizar
    from app.modulos.orquestador import servicio as orquestador
    from app.schemas.resultado import ReferenciaArchivoOriginal, ResultadoDocumento

    fixtures, salida = Path(args.fixtures), Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    indice = leer_indice(fixtures, set(args.casos.split(",")) if args.casos else None)
    lista = pendientes(casos_del_bloque(args.bloque, indice), salida, args.repetir, args.solo)
    print(f"PENDIENTES {len(lista)}", flush=True)

    descargas = {"antes_de_reintento": 0}
    if args.bloque == 2:
        OllamaProvider.usa_texto = staticmethod(lambda doc: False)   # ruta "vision": nunca texto
    else:
        original = OllamaProvider._extraer_vision

        def vision_con_descarga(self, doc, esquema_campos, prompt, motivo=None):
            if motivo:  # reintento con vision: libera antes el modelo de texto (un modelo cada vez)
                self._cliente.post(f"{self.base_url}/api/generate", json={"model": self.modelo_texto, "keep_alive": 0},
                                   timeout=60)
                descargas["antes_de_reintento"] += 1
            return original(self, doc, esquema_campos, prompt, motivo)

        OllamaProvider._extraer_vision = vision_con_descarga

    configuracion.cargar()
    enrutador = crear_enrutador()
    for caso in lista:
        print(f"INICIO {caso['id']}", flush=True)
        esperado = indice[caso["archivo"]]
        medida = {**caso, "caso": esperado["caso"], "tipo": esperado["tipo"], "modalidad_fixture": esperado["modalidad"]}
        inicio = time.perf_counter()
        try:
            contenido = (fixtures / caso["archivo"]).read_bytes()
            doc = orquestador.preparar(contenido, caso["archivo"], caso["declarado"])
            medida["segundos_preparar"] = round(time.perf_counter() - inicio, 1)
            medida["modalidad_detectada"] = doc.modalidad.value
            referencia = ReferenciaArchivoOriginal(nombre_archivo=caso["archivo"], ruta=f"local://{caso['archivo']}",
                                                   hash=hashlib.sha256(contenido).hexdigest())
            descargas_previas = descargas["antes_de_reintento"]
            analisis = analizar(doc, folio=FOLIO, referencia=referencia, enrutador=enrutador)
            r = analisis.resultado
            ResultadoDocumento.model_validate_json(r.model_dump_json())
            campos = {}
            if not caso["clasificacion_equivocada"]:
                for campo, valor in esperado["campos"].items():
                    extraido = r.datos_extraidos.get(campo)
                    campos[campo] = {"esperado": valor, "extraido": extraido, "ok": normalizar(extraido) == normalizar(valor)}
            medida.update({
                "segundos_total": round(time.perf_counter() - inicio, 1),
                "estado": r.estado_analisis.value,
                "tipo_detectado": r.tipo_documental_detectado,
                "confianza_clasificacion": r.confianza_clasificacion,
                "clasificacion_ok": r.tipo_documental_detectado == esperado["tipo"],
                "alertas": [a.codigo + (f"[{a.campo}]" if a.campo else "") for a in r.alertas_encontradas],
                "campos": campos,
                "aciertos": sum(c["ok"] for c in campos.values()),
                "total_campos": len(campos),
                "llamadas": [{"modelo": i.modelo, "entrada": i.entrada, "motivo": i.motivo, "segundos": i.segundos,
                              "tokens_entrada": i.tokens_entrada, "tokens_salida": i.tokens_salida,
                              "reintentos": i.reintentos, "lotes": i.lotes} for i in analisis.llamadas],
                "reintento_vision": any((i.motivo or "").startswith("reintento con vision") for i in analisis.llamadas),
                "descarga_texto_antes_de_reintento": descargas["antes_de_reintento"] > descargas_previas,
                "contrato_valido": True,
            })
            resultado = json.loads(r.model_dump_json())
        except Exception as e:  # noqa: BLE001 - se registra y se repite al reanudar
            medida.update({"excepcion": f"{type(e).__name__}: {e}", "segundos_total": round(time.perf_counter() - inicio, 1)})
            resultado = None
        temporal = salida / f"{caso['id']}.json.tmp"
        temporal.write_text(json.dumps({"medida": medida, "resultado": resultado}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        temporal.replace(salida / f"{caso['id']}.json")
        print(f"FIN {caso['id']} {medida.get('aciertos', '-')}/{medida.get('total_campos', '-')} "
              f"{medida.get('segundos_total')} s {medida.get('excepcion') or ''}", flush=True)


# ------------------------------------------------------------------ modo lanzar (equipo)

def ram_libre_gb() -> float | None:
    if os.name == "nt":
        import ctypes

        class _Memoria(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = _Memoria()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1024**3
    try:
        for linea in Path("/proc/meminfo").read_text().splitlines():
            if linea.startswith("MemAvailable:"):
                return int(linea.split()[1]) / 1024**2
    except OSError:
        pass
    return None


def descargar_modelos() -> None:
    for modelo in MODELOS:
        try:
            peticion = urllib.request.Request(f"{OLLAMA_EQUIPO}/api/generate", method="POST",
                                              data=json.dumps({"model": modelo, "keep_alive": 0}).encode(),
                                              headers={"Content-Type": "application/json"})
            urllib.request.urlopen(peticion, timeout=60).read()
        except OSError:
            pass


def lanzar(args) -> None:
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    indice = leer_indice(Path(args.fixtures), set(args.casos.split(",")) if args.casos else None)
    lista = pendientes(casos_del_bloque(args.bloque, indice), salida, args.repetir, args.solo)
    if not lista:
        print(f"Bloque {args.bloque}: no hay casos pendientes")
        generar_informe(salida)
        return
    descargar_modelos()
    time.sleep(5)
    libre = ram_libre_gb()
    if libre is not None and libre < MARGEN_GB[args.bloque]:
        print(f"Bloque {args.bloque}: RAM libre {libre:.2f} GB < margen {MARGEN_GB[args.bloque]} GB; "
              f"faltan {MARGEN_GB[args.bloque] - libre:.2f} GB. No se lanza.")
        return
    print(f"Bloque {args.bloque}: {len(lista)} casos pendientes; RAM libre {libre:.2f} GB", flush=True)
    comando = ["docker", "compose", "run", "--rm", "--no-deps",
               "-v", f"{Path(args.fixtures)}:/fixtures/generados:ro", "-v", f"{AQUI}:/evaluacion:ro",
               "-v", f"{salida}:/salida", "-e", "OLLAMA_BASE_URL=http://host.docker.internal:11434",
               "backend", "python", "/evaluacion/evaluar_fixtures.py", "trabajar", "--bloque", str(args.bloque),
               "--fixtures", "/fixtures/generados", "--salida", "/salida"]
    if args.casos:
        comando += ["--casos", args.casos]
    if args.repetir:
        comando.append("--repetir")
    if args.solo:
        comando += ["--solo", args.solo]
    proceso = subprocess.Popen(comando, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace")
    estado = {"caso": None, "abortado": False, "minimo_bloque": libre}
    ram_por_caso: dict[str, float] = {}

    def vigilar():
        while proceso.poll() is None:
            actual = ram_libre_gb()
            if actual is not None:
                estado["minimo_bloque"] = min(estado["minimo_bloque"], actual)
                if estado["caso"]:
                    ram_por_caso[estado["caso"]] = min(ram_por_caso.get(estado["caso"], actual), actual)
                if actual < UMBRAL_ABORTAR_GB:
                    estado["abortado"] = True
                    descargar_modelos()
                    proceso.kill()
                    return
            time.sleep(1)

    hilo = threading.Thread(target=vigilar, daemon=True)
    hilo.start()
    for linea in proceso.stdout:
        linea = linea.rstrip()
        if linea.startswith("INICIO "):
            estado["caso"] = linea.split(" ", 1)[1]
        elif linea.startswith(("FIN ", "PENDIENTES ")):
            print(linea, flush=True)
        elif linea.startswith("Traceback") or "Error" in linea:
            print(linea, flush=True)
    proceso.wait()
    hilo.join(timeout=5)
    descargar_modelos()
    ram = {}
    archivo_ram = salida / "ram.json"
    if archivo_ram.exists():
        ram = json.loads(archivo_ram.read_text(encoding="utf-8"))
    ram.setdefault("casos", {}).update({k: round(v, 2) for k, v in ram_por_caso.items()})
    ram.setdefault("bloques", {})[str(args.bloque)] = {"ram_libre_min_gb": round(estado["minimo_bloque"], 2),
                                                        "abortado_por_ram": estado["abortado"]}
    archivo_ram.write_text(json.dumps(ram, indent=2), encoding="utf-8")
    print(f"Bloque {args.bloque}: {'ABORTADO por RAM' if estado['abortado'] else 'terminado'}; "
          f"RAM libre minima {estado['minimo_bloque']:.2f} GB", flush=True)
    generar_informe(salida)


# ------------------------------------------------------------------ informe

def _pct(a: int, t: int) -> str:
    return f"{a}/{t} ({100 * a / t:.0f} %)" if t else "-"


def generar_informe(salida: Path) -> None:
    medidas = []
    for ruta in sorted(salida.glob("*.json")):
        if ruta.name in ("resumen.json", "ram.json"):
            continue
        medidas.append(json.loads(ruta.read_text(encoding="utf-8"))["medida"])
    ram = json.loads((salida / "ram.json").read_text(encoding="utf-8")) if (salida / "ram.json").exists() else {}
    normales = [m for m in medidas if not m.get("clasificacion_equivocada") and not m.get("excepcion")]
    cls = [m for m in medidas if m.get("clasificacion_equivocada")]
    lineas = ["# Evaluacion completa del motor IA con los fixtures", "",
              "Generado por `docs/motor_ia/pruebas_ollama/evaluar_fixtures.py`. Datos ficticios (fixtures de PERSONA_3).",
              "Verdad de referencia: `fixtures/generados/INDICE.md`.", ""]

    def grupo(ruta, modalidad=None, tipo=None):
        return [m for m in normales if m["ruta"] == ruta and (modalidad is None or m["modalidad_fixture"] == modalidad)
                and (tipo is None or m["tipo"] == tipo)]

    lineas += ["## Criterios de aprobado", "", "| Ruta | Modalidad | Aciertos | Minimo | Resultado |", "|---|---|---|---|---|"]
    for ruta, modalidad, minimo, bloquea in CRITERIOS:
        g = grupo(ruta, modalidad)
        a, t = sum(m["aciertos"] for m in g), sum(m["total_campos"] for m in g)
        if not g:
            veredicto = "pendiente"
        else:
            veredicto = ("APROBADO" if a >= minimo else "NO APROBADO") + ("" if bloquea else " (referencia)")
        lineas.append(f"| {ruta} | {modalidad} | {_pct(a, t)} | {minimo}/51 | {veredicto} |")
    auto = grupo("auto")
    clas_ok = sum(m["clasificacion_ok"] for m in auto)
    cls_ok = sum("CLS-001" in m.get("alertas", []) for m in cls)
    falsos_cls = sum("CLS-001" in m.get("alertas", []) for m in normales)
    errores_sys = sum(any(a.startswith(("SYS-001", "SYS-002")) for a in m.get("alertas", [])) for m in medidas)
    excepciones = [m for m in medidas if m.get("excepcion")]
    abortos = [b for b, d in ram.get("bloques", {}).items() if d.get("abortado_por_ram")]
    lineas += ["", "| Criterio | Valor | Minimo | Resultado |", "|---|---|---|---|",
               f"| Tipo detectado correcto (ruta auto) | {clas_ok}/{len(auto)} | 26/27 | "
               f"{'pendiente' if not auto else ('APROBADO' if clas_ok >= min(26, len(auto) - 1) else 'NO APROBADO')} |",
               f"| CLS-001 en los casos equivocados | {cls_ok}/{len(cls)} | 3/3 | "
               f"{'pendiente' if not cls else ('APROBADO' if cls_ok == len(cls) == 3 else 'NO APROBADO')} |",
               f"| CLS-001 en casos correctos (falsos positivos) | {falsos_cls} | 0 | {'APROBADO' if falsos_cls == 0 else 'NO APROBADO'} |",
               f"| Resultados con SYS-001 o SYS-002 | {errores_sys} | 0 | {'APROBADO' if errores_sys == 0 else 'NO APROBADO'} |",
               f"| Excepciones (resultado no valido) | {len(excepciones)} | 0 | {'APROBADO' if not excepciones else 'NO APROBADO'} |",
               f"| Abortos por RAM | {len(abortos)} | 0 | {'APROBADO' if not abortos else 'NO APROBADO'} |"]
    tiempos_auto = [m["segundos_total"] for m in auto]
    if tiempos_auto:
        media = sum(tiempos_auto) / len(tiempos_auto)
        lineas.append(f"| Tiempo medio por documento (ruta auto, informativo) | {media:.0f} s | <= 90 s | "
                      f"{'si' if media <= 90 else 'no'} |")

    lineas += ["", "## Aciertos por tipo, modalidad y ruta", "",
               "| Ruta | Tipo | Digital | Escaneado | Foto |", "|---|---|---|---|---|"]
    for ruta in ("auto", "vision"):
        for tipo in sorted({m["tipo"] for m in normales}):
            celdas = []
            for modalidad in ("digital", "escaneado", "foto"):
                g = grupo(ruta, modalidad, tipo)
                celdas.append(_pct(sum(m["aciertos"] for m in g), sum(m["total_campos"] for m in g)) if g else "-")
            if any(c != "-" for c in celdas):
                lineas.append(f"| {ruta} | {tipo} | " + " | ".join(celdas) + " |")

    fallos = [(m, c, v) for m in normales for c, v in m["campos"].items() if not v["ok"]]
    lineas += ["", "## Campos que fallan", ""]
    if fallos:
        lineas += ["| Ruta | Archivo | Campo | Esperado | Extraido |", "|---|---|---|---|---|"]
        lineas += [f"| {m['ruta']} | `{m['archivo']}` | `{c}` | {v['esperado']} | {v['extraido']} |" for m, c, v in fallos]
    else:
        lineas.append("Ninguno.")

    lineas += ["", "## Clasificacion con tipo declarado equivocado (CLS-001)", "",
               "| Archivo | Declarado | Detectado | Alertas |", "|---|---|---|---|"]
    lineas += [f"| `{m['archivo']}` | {m['declarado']} | {m.get('tipo_detectado')} | {', '.join(m.get('alertas', [])) or '-'} |"
               for m in cls] or ["| - | - | - | - |"]

    lineas += ["", "## Casos: tiempos, modelos, RAM y reintentos", "",
               "| Caso | Modalidad | Aciertos | Tiempo | Llamadas | Reintento con vision | RAM libre minima |",
               "|---|---|---|---|---|---|---|"]
    for m in sorted(medidas, key=lambda x: x["id"]):
        if m.get("excepcion"):
            lineas.append(f"| `{m['id']}` | {m.get('modalidad_fixture')} | EXCEPCION: {m['excepcion']} | "
                          f"{m.get('segundos_total')} s | - | - | {ram.get('casos', {}).get(m['id'], '-')} |")
            continue
        llamadas = "; ".join(f"{l['modelo']} ({l['entrada']}) {l['segundos']} s" for l in m["llamadas"])
        reintento = ("si" + (" (texto descargado antes)" if m.get("descarga_texto_antes_de_reintento") else "")) \
            if m.get("reintento_vision") else "no"
        aciertos = "-" if m.get("clasificacion_equivocada") else f"{m['aciertos']}/{m['total_campos']}"
        lineas.append(f"| `{m['id']}` | {m['modalidad_fixture']} | {aciertos} | {m['segundos_total']} s | {llamadas} | "
                      f"{reintento} | {ram.get('casos', {}).get(m['id'], '-')} GB |")
    lineas += ["", "## RAM por bloque", "", "| Bloque | RAM libre minima | Abortado por RAM |", "|---|---|---|"]
    lineas += [f"| {b} | {d['ram_libre_min_gb']} GB | {'si' if d['abortado_por_ram'] else 'no'} |"
               for b, d in sorted(ram.get("bloques", {}).items())] or ["| - | - | - |"]
    (salida / "informe.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (salida / "resumen.json").write_text(json.dumps({"medidas": medidas, "ram": ram}, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    print(f"Informe: {salida / 'informe.md'}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("modo", choices=["lanzar", "trabajar", "informe"])
    p.add_argument("--bloque", type=int, choices=[1, 2], default=1)
    p.add_argument("--casos", help="casos de INDICE.md separados por comas (p. ej. sano,dificil)")
    p.add_argument("--repetir", action="store_true")
    p.add_argument("--solo", help="id de un caso concreto (p. ej. cls__comprobante_domicilio_sano_escaneado__como_pasaporte)")
    p.add_argument("--fixtures", default=str(FIXTURES_POR_DEFECTO))
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))
    args = p.parse_args()
    {"lanzar": lanzar, "trabajar": trabajar, "informe": lambda a: generar_informe(Path(a.salida))}[args.modo](args)


if __name__ == "__main__":
    main()
