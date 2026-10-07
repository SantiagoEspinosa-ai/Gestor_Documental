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
alertas_expediente, EXP-001 (campo = tipo que falta), una correccion, dos documentos en error (uno con
SYS-001 y otro por fallo de S3 o del motor, sin SYS-00x ni documento_procesado), uno pendiente y un
folio cerrado (aprobado), que es antecedente del folio 2 (misma referencia_externa, ADR-010 C), y el folio
3 sin referencia (sin antecedentes). Comparaciones, recomendacion global, mensajes de CMP-001 y EXP-001 y detalle
de la auditoria, como la API del PR #9. Tres alertas informativas, todas posibles con
la configuracion por defecto: dos VAL-003 (nacionalidad y sexo tomados de la MRZ) en el pasaporte
escaneado del folio 1 y VAL-004 (proveedor opcional no leido, null) en el comprobante del folio 2.
Sin SYS-005: su unico respaldo es OpenRouter, que con PERMITIR_PROVEEDORES_NO_PRIVADOS=false no se usa
nunca (ADR-003); un fallo de Ollama da SYS-001 (folio 3). Un campo sin valor es null, nunca "".
Modelos: siempre Ollama, gemma4:e2b para pdf_digital y qwen2.5vl:3b para escaneados e imagenes.
Como la salida real del motor (ensayo del 2026-10-06, H3): version_prompt extraccion_<tipo>@v3 (y
clasificacion@v2 en el documento no reconocido), evidencia pagina_1:seccion_central, fecha_analisis con
microsegundos y, en el pasaporte del folio 1, una fecha_expedicion que el OCR leyo y no se puede normalizar
("30 SEP 2021"), guardada tal cual. Los JSON son el ESTADO de los mocks (como la BD): guardan los valores
ficticios completos y los handlers enmascaran los sensibles al responder, como la API (ADR-010).

Es determinista: sin azar ni fecha actual. backend/tests/test_generar_datos_mock.py comprueba que
reproduce exactamente los ficheros del repo, y test_contrato_frontend.py que son validos.
Si cambias el contrato o los casos, regenera con este script (no edites los JSON a mano).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "frontend" / "src" / "mocks" / "datos"
ORIGINALES = RAIZ / "frontend" / "public" / "mock-originales"
HOY_MOCKS = date(2026, 9, 30)
# ADR-009: valor reservado de tipo_documental_detectado (clasificado, pero sin ficha); nunca es una ficha
TIPO_DESCONOCIDO = "desconocido"
REVISOR, INTEGRADOR = "revisor.demo", "integrador.demo"  # usuarios de frontend/src/mocks/usuarios.ts
# ADR-012: otro integrador ficticio, sin usuario para entrar; sus folios dan 404 a integrador.demo
INTEGRADOR_OTRO = "integrador.otro"
# Modelos de .env.example y docs/motor_ia/pruebas_ollama.md (PERSONA_2): texto para pdf_digital y vision
# para pdf_escaneado e imagen. Siempre Ollama: con PERMITIR_PROVEEDORES_NO_PRIVADOS=false (ADR-003) el
# respaldo comercial no se usa nunca, asi que los mocks no tienen SYS-005.
PROVEEDOR = "ollama"
MODELO_POR_MODALIDAD = {"digital": "gemma4:e2b", "escaneado": "qwen2.5vl:3b", "foto": "qwen2.5vl:3b"}
# Como el motor real (ensayo con el motor del 2026-10-06): un prompt de extraccion por tipo, y el de clasificacion
# para un documento que no se reconoce (no se extrae nada)
VERSION_PROMPT_CLASIFICACION = "clasificacion@v2"
# Evidencia como la valida el motor (_EVIDENCIA en motor_ia/proveedores/base.py): pagina y seccion
EVIDENCIA = "pagina_1:seccion_central"


def version_prompt(tipo: str) -> str:
    return f"extraccion_{tipo}@v3"
# detalle de documento_procesado: datos de auditoria del motor sin modelo ni version_prompt (van en sus
# columnas), como la API del PR #9 (api/README.md)
DETALLE_PROCESADO = {"proveedor": PROVEEDOR, "respaldo_usado": False}


