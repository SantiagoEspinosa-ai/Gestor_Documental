"""H2: el openapi de la API (`app.openapi()`) contra el Contrato 2 y el frontend.

  a) Rutas y metodos bajo /api/v1: los mismos que la tabla de docs/contratos/endpoints.md.
  b) Codigo de exito de cada endpoint, cuando endpoints.md lo indica (p. ej. `202` en la subida).
  c) Esquemas: mismos campos que la interface equivalente de frontend/src/tipos/contrato.ts, y una
     nulabilidad y opcionalidad que no se contradigan (reglas en `_diferencias`).

Solo detecta desviaciones: no las arregla. Una desviacion real va como xfail(strict=True) con su motivo
hasta que se decida si cambia la API, el TS o el contrato (ADR).
"""
import re
from pathlib import Path

import pytest

from app.main import app

RAIZ_REPO = Path(__file__).resolve().parents[2]
ENDPOINTS_MD = RAIZ_REPO / "docs" / "contratos" / "endpoints.md"
CONTRATO_TS = RAIZ_REPO / "frontend" / "src" / "tipos" / "contrato.ts"
PREFIJO = "/api/v1"
METODOS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

OPENAPI = app.openapi()


def _normalizar(ruta: str) -> str:
    """Sin query y con los parametros de ruta anonimos: {id} y {documento_id} son el mismo hueco."""
    return re.sub(r"\{[^}]+\}", "{}", ruta.split("?")[0])


# ---------------------------------------------------------------- endpoints.md

def _filas_endpoints() -> dict[tuple[str, str], str]:
    """{(metodo, ruta normalizada): columna Respuesta} de la tabla de endpoints.md, tal como esta."""
    filas = {}
    for linea in ENDPOINTS_MD.read_text(encoding="utf-8").splitlines():
        # La descripcion puede llevar "\|" (p. ej. aprobar\|rechazar): no separa columnas
        columnas = [c.strip() for c in re.split(r"(?<!\\)\|", linea)[1:-1]]
        if len(columnas) == 5 and columnas[0] in METODOS:
            filas[(columnas[0], PREFIJO + _normalizar(columnas[1]))] = columnas[4]
    return filas


ENDPOINTS = _filas_endpoints()
API = {(metodo.upper(), _normalizar(ruta)): operacion
       for ruta, operaciones in OPENAPI["paths"].items() if ruta.startswith(PREFIJO)
       for metodo, operacion in operaciones.items()}

# Desviaciones conocidas de (a): endpoints del contrato que la API aun no tiene. Vacio desde H16 (antecedentes)
PENDIENTES: dict[tuple[str, str], str] = {}


def test_la_tabla_de_endpoints_se_lee():
    assert len(ENDPOINTS) >= 15, "No se ha podido leer la tabla de docs/contratos/endpoints.md"


@pytest.mark.parametrize("clave", [
    pytest.param(c, marks=pytest.mark.xfail(strict=True, reason=PENDIENTES[c])) if c in PENDIENTES else c
    for c in sorted(ENDPOINTS.keys() | API.keys())], ids=lambda c: f"{c[0]} {c[1]}")
def test_rutas_y_metodos_iguales(clave):
    if clave not in API:
        pytest.fail(f"Falta en la API: {clave[0]} {clave[1]} esta en endpoints.md")
    if clave not in ENDPOINTS:
        pytest.fail(f"Sobra en la API: {clave[0]} {clave[1]} no esta en endpoints.md")


def _codigo_del_contrato(respuesta: str) -> str | None:
    """`202 {...}` en la columna Respuesta -> "202". Sin codigo, None (no se comprueba)."""
    encontrado = re.match(r"`?(\d{3})\b", respuesta)
    return encontrado.group(1) if encontrado else None


CON_CODIGO = {c: _codigo_del_contrato(r) for c, r in ENDPOINTS.items() if _codigo_del_contrato(r) and c in API}


def test_hay_codigos_que_comprobar():
    assert CON_CODIGO, "endpoints.md deberia indicar al menos el 202 de la subida"


