"""
Evaluacion completa del motor IA con los fixtures de PERSONA_3 (fixtures/generados/, datos ficticios).
Compara cada campo con INDICE.md. NO es codigo del backend: no cambia el motor ni el enrutador.

Bloques (un modelo cada vez):
  1 - nivel normal, ruta "auto" (regla del enrutador) + 3 casos de CLS-001 (tipo declarado equivocado).
  2 - nivel normal, ruta "vision" (modelo de vision forzado) en escaneado y foto.
  3 - fixtures de dificultad (dificil y extremo, seccion "Fixtures de dificultad" de INDICE.md), ruta "auto".
  4 - fixtures de dificultad, ruta "vision".
Cada campo queda como correcto, vacio (null) o incorrecto (con valor distinto del esperado: error
silencioso, que el reintento con vision no detecta porque solo mira los vacios).

Modos:
  lanzar   (en el equipo) arranca el contenedor del backend para un bloque y vigila la RAM: si baja de
           1 GB, descarga los modelos y para. Al terminar genera el informe.
  trabajar (dentro del contenedor) ejecuta los casos pendientes y guarda cada resultado al terminarlo.
  informe  regenera resultados/evaluacion/informe.md y resumen.json con lo que haya.
  indice   lista los documentos y casos de cada bloque leidos de INDICE.md, sin ejecutar modelos.

Uso (desde la raiz del repo, con Docker Desktop y Ollama en marcha):
  python docs/motor_ia/pruebas_ollama/evaluar_fixtures.py lanzar --bloque 1
  python docs/motor_ia/pruebas_ollama/evaluar_fixtures.py informe
Opciones: --casos sano,vencido (filtra por caso de INDICE.md; el duplicado nunca entra), --solo <id>
(un caso concreto), --repetir (vuelve a ejecutar los ya hechos).
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
# RAM libre minima para arrancar cada bloque. El 3 puede reintentar con vision (carga qwen tras descargar gemma).
MARGEN_GB = {1: 4.5, 2: 5.8, 3: 5.8, 4: 5.8}
FOLIO = "CLI-2026-000000"
NIVELES_DIFICULTAD = ("dificil", "extremo")
CASOS_CLS = [  # (archivo, tipo declarado equivocado)
    ("credencial_elector_sano_digital.pdf", "pasaporte"),
    ("pasaporte_sano_foto.jpg", "credencial_elector"),
    ("comprobante_domicilio_sano_escaneado.pdf", "pasaporte"),
]
CRITERIOS = [  # nivel normal: (ruta, modalidad, minimo de aciertos sobre 51, bloquea)
    ("auto", "digital", 49, True),
    ("auto", "escaneado", 47, True),
    ("auto", "foto", 47, True),
    ("vision", "escaneado", 40, False),
    ("vision", "foto", 40, False),
]
# Fixtures de dificultad (34 campos por nivel): (nivel, ruta, metrica, comparacion, umbral, bloquea)
CRITERIOS_DIFICULTAD = [
    ("dificil", "auto", "correctos", ">=", 26, True),
    ("dificil", "auto", "incorrectos", "<=", 3, True),
    ("dificil", "auto", "tipo_correcto", ">=", 6, True),
    ("extremo", "auto", "incorrectos", "<=", 7, True),
    ("extremo", "auto", "tipo_correcto", ">=", 4, False),
]


# ------------------------------------------------------------------ INDICE.md y casos

def leer_indice(fixtures: Path, casos: set[str] | None = None) -> dict[str, dict]:
    """{archivo: {caso, tipo, modalidad, nivel, campos: {campo: valor ISO}}}, sin el caso duplicado.
    Nivel normal: secciones '### <caso> / <tipo>'. Dificil y extremo: seccion '## Fixtures de dificultad'
    (tabla de ficheros y '### Valores esperados: <tipo>', que son los del caso sano)."""
    documentos, actual, en_dificultad = {}, None, False
    dificultad: dict[str, dict] = {}
    valores_dificultad: dict[str, dict] = {}
    for linea in (fixtures / "INDICE.md").read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            en_dificultad, actual = linea.strip() == "## Fixtures de dificultad", None
            continue
        if en_dificultad:
            if m := re.match(r"^\| `([^`]+)` \| (\w+) \| (escaneado|foto) \| (dificil|extremo) \|", linea):
                dificultad[m[1]] = {"tipo": m[2], "modalidad": m[3], "nivel": m[4]}
            elif m := re.match(r"^### Valores esperados: (\w+)$", linea):
                actual = valores_dificultad.setdefault(m[1], {})
            elif actual is not None and (m := re.match(r"^\| `(\w+)` \| (.+) \|$", linea)):
                actual[m[1]] = m[2].strip()
            continue
        if m := re.match(r"^### (\S+) / (\S+)$", linea):
            actual = {"caso": m[1], "tipo": m[2], "campos": {}, "archivos": []}
        elif linea.startswith("### "):
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
        salida[archivo] = {"caso": d["caso"], "tipo": d["tipo"], "modalidad": modalidad, "nivel": "normal",
                           "campos": dict(d["campos"])}
    for archivo, d in dificultad.items():
        if casos and "sano" not in casos:
            continue
        salida[archivo] = {"caso": "sano", **d, "campos": dict(valores_dificultad.get(d["tipo"], {}))}
    return salida


def casos_del_bloque(bloque: int, indice: dict[str, dict]) -> list[dict]:
    normales = {a: d for a, d in indice.items() if d["nivel"] == "normal"}
    dificiles = {a: d for a, d in indice.items() if d["nivel"] in NIVELES_DIFICULTAD}
    casos = []
    if bloque == 1:
        for archivo, d in sorted(normales.items()):
            casos.append({"id": f"auto__{Path(archivo).stem}", "ruta": "auto", "archivo": archivo,
                          "declarado": d["tipo"], "clasificacion_equivocada": False})
        for archivo, declarado in CASOS_CLS:
            if archivo in normales:
                casos.append({"id": f"cls__{Path(archivo).stem}__como_{declarado}", "ruta": "auto",
                              "archivo": archivo, "declarado": declarado, "clasificacion_equivocada": True})
    elif bloque == 2:
        for archivo, d in sorted(normales.items()):
            if d["modalidad"] in ("escaneado", "foto"):
                casos.append({"id": f"vision__{Path(archivo).stem}", "ruta": "vision", "archivo": archivo,
                              "declarado": d["tipo"], "clasificacion_equivocada": False})
    else:
        ruta = "auto" if bloque == 3 else "vision"
        for archivo, d in sorted(dificiles.items()):
            casos.append({"id": f"{ruta}__{Path(archivo).stem}", "ruta": ruta, "archivo": archivo,
                          "declarado": d["tipo"], "clasificacion_equivocada": False})
    return casos


def pendientes(casos: list[dict], salida: Path, repetir: bool, solo: str | None = None) -> list[dict]:
    if solo:
        solos = set(solo.split(","))
        casos = [c for c in casos if c["id"] in solos]
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


def estado_campo(esperado, extraido) -> str:
    """correcto | vacio (null) | incorrecto (con valor distinto del esperado: error silencioso)."""
    if extraido is None or normalizar(extraido) == "":
        return "vacio"
    return "correcto" if normalizar(extraido) == normalizar(esperado) else "incorrecto"


def comparar_campos(esperados: dict, extraidos: dict) -> dict:
    return {campo: {"esperado": valor, "extraido": extraidos.get(campo),
                    "estado": estado_campo(valor, extraidos.get(campo)),
                    "ok": estado_campo(valor, extraidos.get(campo)) == "correcto"}
            for campo, valor in esperados.items()}


# ------------------------------------------------------------------ modo trabajar (contenedor)

def trabajar(args) -> None:
    sys.path.insert(0, "/app")
    import hashlib

    import app.modulos.motor_ia.servicio as servicio_motor
    from app.modulos.configuracion import servicio as configuracion
    from app.modulos.motor_ia.enrutador import crear_enrutador
    from app.modulos.motor_ia.proveedores.ollama import OllamaProvider
    from app.modulos.orquestador import servicio as orquestador
    from app.schemas.resultado import ReferenciaArchivoOriginal, ResultadoDocumento

    fixtures, salida = Path(args.fixtures), Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    indice = leer_indice(fixtures, set(args.casos.split(",")) if args.casos else None)
    lista = pendientes(casos_del_bloque(args.bloque, indice), salida, args.repetir, args.solo)
    print(f"PENDIENTES {len(lista)}", flush=True)

    descargas = {"antes_de_reintento": 0, "cambios_de_modelo": 0}
    antes_del_reintento: dict = {}
    ultimo_modelo = {"nombre": None}
    original_chat = OllamaProvider._chat

    def chat_un_modelo_cada_vez(self, info, mensajes, n_imagenes):
        # Un modelo cada vez: si la peticion va a otro modelo, descarga antes el anterior (keep_alive 0).
        anterior = ultimo_modelo["nombre"]
        if anterior and anterior != info.modelo:
            self._cliente.post(f"{self.base_url}/api/generate", json={"model": anterior, "keep_alive": 0}, timeout=60)
            descargas["cambios_de_modelo"] += 1
            if (info.motivo or "").startswith("reintento con vision"):
                descargas["antes_de_reintento"] += 1
        ultimo_modelo["nombre"] = info.modelo
        return original_chat(self, info, mensajes, n_imagenes)

    OllamaProvider._chat = chat_un_modelo_cada_vez
    if args.bloque in (2, 4):
        OllamaProvider.usa_texto = staticmethod(lambda doc: False)   # ruta "vision": nunca texto
    else:
        original_reintento = servicio_motor._reintento_vision

        def reintento_con_captura(ctx, proveedor, doc, esquema, prompt, extraccion, hay_cls_001):
            antes_del_reintento["datos"] = dict(extraccion.datos_extraidos)   # resultado con texto, antes de vision
            return original_reintento(ctx, proveedor, doc, esquema, prompt, extraccion, hay_cls_001)

        servicio_motor._reintento_vision = reintento_con_captura

    configuracion.cargar()
    enrutador = crear_enrutador()
    for caso in lista:
        print(f"INICIO {caso['id']}", flush=True)
        esperado = indice[caso["archivo"]]
        ficha = configuracion.obtener(esperado["tipo"])
        medida = {**caso, "caso": esperado["caso"], "tipo": esperado["tipo"], "modalidad_fixture": esperado["modalidad"],
                  "nivel": esperado["nivel"], "obligatorios": [c for c, d in ficha.campos.items() if d.obligatorio]}
        antes_del_reintento.clear()
        inicio = time.perf_counter()
        try:
            contenido = (fixtures / caso["archivo"]).read_bytes()
            doc = orquestador.preparar(contenido, caso["archivo"], caso["declarado"])
            medida["segundos_preparar"] = round(time.perf_counter() - inicio, 1)
            medida["modalidad_detectada"] = doc.modalidad.value
            medida["caracteres_texto"] = sum(len("".join((p.texto or "").split())) for p in doc.paginas)
            referencia = ReferenciaArchivoOriginal(nombre_archivo=caso["archivo"], ruta=f"local://{caso['archivo']}",
                                                   hash=hashlib.sha256(contenido).hexdigest())
            descargas_previas = descargas["antes_de_reintento"]
            # Como orquestador.procesar_documento: la MRZ la verifica y completa el orquestador (spec, seccion 11)
            from app.modulos.orquestador.completar_mrz import completar_sexo, verificacion_mrz
            mrz = verificacion_mrz(doc)
            analisis = servicio_motor.analizar(doc, folio=FOLIO, referencia=referencia, enrutador=enrutador, mrz=mrz)
            r = analisis.resultado
            if r.datos_extraidos:
                r = completar_sexo(r, doc, configuracion.obtener(caso["declarado"]), mrz)
            ResultadoDocumento.model_validate_json(r.model_dump_json())
            campos = {} if caso["clasificacion_equivocada"] else comparar_campos(esperado["campos"], r.datos_extraidos)
            reintento = any((i.motivo or "").startswith("reintento con vision") for i in analisis.llamadas)
            medida.update({
                "segundos_total": round(time.perf_counter() - inicio, 1),
                "estado": r.estado_analisis.value,
                "tipo_detectado": r.tipo_documental_detectado,
                "confianza_clasificacion": r.confianza_clasificacion,
                "clasificacion_ok": r.tipo_documental_detectado == esperado["tipo"],
                "alertas": [a.codigo + (f"[{a.campo}]" if a.campo else "") for a in r.alertas_encontradas],
                "campos": campos,
                "aciertos": sum(c["estado"] == "correcto" for c in campos.values()),
                "vacios": sum(c["estado"] == "vacio" for c in campos.values()),
                "incorrectos": sum(c["estado"] == "incorrecto" for c in campos.values()),
                "total_campos": len(campos),
                "llamadas": [{"modelo": i.modelo, "entrada": i.entrada, "motivo": i.motivo, "segundos": i.segundos,
                              "tokens_entrada": i.tokens_entrada, "tokens_salida": i.tokens_salida,
                              "reintentos": i.reintentos, "lotes": i.lotes} for i in analisis.llamadas],
                "reintento_vision": reintento,
                "uso_vision": any(i.entrada == "vision" for i in analisis.llamadas),
                "motivos_vision": [i.motivo for i in analisis.llamadas if i.entrada == "vision" and i.motivo],
                "descarga_texto_antes_de_reintento": descargas["antes_de_reintento"] > descargas_previas,
                "contrato_valido": True,
            })
            if reintento and "datos" in antes_del_reintento and not caso["clasificacion_equivocada"]:
                antes = comparar_campos(esperado["campos"], antes_del_reintento["datos"])
                medida["antes_del_reintento"] = {
                    "aciertos": sum(c["estado"] == "correcto" for c in antes.values()),
                    "vacios": sum(c["estado"] == "vacio" for c in antes.values()),
                    "incorrectos": sum(c["estado"] == "incorrecto" for c in antes.values()),
                    "obligatorios_vacios": sum(antes[c]["estado"] == "vacio" for c in medida["obligatorios"] if c in antes),
                }
            resultado = json.loads(r.model_dump_json())
        except Exception as e:  # noqa: BLE001 - se registra y se repite al reanudar
            medida.update({"excepcion": f"{type(e).__name__}: {e}", "segundos_total": round(time.perf_counter() - inicio, 1)})
            resultado = None
        temporal = salida / f"{caso['id']}.json.tmp"
        temporal.write_text(json.dumps({"medida": medida, "resultado": resultado}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        temporal.replace(salida / f"{caso['id']}.json")
        print(f"FIN {caso['id']} {medida.get('aciertos', '-')}/{medida.get('total_campos', '-')} "
              f"(vacios {medida.get('vacios', '-')}, incorrectos {medida.get('incorrectos', '-')}) "
              f"{medida.get('segundos_total')} s {'reintento vision ' if medida.get('reintento_vision') else ''}"
              f"{medida.get('excepcion') or ''}", flush=True)


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
    contenedor = f"evaluacion_bloque{args.bloque}_{int(time.time())}"
    comando = ["docker", "compose", "run", "--rm", "--no-deps", "--name", contenedor,
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
                    subprocess.run(["docker", "stop", "-t", "5", contenedor], capture_output=True, timeout=120)
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


def _cumple(valor: int, comparacion: str, umbral: int) -> bool:
    return valor >= umbral if comparacion == ">=" else valor <= umbral


def generar_informe(salida: Path) -> None:
    medidas = []
    for ruta in sorted(salida.glob("*.json")):
        if ruta.name in ("resumen.json", "ram.json"):
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        version = ((datos.get("resultado") or {}).get("fecha_y_modelo_utilizado") or {}).get("version_prompt") or ""
        medidas.append({**datos["medida"], "version_extraccion": version.rpartition("@")[2] or "?"})
    for m in medidas:  # resultados anteriores a los niveles de dificultad
        m.setdefault("nivel", "normal")
        for c in m.get("campos", {}).values():
            c.setdefault("estado", estado_campo(c["esperado"], c["extraido"]))
        m.setdefault("vacios", sum(c["estado"] == "vacio" for c in m.get("campos", {}).values()))
        m.setdefault("incorrectos", sum(c["estado"] == "incorrecto" for c in m.get("campos", {}).values()))
    ram = json.loads((salida / "ram.json").read_text(encoding="utf-8")) if (salida / "ram.json").exists() else {}
    validas = [m for m in medidas if not m.get("excepcion")]
    normales = [m for m in validas if not m.get("clasificacion_equivocada") and m["nivel"] == "normal"]
    dificiles = [m for m in validas if m["nivel"] in NIVELES_DIFICULTAD]
    cls = [m for m in medidas if m.get("clasificacion_equivocada")]
    lineas = ["# Evaluacion completa del motor IA con los fixtures", "",
              "Generado por `docs/motor_ia/pruebas_ollama/evaluar_fixtures.py`. Datos ficticios (fixtures de PERSONA_3).",
              "Verdad de referencia: `fixtures/generados/INDICE.md`. Campo incorrecto = con valor distinto del",
              "esperado (error silencioso); vacio = null.", ""]

    def grupo(conjunto, ruta, modalidad=None, tipo=None, nivel=None):
        return [m for m in conjunto if m["ruta"] == ruta and (modalidad is None or m["modalidad_fixture"] == modalidad)
                and (tipo is None or m["tipo"] == tipo) and (nivel is None or m["nivel"] == nivel)]

    def suma(g, clave):
        return sum(m.get(clave, 0) for m in g)

    lineas += ["## Nivel normal: criterios de aprobado", "",
               "| Ruta | Modalidad | Aciertos | Vacios | Incorrectos | Minimo | Resultado |", "|---|---|---|---|---|---|---|"]
    for ruta, modalidad, minimo, bloquea in CRITERIOS:
        g = grupo(normales, ruta, modalidad)
        a, t = suma(g, "aciertos"), suma(g, "total_campos")
        veredicto = "pendiente" if not g else ("APROBADO" if a >= minimo else "NO APROBADO") + ("" if bloquea else " (referencia)")
        lineas.append(f"| {ruta} | {modalidad} | {_pct(a, t)} | {suma(g, 'vacios')} | {suma(g, 'incorrectos')} | "
                      f"{minimo}/51 | {veredicto} |")
    auto = grupo(normales, "auto")
    clas_ok = sum(m["clasificacion_ok"] for m in auto)
    cls_ok = sum("CLS-001" in m.get("alertas", []) for m in cls)
    falsos_cls = sum("CLS-001" in m.get("alertas", []) for m in normales + dificiles)
    errores_sys = sum(any(a.startswith(("SYS-001", "SYS-002")) for a in m.get("alertas", [])) for m in validas)
    excepciones = [m for m in medidas if m.get("excepcion")]
    abortos = [b for b, d in ram.get("bloques", {}).items() if d.get("abortado_por_ram")]
    lineas += ["", "| Criterio | Valor | Minimo | Resultado |", "|---|---|---|---|",
               f"| Tipo detectado correcto (normal, ruta auto) | {clas_ok}/{len(auto)} | 26/27 | "
               f"{'pendiente' if not auto else ('APROBADO' if clas_ok >= min(26, len(auto) - 1) else 'NO APROBADO')} |",
               f"| CLS-001 en los casos equivocados | {cls_ok}/{len(cls)} | 3/3 | "
               f"{'pendiente' if not cls else ('APROBADO' if cls_ok == len(cls) == 3 else 'NO APROBADO')} |",
               f"| CLS-001 en casos correctos (falsos positivos) | {falsos_cls} | 0 | {'APROBADO' if falsos_cls == 0 else 'NO APROBADO'} |",
               f"| Resultados con SYS-001 o SYS-002 (todos los bloques) | {errores_sys} | 0 | {'APROBADO' if errores_sys == 0 else 'NO APROBADO'} |",
               f"| Excepciones (resultado no valido) | {len(excepciones)} | 0 | {'APROBADO' if not excepciones else 'NO APROBADO'} |",
               f"| Abortos por RAM | {len(abortos)} | 0 | {'APROBADO' if not abortos else 'NO APROBADO'} |"]
    tiempos_auto = [m["segundos_total"] for m in auto]
    if tiempos_auto:
        media = sum(tiempos_auto) / len(tiempos_auto)
        lineas.append(f"| Tiempo medio por documento (normal, ruta auto, informativo) | {media:.0f} s | <= 90 s | "
                      f"{'si' if media <= 90 else 'no'} |")

    lineas += ["", "## Nivel normal: aciertos por tipo, modalidad y ruta", "",
               "| Ruta | Tipo | Digital | Escaneado | Foto |", "|---|---|---|---|---|"]
    for ruta in ("auto", "vision"):
        for tipo in sorted({m["tipo"] for m in normales}):
            celdas = []
            for modalidad in ("digital", "escaneado", "foto"):
                g = grupo(normales, ruta, modalidad, tipo)
                celdas.append(_pct(suma(g, "aciertos"), suma(g, "total_campos")) if g else "-")
            if any(c != "-" for c in celdas):
                lineas.append(f"| {ruta} | {tipo} | " + " | ".join(celdas) + " |")

    # --- Fixtures de dificultad ---
    lineas += ["", "## Fixtures de dificultad: criterios de aprobado", ""]
    if dificiles or True:
        lineas += ["| Nivel | Ruta | Metrica | Valor | Criterio | Resultado |", "|---|---|---|---|---|---|"]
        for nivel, ruta, metrica, comparacion, umbral, bloquea in CRITERIOS_DIFICULTAD:
            g = grupo(dificiles, ruta, nivel=nivel)
            if metrica == "tipo_correcto":
                valor, total = sum(m["clasificacion_ok"] for m in g), len(g)
            else:
                valor, total = suma(g, "aciertos" if metrica == "correctos" else metrica), suma(g, "total_campos")
            veredicto = "pendiente" if not g else ("APROBADO" if _cumple(valor, comparacion, umbral) else "NO APROBADO") \
                + ("" if bloquea else " (referencia)")
            lineas.append(f"| {nivel} | {ruta} | {metrica} | {valor}/{total} | {comparacion} {umbral} | {veredicto} |")
        # Mitigacion: en extremo/auto, si el texto deja la mitad o mas de los obligatorios vacios, debe reintentar
        g = grupo(dificiles, "auto", nivel="extremo")
        candidatos = [m for m in g if m.get("antes_del_reintento", {}).get("obligatorios_vacios", 0) * 2 >= len(m["obligatorios"])
                      or (not m.get("reintento_vision") and sum(m["campos"][c]["estado"] == "vacio" for c in m["obligatorios"]
                                                                if c in m["campos"]) * 2 >= len(m["obligatorios"]))]
        sin_reintento = [m["id"] for m in candidatos if not m.get("reintento_vision")]
        veredicto = "pendiente" if not g else ("APROBADO" if not sin_reintento else "NO APROBADO")
        lineas.append(f"| extremo | auto | reintento si >= la mitad de obligatorios vacios | "
                      f"{len(candidatos) - len(sin_reintento)}/{len(candidatos)} | todos | {veredicto} |")

    lineas += ["", "## Fixtures de dificultad: correctos, vacios e incorrectos", "",
               "| Nivel | Ruta | Modalidad | Correctos | Vacios | Incorrectos | Reintentos con vision | Usan vision |",
               "|---|---|---|---|---|---|---|---|"]
    for nivel in NIVELES_DIFICULTAD:
        for ruta in ("auto", "vision"):
            for modalidad in ("escaneado", "foto"):
                g = grupo(dificiles, ruta, modalidad, nivel=nivel)
                if g:
                    lineas.append(f"| {nivel} | {ruta} | {modalidad} | {_pct(suma(g, 'aciertos'), suma(g, 'total_campos'))} | "
                                  f"{suma(g, 'vacios')} | {suma(g, 'incorrectos')} | {sum(m.get('reintento_vision', False) for m in g)}/{len(g)} | "
                                  f"{sum(m.get('uso_vision', False) for m in g)}/{len(g)} |")
    for ruta in ("auto", "vision"):
        por_version: dict[str, list[str]] = {}
        for m in grupo(dificiles, ruta):
            por_version.setdefault(m["version_extraccion"], []).append(m["id"])
        if len(por_version) > 1:   # resultados de distintas ejecuciones: se deja como referencia
            lineas += ["", f"**Nota: la ruta `{ruta}` mezcla versiones del prompt de extraccion** (resultados de "
                       "ejecuciones distintas; se deja como referencia):"]
            lineas += [f"- `extraccion_{v}`: {len(ids)} casos" + (f" ({', '.join(f'`{i}`' for i in ids)})" if len(ids) <= 4 else "")
                       for v, ids in sorted(por_version.items())]
    con_reintento = [m for m in dificiles if m.get("reintento_vision") and m.get("antes_del_reintento")]
    lineas += ["", "Reintentos con vision (resultado con texto antes del reintento -> resultado final):", ""]
    if con_reintento:
        lineas += ["| Caso | Antes: correctos / vacios / incorrectos | Despues: correctos / vacios / incorrectos |",
                   "|---|---|---|"]
        lineas += [f"| `{m['id']}` | {m['antes_del_reintento']['aciertos']} / {m['antes_del_reintento']['vacios']} / "
                   f"{m['antes_del_reintento']['incorrectos']} | {m['aciertos']} / {m['vacios']} / {m['incorrectos']} |"
                   for m in con_reintento]
    else:
        lineas.append("Ninguno.")

    fallos = [(m, c, v) for m in normales + dificiles for c, v in m["campos"].items() if v["estado"] != "correcto"]
    lineas += ["", "## Campos que fallan (todos los bloques)", ""]
    if fallos:
        lineas += ["| Ruta | Nivel | Archivo | Campo | Estado | Esperado | Extraido |", "|---|---|---|---|---|---|---|"]
        lineas += [f"| {m['ruta']} | {m['nivel']} | `{m['archivo']}` | `{c}` | {v['estado']} | {v['esperado']} | {v['extraido']} |"
                   for m, c, v in sorted(fallos, key=lambda x: (x[0]["nivel"], x[0]["id"], x[1]))]
    else:
        lineas.append("Ninguno.")

    lineas += ["", "## Clasificacion con tipo declarado equivocado (CLS-001)", "",
               "| Archivo | Declarado | Detectado | Alertas |", "|---|---|---|---|"]
    lineas += [f"| `{m['archivo']}` | {m['declarado']} | {m.get('tipo_detectado')} | {', '.join(m.get('alertas', [])) or '-'} |"
               for m in cls] or ["| - | - | - | - |"]

    lineas += ["", "## Casos: tiempos, modelos, RAM y reintentos", "",
               "| Caso | Nivel | Modalidad | Correctos | Vacios | Incorrectos | Tiempo | Llamadas | Vision (motivo) | RAM libre minima |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for m in sorted(medidas, key=lambda x: (x["nivel"], x["id"])):
        if m.get("excepcion"):
            lineas.append(f"| `{m['id']}` | {m['nivel']} | {m.get('modalidad_fixture')} | EXCEPCION: {m['excepcion']} | - | - | "
                          f"{m.get('segundos_total')} s | - | - | {ram.get('casos', {}).get(m['id'], '-')} |")
            continue
        llamadas = "; ".join(f"{l['modelo']} ({l['entrada']}) {l['segundos']} s" for l in m["llamadas"])
        reintento = "; ".join(m.get("motivos_vision") or []) or ("si (sin texto suficiente)" if m.get("uso_vision") else "no")
        vacio = m.get("clasificacion_equivocada")
        lineas.append(f"| `{m['id']}` | {m['nivel']} | {m['modalidad_fixture']} | "
                      f"{'-' if vacio else str(m['aciertos']) + '/' + str(m['total_campos'])} | {'-' if vacio else m['vacios']} | "
                      f"{'-' if vacio else m['incorrectos']} | {m['segundos_total']} s | {llamadas} | {reintento} | "
                      f"{ram.get('casos', {}).get(m['id'], '-')} GB |")
    lineas += ["", "## RAM por bloque", "", "| Bloque | RAM libre minima | Abortado por RAM |", "|---|---|---|"]
    lineas += [f"| {b} | {d['ram_libre_min_gb']} GB | {'si' if d['abortado_por_ram'] else 'no'} |"
               for b, d in sorted(ram.get("bloques", {}).items())] or ["| - | - | - |"]
    (salida / "informe.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (salida / "resumen.json").write_text(json.dumps({"medidas": medidas, "ram": ram}, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    print(f"Informe: {salida / 'informe.md'}", flush=True)


def listar_indice(args) -> None:
    indice = leer_indice(Path(args.fixtures), set(args.casos.split(",")) if args.casos else None)
    for nivel in ("normal", *NIVELES_DIFICULTAD):
        docs = {a: d for a, d in indice.items() if d["nivel"] == nivel}
        print(f"nivel {nivel}: {len(docs)} documentos, {sum(len(d['campos']) for d in docs.values())} campos")
    for bloque in (1, 2, 3, 4):
        print(f"bloque {bloque}: {len(casos_del_bloque(bloque, indice))} casos")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("modo", choices=["lanzar", "trabajar", "informe", "indice"])
    p.add_argument("--bloque", type=int, choices=[1, 2, 3, 4], default=1)
    p.add_argument("--casos", help="casos de INDICE.md separados por comas (p. ej. sano,vencido)")
    p.add_argument("--repetir", action="store_true")
    p.add_argument("--solo", help="ids de casos concretos separados por comas (p. ej. cls__comprobante_domicilio_sano_escaneado__como_pasaporte)")
    p.add_argument("--fixtures", default=str(FIXTURES_POR_DEFECTO))
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))
    args = p.parse_args()
    {"lanzar": lanzar, "trabajar": trabajar, "informe": lambda a: generar_informe(Path(a.salida)),
     "indice": listar_indice}[args.modo](args)


if __name__ == "__main__":
    main()
