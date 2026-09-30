"""Comprueba que el frontend (PERSONA_3) refleja los contratos (fuente de verdad: resultado.py,
endpoints.md, codigos_*.md y config/) y que los mocks son validos y coherentes con los fixtures:
  - frontend/src/tipos/contrato.ts: mismos campos y tipos que cada modelo de resultado.py.
  - frontend/src/tipos/codigos.ts: mismos codigos que docs/contratos/codigos_error.md y codigos_alertas.md.
  - frontend/src/mocks/datos/*.json: validos con Pydantic y coherentes con INDICE.md (generador).
Solo datos ficticios."""
import hashlib
import importlib.util
import json
import re
import types
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest
import yaml
from pydantic import BaseModel

RAIZ_REPO = Path(__file__).resolve().parents[2]
FRONT = RAIZ_REPO / "frontend"
CONTRATO_TS = FRONT / "src" / "tipos" / "contrato.ts"
if not CONTRATO_TS.is_file() or not (RAIZ_REPO / "config" / "tipos").is_dir():
    pytest.skip("Tests del contrato del frontend omitidos: falta frontend/ o config/ "
                "(normal dentro del contenedor del backend)", allow_module_level=True)

from app.schemas import resultado  # noqa: E402

CODIGOS_TS = FRONT / "src" / "tipos" / "codigos.ts"
DATOS = FRONT / "src" / "mocks" / "datos"
ORIGINALES = FRONT / "public" / "mock-originales"
CONTRATOS = RAIZ_REPO / "docs" / "contratos"
HOY_MOCKS = date(2026, 9, 30)  # fecha con la que se generaron los datos de los mocks

MODELOS = [c for c in vars(resultado).values()
           if isinstance(c, type) and issubclass(c, BaseModel) and c.__module__ == resultado.__name__]
ENUMS = {"Severidad": "SEVERIDADES", "Recomendacion": "RECOMENDACIONES", "EstadoAnalisis": "ESTADOS_ANALISIS",
         "EstadoGeneral": "ESTADOS_GENERALES", "DecisionHumana": "DECISIONES_HUMANAS"}


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _json(nombre: str):
    return json.loads(_texto(DATOS / f"{nombre}.json"))


# ---------------------------------------------------------------- lectura de los .ts

def interfaces_ts(fuente: str) -> dict[str, dict[str, str]]:
    """{Interfaz: {campo: tipo}} de las `export interface X { ... }` (un campo por linea)."""
    resultado_ = {}
    for nombre, cuerpo in re.findall(r"export interface (\w+) \{\n(.*?)\n\}", fuente, re.DOTALL):
        campos = {}
        for linea in cuerpo.splitlines():
            linea = linea.split("//")[0].strip()
            if m := re.fullmatch(r"(\w+)(\?)?: (.+)", linea):
                campos[m[1]] = m[3].strip()
        resultado_[nombre] = campos
    return resultado_


def constantes_ts(fuente: str) -> dict[str, list[str]]:
    return {n: re.findall(r"'([^']+)'", c) for n, c in
            re.findall(r"export const (\w+) = \[(.*?)\] as const", fuente, re.DOTALL)}


def tipo_ts_esperado(anotacion) -> str:
    """Tipo TypeScript que corresponde a una anotacion de resultado.py."""
    origen, args = get_origin(anotacion), get_args(anotacion)
    if origen in (Union, types.UnionType):
        resto = [a for a in args if a is not type(None)]
        base = tipo_ts_esperado(resto[0])
        return f"{base} | null" if type(None) in args else base
    if anotacion is Any:
        return "unknown"
    if origen is list:
        return f"{tipo_ts_esperado(args[0])}[]"
    if origen is dict:
        return f"Record<string, {tipo_ts_esperado(args[1])}>"
    if anotacion is bool:
        return "boolean"
    if anotacion in (int, float):
        return "number"
    if anotacion is str:
        return "string"
    if anotacion is datetime:
        return "FechaIso"
    if isinstance(anotacion, type) and issubclass(anotacion, (Enum, BaseModel)):
        return anotacion.__name__
    raise AssertionError(f"Anotacion sin equivalente en el test: {anotacion!r}")


# ---------------------------------------------------------------- contrato.ts y codigos.ts

