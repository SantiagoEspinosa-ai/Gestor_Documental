"""Resumen Markdown del expediente (etapa 3): `generar(expediente, fichas, generado_en) -> str`.

Puro y determinista: sin BD ni S3, y con la misma entrada da el mismo texto. Lo guarda en S3 y lo
regenera en cada cambio `servicio.py`. Plantilla `plantillas/resumen.md.j2` (Jinja, sin autoescape:
es Markdown; solo listas, sin tablas, para verse bien con react-markdown sin plugins); todo valor que viene del OCR o del revisor se escapa aqui antes de llegar a la plantilla.

La persona se identifica por la `referencia_externa` del folio, nunca por su nombre (ADR-004): el
nombre solo aparece, si se extrajo, como un dato mas de la tabla de su documento. El nombre del fichero
tampoco sale, porque suele llevarlo.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.modulos.configuracion import servicio as configuracion
from app.schemas.resultado import Alerta, ResultadoDocumento, ResultadoExpediente

_PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
_entorno = Environment(loader=FileSystemLoader(_PLANTILLAS), autoescape=False, undefined=StrictUndefined,
                       trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)

_ESPECIALES = "\\|`*_[]<>"  # la barra invertida va primero: escapa a las demas
_SEVERIDADES = (("bloqueante", "Bloqueantes"), ("critica", "Criticas"), ("preventiva", "Preventivas"),
                ("informativa", "Informativas"))
_ESTADO_GENERAL = {"en_revision": "En revision", "aprobado": "Aprobado", "rechazado": "Rechazado"}
_ESTADO_ANALISIS = {"pendiente": "Pendiente", "procesando": "Procesando", "completado": "Completado",
                    "error": "Error"}
_RECOMENDACION = {"aprobar": "Aprobar", "revision_manual": "Revision manual", "rechazar": "Rechazar"}
_DECISION = {"aprobar": "Aprobado", "rechazar": "Rechazado"}


def escapar(valor: Any) -> str:
    """Valor de texto seguro para Markdown: sin saltos de linea (no rompen tablas) y con |, `, *, _, [, ],
    <, > y \\ escapados (no abren formato, enlaces ni HTML)."""
    texto = " ".join(str(valor).splitlines())
    for caracter in _ESPECIALES:
        texto = texto.replace(caracter, "\\" + caracter)
    return texto


def enmascarar_para_resumen(datos: dict[str, Any], ficha: dict | None) -> dict[str, Any]:
    """ADR-010 A5: aplicar la mascara a los campos sensible cuando llegue H15. Unico punto del resumen.
    Con H15, este punto y `core/webhooks.enmascarar_para_webhook` usaran la MISMA funcion de mascara
    (`****` + 4 ultimos caracteres), para que el resumen y el webhook no se separen."""
    return datos


def _fecha(valor: datetime | None) -> str:
    if valor is None:
        return "—"
    if valor.tzinfo is not None:
        valor = valor.astimezone(timezone.utc)
    return valor.strftime("%Y-%m-%d %H:%M UTC")


def _nombre_campo(campo: str) -> str:
    return escapar(campo.replace("_", " ").capitalize())


def _nombre_tipo(tipo: str | None, fichas: dict[str, dict]) -> str:
    if not tipo:
        return "Sin tipo"
    if tipo == configuracion.NOMBRE_RESERVADO:  # ADR-009: nunca se busca su ficha
        return "Tipo no reconocido"
    return escapar((fichas.get(tipo) or {}).get("nombre_visible") or tipo)


def _ficha(tipo: str | None, fichas: dict[str, dict]) -> dict | None:
    return None if not tipo or tipo == configuracion.NOMBRE_RESERVADO else fichas.get(tipo)


def _alertas(alertas: list[Alerta]) -> list[dict]:
    estado = {None: "sin revisar", False: "falso positivo", True: "confirmada"}
    grupos = []
    for severidad, titulo in _SEVERIDADES:
        de_esta = [a for a in alertas if a.severidad.value == severidad]
        if de_esta:
            grupos.append({"titulo": titulo, "alertas": [
                {"codigo": escapar(a.codigo), "campo": escapar(a.campo) if a.campo else None,
                 "mensaje": escapar(a.mensaje), "estado": estado[a.aplica]} for a in de_esta]})
    return grupos


def _documento(n: int, doc: ResultadoDocumento, fichas: dict[str, dict]) -> dict:
    efectivo = doc.tipo_documental_confirmado or doc.tipo_documental_detectado or doc.tipo_documental_declarado
    extraccion = doc.tipo_documental_confirmado or doc.tipo_documental_declarado or doc.tipo_documental_detectado
    ficha = _ficha(extraccion, fichas)
    datos = enmascarar_para_resumen(doc.datos_extraidos, ficha)
    campos = list(dict.fromkeys([*((ficha or {}).get("campos") or {}), *datos]))
    corregidos = {c.campo for c in doc.correcciones}
    filas = [{"campo": _nombre_campo(c),
              "valor": "no detectado" if datos.get(c) is None else escapar(datos[c]),
              "corregido": c in corregidos} for c in campos]
    return {"n": n, "tipo": _nombre_tipo(efectivo, fichas), "estado": _ESTADO_ANALISIS[doc.estado_analisis.value],
            "filas": filas, "alertas": _alertas(doc.alertas_encontradas)}


def _comparaciones(expediente: ResultadoExpediente, fichas: dict[str, dict]) -> list[dict]:
    por_id = {d.identificador_unico_documento: (i, d) for i, d in enumerate(expediente.documentos, start=1)}
    resultado = []
    for comparacion in expediente.comparaciones:
        valores = []
        for documento_id, valor in comparacion.valores.items():
            n, doc = por_id.get(documento_id, ("?", None))
            extraccion = (doc.tipo_documental_confirmado or doc.tipo_documental_declarado
                          or doc.tipo_documental_detectado) if doc else None
            efectivo = (doc.tipo_documental_confirmado or doc.tipo_documental_detectado
                        or doc.tipo_documental_declarado) if doc else None
            enmascarado = enmascarar_para_resumen({comparacion.campo: valor}, _ficha(extraccion, fichas))
            texto = "no detectado" if enmascarado[comparacion.campo] is None else escapar(enmascarado[comparacion.campo])
            valores.append({"n": n, "tipo": _nombre_tipo(efectivo, fichas), "valor": texto})
        resultado.append({"campo": _nombre_campo(comparacion.campo),
                          "coincide": "coincide" if comparacion.coincide else "no coincide", "valores": valores})
    return resultado


def generar(expediente: ResultadoExpediente, fichas: dict[str, dict], generado_en: datetime) -> str:
    """Markdown del expediente. `fichas`: {nombre: ficha con la forma de GET /tipos-documentales}."""
    decision = None
    if expediente.decision_humana is not None:
        decision = {"decision": _DECISION[expediente.decision_humana.value],
                    "comentario": escapar(expediente.comentario_decision) if expediente.comentario_decision else "—",
                    "usuario": escapar(expediente.usuario_decision or "—"), "fecha": _fecha(expediente.fecha_decision)}
    contexto = {
        "folio": escapar(expediente.folio),
        "referencia": escapar(expediente.referencia_externa) if expediente.referencia_externa else "sin referencia",
        "proceso": escapar(expediente.proceso),
        "fecha_solicitud": _fecha(expediente.fecha_solicitud),
        "estado_general": _ESTADO_GENERAL[expediente.estado_general.value],
        "recomendacion": _RECOMENDACION.get(expediente.recomendacion_global.value, "—")
        if expediente.recomendacion_global else "—",
        "decision": decision,
        "documentos": [_documento(i, d, fichas) for i, d in enumerate(expediente.documentos, start=1)],
        "alertas_expediente": _alertas(expediente.alertas_expediente),
        "comparaciones": _comparaciones(expediente, fichas),
        "generado_en": _fecha(generado_en),
    }
    return _entorno.get_template("resumen.md.j2").render(**contexto)