@pytest.mark.parametrize("clave", sorted(CON_CODIGO), ids=lambda c: f"{c[0]} {c[1]}")
def test_codigo_de_exito(clave):
    exitos = sorted(c for c in API[clave]["responses"] if c.startswith("2"))
    assert exitos == [CON_CODIGO[clave]], f"{clave[0]} {clave[1]}: openapi {exitos}, endpoints.md {CON_CODIGO[clave]}"


# ---------------------------------------------------------------- contrato.ts

# Esquema del openapi -> interface de contrato.ts cuando el nombre no coincide.
# Los que se llaman igual (ResultadoDocumento, Alerta, ResumenFolio, PaginaAuditoria...) se emparejan solos
EQUIVALENTES = {
    "LoginEntrada": "PeticionLogin",
    "LoginSalida": "RespuestaLogin",
    "UsuarioYo": "UsuarioActual",
    "Proceso": "ProcesoCompleto",  # el revisor recibe ProcesoRevisor = Omit<..., 'webhook_url' | 'modelos'>
    "FolioEntrada": "PeticionCrearFolio",
    "FolioCreado": "RespuestaCrearFolio",
    "DocumentoAceptado": "RespuestaSubidaDocumento",
    "UrlOriginal": "RespuestaOriginal",
    "RevelarEntrada": "PeticionRevelar",
    "RetirarEntrada": "PeticionRetirar",  # ADR-013
    "DatoRevelado": "RespuestaRevelar",
    "ConfirmarClasificacionEntrada": "PeticionConfirmarClasificacion",
    "ResolverAlertaEntrada": "PeticionResolverAlerta",
    "DecisionEntrada": "PeticionDecision",
    "CampoTipo": "CampoFicha",
}
# Esquemas sin interface en contrato.ts: los genera FastAPI o son multipart
SIN_INTERFACE = {"HTTPValidationError", "ValidationError", "Body_subir_api_v1_folios__folio__documentos_post"}

# Desviaciones conocidas de (c): {esquema: motivo}. Pendientes de decidir si cambia la API, el TS o el contrato.
# Vacio: las de Proceso, TipoDocumental y CampoTipo se corrigieron tras el primer pase de H2
DESVIACIONES_ESQUEMA: dict[str, str] = {}


def _interfaces_ts() -> dict[str, dict[str, tuple[bool, bool]]]:
    """{Interface: {campo: (opcional, nullable)}}. Un campo por linea; los comentarios se ignoran."""
    fuente = re.sub(r"/\*.*?\*/", "", CONTRATO_TS.read_text(encoding="utf-8"), flags=re.DOTALL)
    interfaces = {}
    for nombre, cuerpo in re.findall(r"export interface (\w+) \{\n(.*?)\n\}", fuente, re.DOTALL):
        campos = {}
        for linea in cuerpo.splitlines():
            campo = re.match(r"\s*(\w+)(\?)?:\s*(.+?)\s*$", linea.split("//")[0])
            if campo:
                tipo = campo.group(3)
                campos[campo.group(1)] = (bool(campo.group(2)), bool(re.search(r"\|\s*null\b", tipo)))
        interfaces[nombre] = campos
    return interfaces


def _campos_openapi(esquema: dict) -> dict[str, tuple[bool, bool]]:
    """{campo: (opcional, nullable)} de un esquema de components/schemas."""
    requeridos = set(esquema.get("required", []))
    return {campo: (campo not in requeridos,
                    any(o.get("type") == "null" for o in propiedad.get("anyOf", [])) or propiedad.get("type") == "null")
            for campo, propiedad in esquema.get("properties", {}).items()}


def _referencias(nodo) -> set[str]:
    """Nombres de components/schemas a los que apunta un nodo, siguiendo los $ref anidados."""
    vistos: set[str] = set()
    pendientes = [nodo]
    while pendientes:
        actual = pendientes.pop()
        if isinstance(actual, dict):
            ref = actual.get("$ref", "")
            if ref.startswith("#/components/schemas/") and (nombre := ref.rsplit("/", 1)[1]) not in vistos:
                vistos.add(nombre)
                pendientes.append(OPENAPI["components"]["schemas"][nombre])
            pendientes.extend(actual.values())
        elif isinstance(actual, list):
            pendientes.extend(actual)
    return vistos