def test_contrato_ts_tiene_todos_los_modelos_de_resultado_py():
    assert {m.__name__ for m in MODELOS} <= set(interfaces_ts(_texto(CONTRATO_TS)))


@pytest.mark.parametrize("modelo", MODELOS, ids=lambda m: m.__name__)
def test_campos_y_tipos_iguales_que_resultado_py(modelo):
    ts = interfaces_ts(_texto(CONTRATO_TS))[modelo.__name__]
    esperado = {nombre: tipo_ts_esperado(campo.annotation) for nombre, campo in modelo.model_fields.items()}
    assert ts == esperado


def test_enums_iguales_que_resultado_py():
    constantes = constantes_ts(_texto(CONTRATO_TS))
    for enum_py, constante in ENUMS.items():
        assert constantes[constante] == [e.value for e in getattr(resultado, enum_py)], enum_py
        assert f"export type {enum_py} = (typeof {constante})[number]" in _texto(CONTRATO_TS)


def test_codigos_de_error_iguales_que_el_catalogo():
    catalogo = {c: int(h) for h, c in re.findall(r"^\| (\d{3}) \| `(\w+)` \|", _texto(CONTRATOS / "codigos_error.md"), re.M)}
    bloque = _texto(CODIGOS_TS).split("ESTADO_HTTP_POR_ERROR = {")[1].split("} as const")[0]
    ts = {c: int(h) for c, h in re.findall(r"(\w+): (\d{3}),", bloque)}
    assert ts == catalogo


def test_codigos_de_alerta_iguales_que_el_catalogo():
    catalogo = {c: (e.split()[0], s) for c, e, s in
                re.findall(r"^\| `([A-Z]{3}-\d{3})` \| ([^|]+?) \| (\w+) \|", _texto(CONTRATOS / "codigos_alertas.md"), re.M)}
    ts = {c: (e, s) for c, e, s in
          re.findall(r"'([A-Z]{3}-\d{3})': \{ emisor: '([^']+)', severidad: '(\w+)'", _texto(CODIGOS_TS))}
    assert ts == catalogo
    assert "PREFIJO_REGLA = 'REG-'" in _texto(CODIGOS_TS)


def test_acciones_de_auditoria_iguales_que_endpoints_md():
    contrato = _texto(CONTRATOS / "endpoints.md").split("`accion` es una lista cerrada:")[1].split("`detalle`")[0]
    assert constantes_ts(_texto(CONTRATO_TS))["ACCIONES_AUDITORIA"] == re.findall(r"`(\w+)`", contrato)


# ---------------------------------------------------------------- datos de los mocks

def test_folios_validos_y_con_todas_las_claves():
    for folio in _json("folios"):
        # La API serializa todos los campos: el JSON del mock debe ser exactamente esa serializacion
        assert resultado.ResultadoExpediente.model_validate(folio).model_dump(mode="json") == folio, folio["folio"]


def test_los_mocks_cubren_los_casos_pedidos():
    folios = _json("folios")
    documentos = [d for f in folios for d in f["documentos"]]
    todas = [a for d in documentos for a in d["alertas_encontradas"]] + [a for f in folios for a in f["alertas_expediente"]]
    por_folio = {f["folio"]: f for f in folios}
    severidades_f1 = {a["severidad"] for a in por_folio["ONB-2026-000001"]["alertas_expediente"]} | {
        a["severidad"] for d in por_folio["ONB-2026-000001"]["documentos"] for a in d["alertas_encontradas"]}
    assert severidades_f1 == {s.value for s in resultado.Severidad}
    assert any(a["codigo"] == "CMP-001" and a["campo"] == "domicilio" for f in folios for a in f["alertas_expediente"])
    assert any(a["codigo"] == "EXP-001" for f in folios for a in f["alertas_expediente"])
    assert any(d["correcciones"] for d in documentos)
    assert any(d["estado_analisis"] == "error" and any(a["codigo"].startswith("SYS-") for a in d["alertas_encontradas"])
               for d in documentos)
    assert any(d["estado_analisis"] == "pendiente" for d in documentos)
    assert any(f["estado_general"] == "aprobado" and f["decision_humana"] == "aprobar" for f in folios)
    assert all(a["id"] for a in todas) and len({a["id"] for a in todas}) == len(todas)


