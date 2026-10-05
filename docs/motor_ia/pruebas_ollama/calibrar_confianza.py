"""
Calibracion de la confianza calculada por el codigo (ADR-007) sin llamar al modelo y sin cambiar los umbrales.

  A - Valores correctos (los de INDICE.md) en el texto de cada fixture y especimen: cuantos campos quedarian por
      debajo de `confianza_minima_campo` aunque la extraccion fuera perfecta (VAL-002 falsos) y cuantas
      clasificaciones por debajo de `confianza_minima_clasificacion` (CLS-002 falsos).
  B - Valores extraidos en la evaluacion (resultados/evaluacion/*.json): si la confianza separa los campos correctos
      de los incorrectos (los incorrectos deberian quedar por debajo del minimo).

Datos ficticios (fixtures y especimenes de PERSONA_3). Uso, desde la raiz del repo (contenedor del backend):

  MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures:ro" \\
    -v "<repo>/docs/motor_ia/pruebas_ollama:/evaluacion" backend python /evaluacion/calibrar_confianza.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "/app")

from app.modulos.configuracion import servicio as configuracion  # noqa: E402
from app.modulos.configuracion.servicio import TipoCampo  # noqa: E402
from app.modulos.motor_ia.confianza import (  # noqa: E402
    VerificacionMrz,
    confianza_clasificacion,
    confianzas_de_campos,
    texto_del_documento,
)
from app.modulos.orquestador import servicio as orquestador  # noqa: E402

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from evaluar_fixtures import leer_indice  # noqa: E402

FIXTURES = Path("/fixtures/generados")
ESPECIMENES = Path("/fixtures/especimenes")
EVALUACION = AQUI / "resultados" / "evaluacion"
SALIDA = AQUI / "resultados" / "calibracion"


def verificacion_mrz(doc) -> VerificacionMrz | None:
    for pagina in doc.paginas:
        if (mrz := orquestador.buscar_mrz(pagina.texto)) is not None:
            return VerificacionMrz(mrz.numero_documento, mrz.fecha_nacimiento, mrz.fecha_vencimiento, mrz.sexo,
                                   orquestador.validar_digitos(mrz))
    return None


def tipar(valores: dict, ficha) -> dict:
    """Valores de INDICE.md (texto) con el tipo que tendria la extraccion: anio -> entero."""
    salida = {}
    for campo, valor in valores.items():
        if campo in ficha.campos and ficha.campos[campo].tipo is TipoCampo.anio and str(valor).isdigit():
            salida[campo] = int(valor)
        else:
            salida[campo] = valor
    return salida


_cache: dict[str, tuple[object, str, VerificacionMrz | None]] = {}


def preparado(ruta: Path, declarado: str):
    if ruta.name not in _cache:
        doc = orquestador.preparar(ruta.read_bytes(), ruta.name, declarado)
        _cache[ruta.name] = (doc, texto_del_documento(doc.paginas), verificacion_mrz(doc))
    return _cache[ruta.name]


def analisis_a(indice: dict) -> list[dict]:
    filas = []
    sano = {d["tipo"]: d["campos"] for d in indice.values() if d["caso"] == "sano" and d["nivel"] == "normal"}
    documentos = [(FIXTURES / a, d["tipo"], d["nivel"], d["campos"]) for a, d in indice.items()]
    documentos += [(r, r.name.split("_sano_")[0], "especimen", sano[r.name.split("_sano_")[0]])
                   for r in sorted(ESPECIMENES.glob("*.jpg"))]
    for ruta, tipo, nivel, esperados in documentos:
        ficha = configuracion.obtener(tipo)
        doc, texto, mrz = preparado(ruta, tipo)
        valores = tipar(esperados, ficha)
        confianzas = confianzas_de_campos(valores, ficha, texto, mrz if tipo == "pasaporte" else None)
        filas.append({"archivo": ruta.name, "tipo": tipo, "nivel": nivel,
                      "modalidad": doc.modalidad.value, "caracteres": len(texto.replace("\n", "")),
                      "clasificacion": confianza_clasificacion(ficha, texto),
                      "minimo_clasificacion": ficha.confianza_minima_clasificacion,
                      "minimo_campo": ficha.confianza_minima_campo,
                      "campos": {c: confianzas[c] for c in valores if c in confianzas}})
    return filas


def analisis_b() -> list[dict]:
    filas = []
    for ruta in sorted(EVALUACION.glob("*.json")):
        if ruta.name in ("ram.json", "resumen.json"):
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        m, r = datos["medida"], datos.get("resultado") or {}
        if m.get("excepcion") or not r:
            continue
        ficha = configuracion.obtener(m["declarado"])  # ficha con la que se extrajo (ADR-006 2.5)
        doc, texto, mrz = preparado(FIXTURES / m["archivo"], m["declarado"])
        extraidos = r.get("datos_extraidos") or {}
        confianzas = confianzas_de_campos(extraidos, ficha, texto, mrz if ficha.nombre == "pasaporte" else None)
        detectada = {f.nombre: f for f in configuracion.listar()}.get(m.get("tipo_detectado"))
        filas.append({"id": m["id"], "ruta": m["ruta"], "nivel": m.get("nivel", "normal"),
                      "cls_equivocada": m.get("clasificacion_equivocada", False),
                      "tipo_detectado": m.get("tipo_detectado"),
                      "clasificacion": confianza_clasificacion(detectada, texto) if detectada else None,
                      "minimo_clasificacion": detectada.confianza_minima_clasificacion if detectada else None,
                      "minimo_campo": ficha.confianza_minima_campo,
                      "campos": {c: {"estado": v["estado"], "confianza": confianzas.get(c, 0.0),
                                     "modelo": (r.get("nivel_confianza_por_campo") or {}).get(c)}
                                 for c, v in m["campos"].items()}})
    return filas


def _pct(a: int, t: int) -> str:
    return f"{a}/{t} ({100 * a / t:.0f} %)" if t else "-"


def informe(a: list[dict], b: list[dict]) -> str:
    l = ["# Calibracion de la confianza calculada (ADR-007)", "",
         "Generado por `docs/motor_ia/pruebas_ollama/calibrar_confianza.py`, sin llamar al modelo. Pesos:",
         "0,6 x aparece + 0,4 x formato; tope 0,5 si fallan los digitos de la MRZ. Umbrales sin cambiar.", "",
         "## A. Valores correctos en el texto de cada documento", "",
         "Si la extraccion fuera perfecta: campos con confianza >= `confianza_minima_campo` (si no, VAL-002 falso) y",
         "clasificaciones >= `confianza_minima_clasificacion` (si no, CLS-002 falso).", "",
         "| Nivel | Documentos | Campos >= minimo | Clasificacion >= minimo |", "|---|---|---|---|"]
    for nivel in ("normal", "dificil", "extremo", "especimen"):
        g = [f for f in a if f["nivel"] == nivel]
        if not g:
            continue
        campos = [(c, f["minimo_campo"]) for f in g for c in f["campos"].values()]
        l.append(f"| {nivel} | {len(g)} | {_pct(sum(c >= m for c, m in campos), len(campos))} | "
                 f"{_pct(sum(f['clasificacion'] >= f['minimo_clasificacion'] for f in g), len(g))} |")
    l += ["", "Por modalidad (nivel normal):", "", "| Modalidad | Campos >= minimo | Clasificacion >= minimo |", "|---|---|---|"]
    for modalidad in ("pdf_digital", "pdf_escaneado", "imagen"):
        g = [f for f in a if f["nivel"] == "normal" and f["modalidad"] == modalidad]
        campos = [(c, f["minimo_campo"]) for f in g for c in f["campos"].values()]
        l.append(f"| {modalidad} | {_pct(sum(c >= m for c, m in campos), len(campos))} | "
                 f"{_pct(sum(f['clasificacion'] >= f['minimo_clasificacion'] for f in g), len(g))} |")
    bajos = Counter()
    for f in a:
        for campo, c in f["campos"].items():
            if c < f["minimo_campo"]:
                bajos[(f["nivel"], f["tipo"], campo)] += 1
    l += ["", "Campos correctos por debajo del minimo (nivel, tipo, campo: documentos):", ""]
    l += [f"- {n} / {t} / `{c}`: {k}" for (n, t, c), k in sorted(bajos.items())] or ["- ninguno"]
    l += ["", "Clasificacion por documento (confianza del tipo correcto):", "",
          "| Documento | Nivel | Caracteres de texto | Clasificacion | Minimo |", "|---|---|---|---|---|"]
    l += [f"| `{f['archivo']}` | {f['nivel']} | {f['caracteres']} | {f['clasificacion']:.3f} | {f['minimo_clasificacion']:.2f} |"
          for f in a if f["clasificacion"] < f["minimo_clasificacion"] or f["nivel"] != "normal"]

    l += ["", "## B. Valores extraidos en la evaluacion", "",
          "Campos con valor (los vacios llevan VAL-001/VAL-004). Objetivo: correctos >= minimo e incorrectos < minimo.", "",
          "| Nivel | Ruta | Correctos >= minimo | Incorrectos < minimo (detectados) | Confianza del modelo en los incorrectos |",
          "|---|---|---|---|---|"]
    for nivel in ("normal", "dificil", "extremo"):
        for ruta in ("auto", "vision"):
            g = [f for f in b if f["nivel"] == nivel and f["ruta"] == ruta and not f["cls_equivocada"]]
            if not g:
                continue
            ok = [(c["confianza"], f["minimo_campo"]) for f in g for c in f["campos"].values() if c["estado"] == "correcto"]
            mal = [(c["confianza"], f["minimo_campo"], c["modelo"]) for f in g for c in f["campos"].values()
                   if c["estado"] == "incorrecto"]
            modelo = sorted({round(x[2], 2) for x in mal if x[2] is not None})
            l.append(f"| {nivel} | {ruta} | {_pct(sum(c >= m for c, m in ok), len(ok))} | "
                     f"{_pct(sum(c < m for c, m, _ in mal), len(mal))} | {', '.join(map(str, modelo)) or '-'} |")
    l += ["", "Incorrectos que pasan el minimo (errores silenciosos que la confianza no ve):", ""]
    silenciosos = [(f["id"], campo, c["confianza"]) for f in b if not f["cls_equivocada"]
                   for campo, c in f["campos"].items() if c["estado"] == "incorrecto" and c["confianza"] >= f["minimo_campo"]]
    l += [f"- `{i}` / `{campo}`: {conf:.2f}" for i, campo, conf in silenciosos] or ["- ninguno"]
    l += ["", "Clasificacion del tipo detectado (CLS-002 si < minimo):", "",
          "| Nivel | Ruta | Casos | Con CLS-002 |", "|---|---|---|---|"]
    for nivel in ("normal", "dificil", "extremo"):
        for ruta in ("auto", "vision"):
            g = [f for f in b if f["nivel"] == nivel and f["ruta"] == ruta and not f["cls_equivocada"] and f["clasificacion"] is not None]
            if g:
                l.append(f"| {nivel} | {ruta} | {len(g)} | {sum(f['clasificacion'] < f['minimo_clasificacion'] for f in g)} |")
    cls = [f for f in b if f["cls_equivocada"]]
    l += ["", f"Casos con el tipo declarado equivocado (CLS-001): {len(cls)}; el tipo detectado tiene confianza "
          + ", ".join(f"{f['clasificacion']:.2f}" for f in cls if f["clasificacion"] is not None) + "."]
    return "\n".join(l) + "\n"


def main() -> None:
    configuracion.cargar()
    indice = leer_indice(FIXTURES)
    a, b = analisis_a(indice), analisis_b()
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "calibracion.json").write_text(json.dumps({"a": a, "b": b}, ensure_ascii=False, indent=1), encoding="utf-8")
    texto = informe(a, b)
    (SALIDA / "informe.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
