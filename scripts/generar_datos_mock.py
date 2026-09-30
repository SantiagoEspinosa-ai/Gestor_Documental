"""
Genera los datos ficticios de los mocks del frontend a partir del generador de fixtures.
Responsable: PERSONA_3. Solo datos ficticios.

Uso (desde la raiz del repo):
    python scripts/generar_datos_mock.py [--datos DIR] [--originales DIR]

Escribe:
  - frontend/src/mocks/datos/{folios,procesos,tipos_documentales,auditoria}.json
  - frontend/public/mock-originales/: copias de los fixtures que usan esos folios

Los valores, las reglas incumplidas y los SHA-256 salen de scripts/generar_fixtures.py con
--hoy HOY_MOCKS (2026-09-30), asi que coinciden con fixtures/generados/INDICE.md generado con esa
fecha. Por eso, subir desde la UI un fixture generado con --hoy 2026-09-30 da DUP-001 contra los
documentos de los mocks. Con otra fecha cambian los ficheros y ese DUP-001 no aparece.
procesos y tipos_documentales se copian de config/.

Los 4 folios cubren: alertas de las 4 severidades (una bloqueante), CMP-001 de domicilio en
alertas_expediente, EXP-001 (campo = tipo que falta), una correccion, un documento en error
(SYS-001), uno pendiente y un folio cerrado (aprobado). Las tres informativas: VAL-003 (valor tomado
de la MRZ) en el pasaporte del folio 1, VAL-004 (proveedor opcional no leido, null) en el comprobante
del folio 2 y SYS-005 (proveedor de respaldo) en la credencial del folio 3. Un campo sin valor es
null, nunca "".

Es determinista: sin azar ni fecha actual. backend/tests/test_generar_datos_mock.py comprueba que
reproduce exactamente los ficheros del repo, y test_contrato_frontend.py que son validos.
Si cambias el contrato o los casos, regenera con este script (no edites los JSON a mano).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "frontend" / "src" / "mocks" / "datos"
ORIGINALES = RAIZ / "frontend" / "public" / "mock-originales"
HOY_MOCKS = date(2026, 9, 30)
REVISOR, INTEGRADOR = "revisor.demo", "integrador.demo"  # usuarios de frontend/src/mocks/usuarios.ts
MODELO = ("llama3.2-vision:11b", "extraccion@v1")
# Proveedor de respaldo de SYS-005: OpenRouter (ADR-003, PROVEEDOR_COMERCIAL de .env.example); modelo ficticio
RESPALDO = ("openrouter", "modelo-respaldo-ficticio:free", "extraccion@v1")


def _cargar_generador():
    spec = importlib.util.spec_from_file_location("generar_fixtures", RAIZ / "scripts" / "generar_fixtures.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def momento(dia: int, hora: int, minuto: int) -> datetime:
    return datetime(2026, 9, dia, hora, minuto, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def confianza_campo(tipo: str, campo: str) -> float:
    """Determinista y plausible (0.86..0.98), sin azar."""
    h = int(hashlib.sha256(f"{tipo}.{campo}".encode()).hexdigest(), 16)
    return round(0.86 + (h % 13) / 100, 2)


def bloquea(a: dict) -> bool:
    return a["severidad"] == "bloqueante" and a["aplica"] is not False


def pesa(a: dict) -> bool:
    return a["severidad"] in ("critica", "bloqueante") and a["aplica"] is not False


class DatosMock:
    """Construye folios, documentos, alertas y auditoria con contadores propios."""

    def __init__(self, gf, fixtures: Path, originales: Path):
        self.gf, self.fixtures, self.originales = gf, fixtures, originales
        self.fichas = gf.cargar_fichas()
        self.contador_alertas = 0
        self.auditoria: list[dict] = []
        self.hashes_por_folio: dict[str, set[str]] = {}  # para `duplicado` en la auditoria de la subida

    def alerta(self, codigo, mensaje, severidad, campo=None, confianza=1.0) -> dict:
        self.contador_alertas += 1
        return {"id": f"alr-{self.contador_alertas:06d}", "codigo": codigo, "mensaje": mensaje, "severidad": severidad,
                "confianza": confianza, "campo": campo, "resuelta_por_revisor": False, "aplica": None,
                "comentario_revisor": None, "resuelta_por": None, "resuelta_en": None}

    def auditar(self, usuario, accion, folio, documento_id, detalle, cuando, modelo=None, version_prompt=None):
        self.auditoria.append({"id": len(self.auditoria) + 1, "usuario": usuario, "accion": accion, "folio": folio,
                               "documento_id": documento_id, "detalle": detalle, "modelo": modelo,
                               "version_prompt": version_prompt, "creado_en": iso(cuando)})

    def documento(self, folio, secuencia, n, caso, tipo, modalidad, subido, estado="completado", alertas_extra=(),
                  confianzas=None, correcciones=(), vacios=(), respaldo=False) -> dict:
        """`vacios`: campos opcionales que el analisis no leyo (null, confianza 0, sin evidencia y VAL-004).
        `respaldo`: analizado con el proveedor de respaldo (SYS-005)."""
        gf = self.gf
        archivo = gf.nombre_archivo(tipo, caso, modalidad)
        shutil.copyfile(self.fixtures / archivo, self.originales / archivo)
        uid = f"00000000-0000-4000-8000-{secuencia:06d}{n:06d}"
        ext = archivo.rsplit(".", 1)[1]
        datos = (self.fixtures / archivo).read_bytes()
        hash_ = hashlib.sha256(datos).hexdigest()
        vistos = self.hashes_por_folio.setdefault(folio, set())
        duplicado = hash_ in vistos
        vistos.add(hash_)
        doc = {"folio_solicitud": folio, "identificador_unico_documento": uid,
               "tipo_documental_declarado": tipo, "tipo_documental_detectado": None,
               "tipo_documental_confirmado": None, "confianza_clasificacion": None,
               "datos_extraidos": {}, "nivel_confianza_por_campo": {}, "evidencia_por_campo": {},
               "reglas_cumplidas_e_incumplidas": {"cumplidas": [], "incumplidas": []},
               "alertas_encontradas": list(alertas_extra), "correcciones": [], "recomendacion": None,
               "estado_analisis": estado, "fecha_y_modelo_utilizado": None,
               "referencia_archivo_original": {
                   "nombre_archivo": archivo, "ruta": f"onboarding/2026/{secuencia:06d}/{uid}.{ext}",
                   "hash": hash_}}
        # Mismo detalle que la API real: sin nombre_archivo (los nombres de fichero suelen llevar el de la persona)
        self.auditar(INTEGRADOR, "documento_subido", folio, uid,
                     {"hash_sha256": hash_, "tamano_bytes": len(datos), "duplicado": duplicado}, subido)
        if estado != "completado":
            if estado == "error":
                self.auditar(None, "documento_procesado", folio, uid, {"estado_analisis": "error"},
                             subido + timedelta(seconds=40), *MODELO)
            return doc
        ficha = self.fichas[tipo]
        persona = gf.PERSONAS_FICTICIAS[gf.CASOS[caso]["persona"]]
        valores = gf.valores_documento(tipo, persona, caso, HOY_MOCKS)
        incumplidas = gf.evaluar_reglas(ficha, valores, HOY_MOCKS)
        ids_incumplidas = [a["codigo"].removeprefix("REG-") for a in incumplidas]
        obligatorios = [c for c in vacios if ficha["campos"][c]["obligatorio"]]
        if obligatorios:
            raise ValueError(f"{tipo}: {obligatorios} son obligatorios; vacios solo admite campos opcionales (VAL-004)")
        proveedor, modelo, version_prompt = RESPALDO if respaldo else ("ollama", *MODELO)
        doc.update({
            "tipo_documental_detectado": tipo, "confianza_clasificacion": 0.94,
            "datos_extraidos": {c: v.isoformat() if isinstance(v, date) else v
                                for c, v in ((c, valores[c]) for c in ficha["campos"])},
            "nivel_confianza_por_campo": {c: confianza_campo(tipo, c) for c in ficha["campos"]} | (confianzas or {}),
            "evidencia_por_campo": {c: "pagina_1" for c in ficha["campos"]},
            "reglas_cumplidas_e_incumplidas": {
                "cumplidas": [r["id"] for r in ficha["reglas"] if r["id"] not in ids_incumplidas],
                "incumplidas": ids_incumplidas},
            "fecha_y_modelo_utilizado": {"fecha_analisis": iso(subido + timedelta(seconds=40)), "proveedor": proveedor,
                                         "modelo": modelo, "version_prompt": version_prompt},
        })
        for campo in vacios:  # sin valor = null (nunca ""), confianza 0 (ADR-007) y sin evidencia
            doc["datos_extraidos"][campo] = None
            doc["nivel_confianza_por_campo"][campo] = 0.0
            del doc["evidencia_por_campo"][campo]
        doc["alertas_encontradas"] = (
            [self.alerta(a["codigo"], a["motivo"], a["severidad"], a["campo"]) for a in incumplidas]
            + [self.alerta("VAL-004", f"Falta el campo opcional {c}", "informativa", c) for c in vacios]
            + ([self.alerta("SYS-005", "Fallo el proveedor principal; analizado con el proveedor de respaldo",
                            "informativa")] if respaldo else [])
            + doc["alertas_encontradas"])
        for campo, anterior, cuando in correcciones:
            doc["correcciones"].append({"campo": campo, "valor_anterior": anterior,
                                        "valor_nuevo": doc["datos_extraidos"][campo], "usuario": REVISOR,
                                        "fecha": iso(cuando)})
            doc["nivel_confianza_por_campo"][campo] = 1.0
            doc["evidencia_por_campo"][campo] = "correccion_revisor"
        bajas = any(v < ficha["confianza_minima_campo"] for v in doc["nivel_confianza_por_campo"].values())
        doc["recomendacion"] = "revision_manual" if bajas or any(pesa(a) for a in doc["alertas_encontradas"]) else "aprobar"
        self.auditar(None, "documento_procesado", folio, uid, {"estado_analisis": "completado"},
                     subido + timedelta(seconds=40), modelo, version_prompt)
        for campo, _, cuando in correcciones:
            self.auditar(REVISOR, "dato_corregido", folio, uid, {"campo": campo}, cuando)
        return doc

    def comparaciones(self, documentos) -> list[dict]:
        por_campo: dict[str, dict] = {}
        completos = [d for d in documentos if d["estado_analisis"] == "completado"]
        for i, a in enumerate(completos):
            for b in completos[i + 1:]:
                ta, tb = a["tipo_documental_detectado"], b["tipo_documental_detectado"]
                campos = (set(self.fichas[ta].get("comparaciones", {}).get(tb, []))
                          | set(self.fichas[tb].get("comparaciones", {}).get(ta, [])))
                for campo in campos:
                    valores = por_campo.setdefault(campo, {})
                    valores[a["identificador_unico_documento"]] = a["datos_extraidos"][campo]
                    valores[b["identificador_unico_documento"]] = b["datos_extraidos"][campo]
        return [{"campo": c, "coincide": len({self.gf.normalizar(v) for v in vals.values()}) == 1, "valores": vals}
                for c, vals in sorted(por_campo.items())]

    def expediente(self, folio, referencia, solicitado, documentos, alertas_expediente=(), decision=None,
                   resumen=False) -> dict:
        todas = [a for d in documentos for a in d["alertas_encontradas"]] + list(alertas_expediente)
        revisar = any(bloquea(a) or pesa(a) for a in todas) or any(d["recomendacion"] != "aprobar" for d in documentos)
        exp = {"folio": folio, "proceso": "onboarding", "referencia_externa": referencia,
               "fecha_solicitud": iso(solicitado), "estado_general": "en_revision", "documentos": documentos,
               "comparaciones": self.comparaciones(documentos), "alertas_expediente": list(alertas_expediente),
               "recomendacion_global": "revision_manual" if revisar else "aprobar", "decision_humana": None,
               "comentario_decision": None, "usuario_decision": None, "fecha_decision": None,
               "ruta_resumen_md": f"onboarding/2026/{folio[-6:]}/resumen.md" if resumen else None}
        if decision:
            dec, comentario, cuando = decision
            exp.update({"estado_general": "aprobado" if dec == "aprobar" else "rechazado", "decision_humana": dec,
                        "comentario_decision": comentario, "usuario_decision": REVISOR, "fecha_decision": iso(cuando)})
            self.auditar(REVISOR, "decision_tomada", folio, None, {"decision": dec}, cuando)
        return exp

    def folios(self) -> list[dict]:
        folios = []
        # 1. Luis, pasaporte vencido: alertas de las 4 severidades (bloqueante, critica, preventiva, informativa)
        f, s, t0 = "ONB-2026-000001", 1, momento(28, 9, 15)
        self.auditar(INTEGRADOR, "folio_creado", f, None, {}, t0)
        d1 = self.documento(f, s, 1, "vencido", "pasaporte", "escaneado", t0 + timedelta(minutes=1),
                            alertas_extra=[self.alerta("VAL-003", "Valor de nacionalidad tomado de la MRZ: no se leyo "
                                                       "en la zona visual", "informativa", "nacionalidad")])
        d2 = self.documento(f, s, 2, "vencido", "credencial_elector", "foto", t0 + timedelta(minutes=2),
                            confianzas={"clave_elector": 0.62},
                            alertas_extra=[self.alerta("VAL-002", "Confianza de clave_elector (0.62) por debajo del "
                                                       "minimo de la ficha (0.80)", "preventiva", "clave_elector", 0.62)])
        d3 = self.documento(f, s, 3, "vencido", "comprobante_domicilio", "digital", t0 + timedelta(minutes=3))
        d4 = self.documento(f, s, 4, "vencido", "comprobante_domicilio", "digital", t0 + timedelta(minutes=4),
                            alertas_extra=[self.alerta("DUP-001", f"Mismo SHA-256 que el documento "
                                                       f"{d3['identificador_unico_documento']} del folio", "critica")])
        folios.append(self.expediente(f, "CLI-000101", t0, [d1, d2, d3, d4]))

        # 2. Ana, domicilio distinto: CMP-001 en alertas_expediente, una correccion y un documento pendiente
        f, s, t0 = "ONB-2026-000002", 2, momento(29, 11, 40)
        self.auditar(INTEGRADOR, "folio_creado", f, None, {}, t0)
        d1 = self.documento(f, s, 1, "domicilio_distinto", "credencial_elector", "escaneado", t0 + timedelta(minutes=1),
                            correcciones=[("nombre_completo", "ANA EJEMPL0 PRUEBA", t0 + timedelta(minutes=25))])
        d2 = self.documento(f, s, 2, "domicilio_distinto", "comprobante_domicilio", "foto", t0 + timedelta(minutes=2),
                            vacios=("proveedor",))
        d3 = self.documento(f, s, 3, "domicilio_distinto", "pasaporte", "digital", t0 + timedelta(minutes=30),
                            estado="pendiente")
        folios.append(self.expediente(f, "CLI-000102", t0, [d1, d2, d3], [
            self.alerta("CMP-001", "domicilio distinto entre credencial_elector y comprobante_domicilio", "critica",
                        "domicilio")]))

        # 3. Ana, falta el comprobante: EXP-001 (campo = tipo que falta) y un documento en error (SYS-001)
        f, s, t0 = "ONB-2026-000003", 3, momento(30, 8, 5)
        self.auditar(INTEGRADOR, "folio_creado", f, None, {}, t0)
        d1 = self.documento(f, s, 1, "sano", "credencial_elector", "digital", t0 + timedelta(minutes=1), respaldo=True)
        d2 = self.documento(f, s, 2, "sano", "pasaporte", "foto", t0 + timedelta(minutes=2), estado="error",
                            alertas_extra=[self.alerta("SYS-001", "Fallo del proveedor principal y sin respaldo", "critica")])
        folios.append(self.expediente(f, None, t0, [d1, d2], [
            self.alerta("EXP-001", "Falta comprobante_domicilio, requerido por el proceso onboarding", "bloqueante",
                        "comprobante_domicilio")]))

        # 4. Ana, todo correcto: folio cerrado (aprobado) con resumen
        f, s, t0 = "ONB-2026-000004", 4, momento(25, 10, 0)
        self.auditar(INTEGRADOR, "folio_creado", f, None, {}, t0)
        docs = [self.documento(f, s, i + 1, "sano", tipo, "digital", t0 + timedelta(minutes=i + 1))
                for i, tipo in enumerate(("pasaporte", "credencial_elector", "comprobante_domicilio"))]
        folios.append(self.expediente(f, "CLI-000104", t0, docs,
                                      decision=("aprobar", "Documentacion completa y coherente", momento(26, 12, 30)),
                                      resumen=True))
        return folios


def generar(datos: Path = DATOS, originales: Path = ORIGINALES) -> None:
    gf = _cargar_generador()
    with tempfile.TemporaryDirectory() as tmp:
        fixtures = Path(tmp)
        gf.generar(HOY_MOCKS, fixtures)
        shutil.rmtree(originales, ignore_errors=True)
        originales.mkdir(parents=True)
        datos.mkdir(parents=True, exist_ok=True)
        constructor = DatosMock(gf, fixtures, originales)
        folios = constructor.folios()

    procesos_yaml = yaml.safe_load((RAIZ / "config" / "procesos.yaml").read_text(encoding="utf-8"))["procesos"]
    claves_proceso = ("prefijo_folio", "tipos_requeridos", "tipos_opcionales", "permitir_antecedentes",
                      "caducidad_antecedentes_dias", "webhook_url", "modelos")
    procesos = [{"nombre": nombre, **{k: p[k] for k in claves_proceso}} for nombre, p in procesos_yaml.items()]
    claves_ficha = ("nombre", "nombre_visible", "categoria", "descripcion", "formatos_permitidos", "campos",
                    "confianza_minima_clasificacion", "confianza_minima_campo", "reglas", "comparaciones")
    tipos = [{k: ficha[k] for k in claves_ficha} for ficha in constructor.fichas.values()]
    auditoria = sorted(constructor.auditoria, key=lambda e: e["creado_en"])
    for i, entrada in enumerate(auditoria, 1):
        entrada["id"] = i
    for nombre, contenido in (("folios", folios), ("procesos", procesos), ("tipos_documentales", tipos),
                              ("auditoria", auditoria)):
        (datos / f"{nombre}.json").write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera los datos ficticios de los mocks del frontend")
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--originales", type=Path, default=ORIGINALES)
    args = parser.parse_args()
    generar(args.datos, args.originales)
    print(f"Datos de los mocks en {args.datos} y originales en {args.originales} (--hoy {HOY_MOCKS})")


if __name__ == "__main__":
    main()