def _cargar_generador():
    spec = importlib.util.spec_from_file_location("generar_fixtures", RAIZ / "scripts" / "generar_fixtures.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def momento(dia: int, hora: int, minuto: int) -> datetime:
    return datetime(2026, 9, dia, hora, minuto, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_analisis(dt: datetime, uid: str) -> str:
    """fecha_analisis con microsegundos, como la serializa la API (datetime.now() del motor); deterministas,
    sacados del id del documento"""
    micro = int(hashlib.sha256(uid.encode()).hexdigest()[:8], 16) % 1_000_000
    return dt.replace(microsecond=micro).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def campo_api(definicion: dict) -> dict:
    """Un campo como lo devuelve GET /tipos-documentales (`_campo` de ingesta/tipos.py): `sensible` siempre
    (false si la ficha no lo marca; ADR-010 A6) y `patron` solo si existe, con el mismo orden de claves."""
    campo = {"tipo": definicion["tipo"], "obligatorio": bool(definicion.get("obligatorio", False)),
             "sensible": bool(definicion.get("sensible", False))}
    if definicion.get("patron"):
        campo["patron"] = definicion["patron"]
    return campo


def confianza_campo(tipo: str, campo: str) -> float:
    """Determinista y plausible (0.86..0.98), sin azar."""
    h = int(hashlib.sha256(f"{tipo}.{campo}".encode()).hexdigest(), 16)
    return round(0.86 + (h % 13) / 100, 2)


def pesa(a: dict) -> bool:
    return a["severidad"] in ("critica", "bloqueante") and a["aplica"] is not False


# Comparaciones como validacion/comparaciones.py de la API (PR #9): mismos formatos de fecha y misma
# normalizacion. Se copia la logica (no se importa backend/) para que el script siga siendo independiente.
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


def normalizar_texto(valor) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos).strip().upper()


def normalizar_fecha(valor) -> str:
    texto = str(valor).strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return normalizar_texto(valor)


def vacio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def tipo_efectivo(doc: dict) -> str | None:
    return doc["tipo_documental_confirmado"] or doc["tipo_documental_detectado"] or doc["tipo_documental_declarado"]


class DatosMock:
    """Construye folios, documentos, alertas y auditoria con contadores propios."""

    def __init__(self, gf, fixtures: Path, originales: Path):
        self.gf, self.fixtures, self.originales = gf, fixtures, originales
        self.fichas = gf.cargar_fichas()
        self.contador_alertas = 0
        self.auditoria: list[dict] = []
        self.hashes_por_folio: dict[str, set[str]] = {}  # para `duplicado` en la auditoria de la subida
        self.duenos: dict[str, str] = {}  # folio -> integrador que lo creo (ADR-012): sube sus documentos

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
                  confianzas=None, correcciones=(), vacios=(), fallo_plataforma=False, no_reconocido=False,
                  ilegibles=None) -> dict:
        """`vacios`: campos opcionales que el analisis no leyo (null, confianza 0, sin evidencia y VAL-004).
        `fallo_plataforma` (con estado="error"): fallo de S3 o excepcion del motor. Como la API, el documento
        queda en error sin Resultado, sin SYS-00x y sin entrada documento_procesado en la auditoria.
        `ilegibles`: {campo: texto} que el OCR leyo pero no se puede normalizar (p. ej. una fecha "30 SEP 2021");
        se guarda tal cual, como lo devolveria el motor, sin simular las reglas que dispararia.
        `no_reconocido`: subido sin tipo declarado y el motor no lo reconoce (ADR-009, punto 4): detectado
        `desconocido`, sin datos ni alertas del motor y con la EXP-002 de la plataforma. `tipo` solo elige
        el fichero ficticio."""
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
               "tipo_documental_declarado": None if no_reconocido else tipo, "tipo_documental_detectado": None,
               "tipo_documental_confirmado": None, "confianza_clasificacion": None,
               "datos_extraidos": {}, "nivel_confianza_por_campo": {}, "evidencia_por_campo": {},
               "reglas_cumplidas_e_incumplidas": {"cumplidas": [], "incumplidas": []},
               "alertas_encontradas": list(alertas_extra), "correcciones": [], "recomendacion": None,
               "estado_analisis": estado, "fecha_y_modelo_utilizado": None,
               "referencia_archivo_original": {
                   "nombre_archivo": archivo, "ruta": f"onboarding/2026/{secuencia:06d}/{uid}.{ext}",
                   "hash": hash_}}
        # Mismo detalle que la API real: sin nombre_archivo (los nombres de fichero suelen llevar el de la persona)
        self.auditar(self.duenos[folio], "documento_subido", folio, uid,
                     {"hash_sha256": hash_, "tamano_bytes": len(datos), "duplicado": duplicado}, subido)
        if estado != "completado":
            if estado == "error" and not fallo_plataforma:  # el motor devolvio un resultado en error (SYS-00x)
                self.auditar(None, "documento_procesado", folio, uid, DETALLE_PROCESADO,
                             subido + timedelta(seconds=40), MODELO_POR_MODALIDAD[modalidad], version_prompt(tipo))
            return doc
        if no_reconocido:
            modelo = MODELO_POR_MODALIDAD[modalidad]
            doc.update({
                "tipo_documental_detectado": TIPO_DESCONOCIDO, "recomendacion": "revision_manual",
                "fecha_y_modelo_utilizado": {"fecha_analisis": iso_analisis(subido + timedelta(seconds=40), uid),
                                             "proveedor": PROVEEDOR, "modelo": modelo,
                                             "version_prompt": VERSION_PROMPT_CLASIFICACION}})
            # Como expediente.recalcular_exp002: "desconocido" no es un tipo del proceso
            doc["alertas_encontradas"] = [self.alerta("EXP-002", "Tipo de documento no reconocido", "informativa",
                                                      TIPO_DESCONOCIDO)] + doc["alertas_encontradas"]
            self.auditar(None, "documento_procesado", folio, uid, DETALLE_PROCESADO,
                         subido + timedelta(seconds=40), modelo, VERSION_PROMPT_CLASIFICACION)
            return doc
        ficha = self.fichas[tipo]
        persona = gf.PERSONAS_FICTICIAS[gf.CASOS[caso]["persona"]]
        valores = gf.valores_documento(tipo, persona, caso, HOY_MOCKS)
        incumplidas = gf.evaluar_reglas(ficha, valores, HOY_MOCKS)
        ids_incumplidas = [a["codigo"].removeprefix("REG-") for a in incumplidas]
        obligatorios = [c for c in vacios if ficha["campos"][c]["obligatorio"]]
        if obligatorios:
            raise ValueError(f"{tipo}: {obligatorios} son obligatorios; vacios solo admite campos opcionales (VAL-004)")
        proveedor, modelo, prompt = PROVEEDOR, MODELO_POR_MODALIDAD[modalidad], version_prompt(tipo)
        doc.update({
            "tipo_documental_detectado": tipo, "confianza_clasificacion": 0.94,
            "datos_extraidos": {c: v.isoformat() if isinstance(v, date) else v
                                for c, v in ((c, valores[c]) for c in ficha["campos"])},
            "nivel_confianza_por_campo": {c: confianza_campo(tipo, c) for c in ficha["campos"]} | (confianzas or {}),
            "evidencia_por_campo": {c: EVIDENCIA for c in ficha["campos"]},
            "reglas_cumplidas_e_incumplidas": {
                "cumplidas": [r["id"] for r in ficha["reglas"] if r["id"] not in ids_incumplidas],
                "incumplidas": ids_incumplidas},
            "fecha_y_modelo_utilizado": {"fecha_analisis": iso_analisis(subido + timedelta(seconds=40), uid),
                                         "proveedor": proveedor, "modelo": modelo, "version_prompt": prompt},
        })
        doc["datos_extraidos"].update(ilegibles or {})
        for campo in vacios:  # sin valor = null (nunca ""), confianza 0 (ADR-007) y sin evidencia
            doc["datos_extraidos"][campo] = None
            doc["nivel_confianza_por_campo"][campo] = 0.0
            del doc["evidencia_por_campo"][campo]
        doc["alertas_encontradas"] = (
            [self.alerta(a["codigo"], a["motivo"], a["severidad"], a["campo"]) for a in incumplidas]
            + [self.alerta("VAL-004", f"Falta el campo opcional {c}", "informativa", c) for c in vacios]
            + doc["alertas_encontradas"])
        for campo, anterior, cuando in correcciones:
            doc["correcciones"].append({"campo": campo, "valor_anterior": anterior,
                                        "valor_nuevo": doc["datos_extraidos"][campo], "usuario": REVISOR,
                                        "fecha": iso(cuando)})
            doc["nivel_confianza_por_campo"][campo] = 1.0
            doc["evidencia_por_campo"][campo] = "correccion_revisor"
        bajas = any(v < ficha["confianza_minima_campo"] for v in doc["nivel_confianza_por_campo"].values())
        doc["recomendacion"] = "revision_manual" if bajas or any(pesa(a) for a in doc["alertas_encontradas"]) else "aprobar"
        self.auditar(None, "documento_procesado", folio, uid, DETALLE_PROCESADO,
                     subido + timedelta(seconds=40), modelo, prompt)
        for campo, _, cuando in correcciones:  # un PATCH por correccion: {campos: [...]}, como la API
            self.auditar(REVISOR, "dato_corregido", folio, uid, {"campos": [campo]}, cuando)
        return doc

    def comparaciones(self, documentos) -> list[dict]:
        """Como validacion.comparar (PR #9): por campo, los documentos completados con valor de los tipos de
        un par cuyos dos lados tienen valor; con menos de 2 no hay comparacion; los vacios no participan."""
        relaciones: dict[str, set[frozenset]] = {}
        for tipo, ficha in self.fichas.items():
            for otro, campos in (ficha.get("comparaciones") or {}).items():
                for campo in campos or []:
                    relaciones.setdefault(campo, set()).add(frozenset((tipo, otro)))
        completos = [d for d in documentos if d["estado_analisis"] == "completado"]
        resultado = []
        for campo, pares in sorted(relaciones.items()):
            con_valor = [d for d in completos if tipo_efectivo(d) and not vacio(d["datos_extraidos"].get(campo))]
            tipos_con_valor = {tipo_efectivo(d) for d in con_valor}
            tipos = {t for par in pares if par <= tipos_con_valor for t in par}
            participantes = [d for d in con_valor if tipo_efectivo(d) in tipos]
            if len(participantes) < 2:
                continue
            tipo_campo = lambda d: self.fichas[tipo_efectivo(d)]["campos"].get(campo, {}).get("tipo")
            normalizados = {normalizar_fecha(d["datos_extraidos"][campo]) if tipo_campo(d) == "fecha"
                            else normalizar_texto(d["datos_extraidos"][campo]) for d in participantes}
            resultado.append({"campo": campo, "coincide": len(normalizados) == 1,
                              "valores": {d["identificador_unico_documento"]: d["datos_extraidos"][campo]
                                          for d in participantes}})
        return resultado

    def crear_folio(self, folio, dueno, cuando) -> None:
        """folio_creado con su integrador: los mocks sacan de aqui el dueno del folio (ADR-012)."""
        self.duenos[folio] = dueno
        self.auditar(dueno, "folio_creado", folio, None, {}, cuando)

    def recomendacion_global(self, documentos, alertas) -> str:
        """Como expediente/recomendacion.py (PR #9); no usa la recomendacion por documento (es del motor)."""
        if not documentos or any(d["estado_analisis"] != "completado" for d in documentos):
            return "revision_manual"
        if any(pesa(a) for a in alertas):
            return "revision_manual"
        for d in documentos:
            ficha = self.fichas.get(tipo_efectivo(d))
            if (ficha is None or d["confianza_clasificacion"] is None
                    or d["confianza_clasificacion"] < ficha["confianza_minima_clasificacion"]
                    or any(c < ficha["confianza_minima_campo"] for c in d["nivel_confianza_por_campo"].values())):
                return "revision_manual"
        return "aprobar"

    def expediente(self, folio, referencia, solicitado, documentos, alertas_expediente=(), decision=None,
                   resumen=False) -> dict:
        todas = [a for d in documentos for a in d["alertas_encontradas"]] + list(alertas_expediente)
        exp = {"folio": folio, "proceso": "onboarding", "referencia_externa": referencia,
               "fecha_solicitud": iso(solicitado), "estado_general": "en_revision", "documentos": documentos,
               "comparaciones": self.comparaciones(documentos), "alertas_expediente": list(alertas_expediente),
               "recomendacion_global": self.recomendacion_global(documentos, todas), "decision_humana": None,
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
        self.crear_folio(f, INTEGRADOR, t0)
        d1 = self.documento(f, s, 1, "vencido", "pasaporte", "escaneado", t0 + timedelta(minutes=1),
                            alertas_extra=[self.alerta("VAL-003", f"Valor de {c} tomado de la MRZ: no se leyo en la "
                                                       "zona visual", "informativa", c) for c in ("nacionalidad", "sexo")],
                            ilegibles={"fecha_expedicion": "30 SEP 2021"})  # fecha que no se puede normalizar
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
        self.crear_folio(f, INTEGRADOR, t0)
        d1 = self.documento(f, s, 1, "domicilio_distinto", "credencial_elector", "escaneado", t0 + timedelta(minutes=1),
                            correcciones=[("nombre_completo", "ANA EJEMPL0 PRUEBA", t0 + timedelta(minutes=25))])
        d2 = self.documento(f, s, 2, "domicilio_distinto", "comprobante_domicilio", "foto", t0 + timedelta(minutes=2),
                            vacios=("proveedor",))
        d3 = self.documento(f, s, 3, "domicilio_distinto", "pasaporte", "digital", t0 + timedelta(minutes=30),
                            estado="pendiente")
        folios.append(self.expediente(f, "CLI-000102", t0, [d1, d2, d3], [
            self.alerta("CMP-001", "Los documentos no coinciden en domicilio", "critica", "domicilio")]))

        # 3. Ana, falta el comprobante: EXP-001 (campo = tipo que falta) y dos documentos en error: uno con
        # SYS-001 (el motor devolvio el error) y otro por un fallo de S3 o del motor, sin SYS-00x. El
        # comprobante en error no cubre su tipo: EXP-001 sigue (solo cuentan los completados). Y un documento
        # sin tipo declarado que el motor no reconoce (ADR-009): EXP-002 y no cubre ningun requerido
        f, s, t0 = "ONB-2026-000003", 3, momento(30, 8, 5)
        self.crear_folio(f, INTEGRADOR_OTRO, t0)
        d1 = self.documento(f, s, 1, "sano", "credencial_elector", "digital", t0 + timedelta(minutes=1))
        d2 = self.documento(f, s, 2, "sano", "pasaporte", "foto", t0 + timedelta(minutes=2), estado="error",
                            alertas_extra=[self.alerta("SYS-001", "Fallo del proveedor principal y sin respaldo", "critica")])
        d3 = self.documento(f, s, 3, "sano", "comprobante_domicilio", "escaneado", t0 + timedelta(minutes=3),
                            estado="error", fallo_plataforma=True)
        # Fichero que ningun otro documento de los datos usa: el clasificador de los mocks reutiliza el
        # analisis de un documento con el mismo SHA-256, y no debe dar "desconocido" a otras subidas
        d4 = self.documento(f, s, 4, "sano", "pasaporte", "escaneado", t0 + timedelta(minutes=4), no_reconocido=True)
        folios.append(self.expediente(f, None, t0, [d1, d2, d3, d4], [
            self.alerta("EXP-001", f"Falta el documento requerido: {self.fichas['comprobante_domicilio']['nombre_visible']}",
                        "bloqueante", "comprobante_domicilio")]))

        # 4. Ana, todo correcto: folio cerrado (aprobado) con resumen. Misma referencia que el folio 2: es su
        # antecedente (ADR-010 C, H16)
        f, s, t0 = "ONB-2026-000004", 4, momento(25, 10, 0)
        self.crear_folio(f, INTEGRADOR_OTRO, t0)
        docs = [self.documento(f, s, i + 1, "sano", tipo, "digital", t0 + timedelta(minutes=i + 1))
                for i, tipo in enumerate(("pasaporte", "credencial_elector", "comprobante_domicilio"))]
        folios.append(self.expediente(f, "CLI-000102", t0, docs,
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
    # Como la API: un webhook_url vacio en procesos.yaml llega como null (core/procesos.py)
    procesos = [{"nombre": nombre, **{k: p[k] for k in claves_proceso}, "webhook_url": p["webhook_url"] or None}
                for nombre, p in procesos_yaml.items()]
    claves_ficha = ("nombre", "nombre_visible", "categoria", "descripcion", "formatos_permitidos", "campos",
                    "confianza_minima_clasificacion", "confianza_minima_campo", "reglas", "comparaciones")
    tipos = [{**{k: ficha[k] for k in claves_ficha}, "campos": {c: campo_api(d) for c, d in ficha["campos"].items()}}
             for ficha in constructor.fichas.values()]
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