_OPERACIONES = [o for operaciones in OPENAPI["paths"].values() for o in operaciones.values()]
DE_ENTRADA = _referencias([o.get("requestBody", {}) for o in _OPERACIONES])
DE_SALIDA = _referencias([o["responses"].get(c) for o in _OPERACIONES for c in o["responses"] if c.startswith("2")])


def _diferencias(esquema: str, api: dict[str, tuple[bool, bool]], ts: dict[str, tuple[bool, bool]]) -> dict:
    """Campos cuya (opcionalidad, nulabilidad) se contradice entre openapi y TS. Por direccion:
    - Respuesta: Pydantic serializa todos los campos, tambien los que tienen valor por defecto, asi que
      "no requerido" en el openapi no significa que pueda faltar. Se compara la nulabilidad (`T | null`
      frente a anyOf con null) y que un campo `campo?:` del TS no sea requerido en el openapi.
    - Peticion: lo que el TS puede enviar lo tiene que aceptar la API. Falla si el TS lo deja opcional
      y la API lo exige, o si el TS envia null y la API no lo acepta.
    """
    distintos = {}
    for campo in api.keys() & ts.keys():
        (api_opcional, api_null), (ts_opcional, ts_null) = api[campo], ts[campo]
        problemas = []
        if esquema in DE_SALIDA:
            if api_null != ts_null:
                problemas.append(f"respuesta: nullable en la API {api_null}, en el TS {ts_null}")
            if ts_opcional and not api_opcional:
                problemas.append("respuesta: opcional en el TS y requerido en la API")
        if esquema in DE_ENTRADA:
            if ts_opcional and not api_opcional:
                problemas.append("peticion: opcional en el TS y requerido en la API")
            if ts_null and not api_null:
                problemas.append("peticion: el TS envia null y la API no lo acepta")
        if problemas:
            distintos[campo] = problemas
    return distintos


ESQUEMAS = {nombre: esquema for nombre, esquema in OPENAPI["components"]["schemas"].items()
            if "properties" in esquema and nombre not in SIN_INTERFACE}  # los enum no tienen properties


def _parejas() -> list[tuple[str, str]]:
    if not CONTRATO_TS.is_file():
        return []
    interfaces = _interfaces_ts()
    return sorted((nombre, EQUIVALENTES.get(nombre, nombre)) for nombre in ESQUEMAS
                  if EQUIVALENTES.get(nombre, nombre) in interfaces)


@pytest.fixture(scope="module")
def interfaces():
    if not CONTRATO_TS.is_file():
        pytest.skip("Falta frontend/src/tipos/contrato.ts (normal dentro del contenedor del backend)")
    return _interfaces_ts()


def test_cada_esquema_tiene_su_interface(interfaces):
    sin_pareja = sorted(n for n in ESQUEMAS if EQUIVALENTES.get(n, n) not in interfaces)
    assert not sin_pareja, (f"Esquemas del openapi sin interface en contrato.ts: {sin_pareja}. "
                            "Anade la interface o la equivalencia en EQUIVALENTES")


@pytest.mark.parametrize("esquema,interface", [
    pytest.param(e, i, marks=pytest.mark.xfail(strict=True, reason=DESVIACIONES_ESQUEMA[e]))
    if e in DESVIACIONES_ESQUEMA else (e, i) for e, i in _parejas()], ids=lambda v: v)
def test_esquema_igual_que_contrato_ts(esquema, interface, interfaces):
    api, ts = _campos_openapi(ESQUEMAS[esquema]), interfaces[interface]
    faltan, sobran = sorted(ts.keys() - api.keys()), sorted(api.keys() - ts.keys())
    assert not faltan and not sobran, (f"{esquema} / {interface}: campos que faltan en la API {faltan}, "
                                       f"que sobran en la API {sobran}")
    distintos = _diferencias(esquema, api, ts)
    assert not distintos, f"{esquema} / {interface}: opcionalidad o nulabilidad contradictoria: {distintos}"