def test_codigos_y_severidades_de_las_alertas_de_los_mocks():
    fichas = {f["nombre"]: f for f in _json("tipos_documentales")}
    catalogo = dict(re.findall(r"'([A-Z]{3}-\d{3})': \{ emisor: '[^']+', severidad: '(\w+)'", _texto(CODIGOS_TS)))
    for folio in _json("folios"):
        alertas = [(None, a) for a in folio["alertas_expediente"]] + [
            (d["tipo_documental_detectado"] or d["tipo_documental_declarado"], a)
            for d in folio["documentos"] for a in d["alertas_encontradas"]]
        for tipo, a in alertas:
            if a["codigo"].startswith("REG-"):
                regla = next(r for r in fichas[tipo]["reglas"] if f"REG-{r['id']}" == a["codigo"])
                assert a["severidad"] == regla["severidad"]
            elif a["codigo"].startswith("MOCK-"):  # solo mocks: no hay codigo informativo en el catalogo
                assert a["severidad"] == "informativa"
            else:
                assert catalogo[a["codigo"]] == a["severidad"], a["codigo"]


def test_tipos_documentales_y_procesos_iguales_que_config():
    claves = ("nombre", "nombre_visible", "categoria", "descripcion", "formatos_permitidos", "campos",
              "confianza_minima_clasificacion", "confianza_minima_campo", "reglas", "comparaciones")
    fichas = [yaml.safe_load(_texto(r)) for r in sorted((RAIZ_REPO / "config" / "tipos").glob("*.yaml"))]
    assert _json("tipos_documentales") == [{k: f[k] for k in claves} for f in fichas]
    procesos = yaml.safe_load(_texto(RAIZ_REPO / "config" / "procesos.yaml"))["procesos"]
    assert {p["nombre"]: {k: v for k, v in p.items() if k != "nombre"} for p in _json("procesos")} == {
        n: {k: p[k] for k in ("prefijo_folio", "tipos_requeridos", "tipos_opcionales", "permitir_antecedentes",
                              "caducidad_antecedentes_dias", "webhook_url", "modelos")} for n, p in procesos.items()}


def test_auditoria_con_la_forma_del_contrato():
    acciones = constantes_ts(_texto(CONTRATO_TS))["ACCIONES_AUDITORIA"]
    claves = set(interfaces_ts(_texto(CONTRATO_TS))["EntradaAuditoria"])
    for entrada in _json("auditoria"):
        assert set(entrada) == claves and entrada["accion"] in acciones
        assert isinstance(entrada["id"], int) and datetime.fromisoformat(entrada["creado_en"])


@pytest.fixture(scope="module")
def generador(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("gf", RAIZ_REPO / "scripts" / "generar_fixtures.py")
    gf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gf)
    salida = tmp_path_factory.mktemp("fixtures")
    return gf, gf.generar(HOY_MOCKS, salida)


def test_datos_y_originales_coherentes_con_los_fixtures(generador):
    gf, hashes = generador
    for folio in _json("folios"):
        for doc in folio["documentos"]:
            archivo = doc["referencia_archivo_original"]["nombre_archivo"]
            caso = next(c for c in gf.CASOS if f"_{c}_" in archivo)
            tipo = doc["tipo_documental_declarado"]
            # Mismo fichero que el generador (y que public/mock-originales) -> DUP-001 al volver a subirlo
            assert doc["referencia_archivo_original"]["hash"] == hashes[archivo] \
                == hashlib.sha256((ORIGINALES / archivo).read_bytes()).hexdigest()
            if doc["estado_analisis"] != "completado":
                assert doc["datos_extraidos"] == {}
                continue
            persona = gf.PERSONAS_FICTICIAS[gf.CASOS[caso]["persona"]]
            esperados = {c: v.isoformat() if isinstance(v, date) else v
                         for c, v in gf.valores_documento(tipo, persona, caso, HOY_MOCKS).items()}
            assert doc["datos_extraidos"] == esperados, archivo
            for correccion in doc["correcciones"]:
                assert correccion["valor_nuevo"] == esperados[correccion["campo"]]
                assert doc["evidencia_por_campo"][correccion["campo"]] == "correccion_revisor"
