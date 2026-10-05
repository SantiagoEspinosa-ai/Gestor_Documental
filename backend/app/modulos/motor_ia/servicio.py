"""
API publica de motor_ia (ADR-005): analiza un DocumentoPreparado y devuelve un ResultadoDocumento.
Clasifica, elige la ficha (ADR-006, 2.5), extrae y usa el respaldo si el proveedor principal falla. La MRZ
(sexo y VAL-003) la completa el orquestador despues (spec, seccion 11): este modulo no importa orquestador. Con OCR pobre (spec, seccion 3) reclasifica o extrae con vision. La confianza
de campo y de clasificacion la calcula el codigo (ADR-007, `confianza.py`); la del modelo va a la auditoria.
Reglas deterministas, VAL-00x y recomendacion: validacion.
Decisiones: docs/motor_ia/SPEC_CONFIGURACION.md, seccion 10.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import TypeVar

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.confianza import (
    VerificacionMrz,
    confianza_clasificacion,
    confianzas_de_campos,
    texto_del_documento,
)
from app.modulos.motor_ia.enrutador import crear_enrutador
from app.modulos.motor_ia.interfaces import DocumentoPreparado, Enrutador, ProveedorLLM, ResultadoExtraccion, Tarea
from app.modulos.motor_ia.prompts import (
    formatear_contenido,
    formatear_contexto_rag,
    formatear_campos,
    formatear_esquema,
    formatear_tipos,
    renderizar,
)
from app.modulos.motor_ia.proveedores.base import (
    DESCONOCIDO,
    MAX_CARACTERES_TEXTO,
    ErrorProveedor,
    ErrorRespuestaInvalida,
    InfoLlamada,
    campos_con_formato_invalido,
    combinar_texto_y_vision,
    necesita_reintento_vision,
    obligatorios_vacios,
    recortar_texto,
)
from app.schemas.resultado import (
    Alerta,
    EstadoAnalisis,
    FechaYModelo,
    ReferenciaArchivoOriginal,
    ResultadoDocumento,
    Severidad,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
CONFIANZA_ALERTA_DETERMINISTA = 1.0

_enrutador_por_defecto: Enrutador | None = None


@dataclass
class Analisis:
    """Resultado del analisis y, para la auditoria, las llamadas a los modelos y la confianza que dio el
    modelo (ADR-007: no se usa en reglas; por campo y "clasificacion")."""
    resultado: ResultadoDocumento
    llamadas: list[InfoLlamada] = field(default_factory=list)
    confianzas_modelo: dict[str, float] = field(default_factory=dict)
    version_prompt_clasificacion: str | None = None  # p. ej. clasificacion@v2; None si no se clasifico


__all__ = ["Analisis", "VerificacionMrz", "analizar", "confianzas_de_campos", "texto_del_documento"]


class _FalloProveedor(Exception):
    def __init__(self, ultimo: ErrorProveedor):
        super().__init__(str(ultimo))
        self.ultimo = ultimo


class _Contexto:
    """Estado de un analisis: alertas sin repetir (codigo, campo) y llamadas registradas."""

    def __init__(self, enrutador: Enrutador):
        self.enrutador = enrutador
        self.alertas: list[Alerta] = []
        self.llamadas: list[InfoLlamada] = []

    def alerta(self, codigo: str, severidad: Severidad, mensaje: str, campo: str | None = None) -> None:
        if not any(a.codigo == codigo and a.campo == campo for a in self.alertas):  # ADR-006, 1.3
            self.alertas.append(Alerta(codigo=codigo, mensaje=mensaje, severidad=severidad,
                                       confianza=CONFIANZA_ALERTA_DETERMINISTA, campo=campo))

    def registrar(self, proveedor: ProveedorLLM) -> None:
        """Todas las llamadas de la ultima operacion (con reintento de vision son dos)."""
        infos = getattr(proveedor, "ultimas_llamadas", None) or [getattr(proveedor, "ultima_llamada", None)]
        for info in infos:
            if info is not None and not any(info is x for x in self.llamadas):
                self.llamadas.append(info)

    def con_respaldo(self, tarea: Tarea, tipo: str | None, llamada: Callable[[ProveedorLLM], T]) -> tuple[T, ProveedorLLM]:
        """Principal y, si falla (tambien por JSON invalido), el respaldo. SYS-005 si se usa el respaldo."""
        principal = self.enrutador.obtener(tarea, tipo)
        try:
            return llamada(principal), principal
        except ErrorProveedor as error:
            ultimo = error
            logger.warning("%s: fallo el proveedor principal '%s': %s", tarea.value, principal.nombre, error)
        finally:
            self.registrar(principal)
        respaldo = self.enrutador.respaldo(tarea, tipo)
        if respaldo is not None:
            try:
                resultado = llamada(respaldo)
            except ErrorProveedor as error:
                ultimo = error
                logger.warning("%s: fallo tambien el respaldo '%s': %s", tarea.value, respaldo.nombre, error)
            else:
                self.alerta("SYS-005", Severidad.informativa,
                            f"El proveedor principal fallo y el analisis se hizo con el proveedor de respaldo '{respaldo.nombre}'")
                return resultado, respaldo
            finally:
                self.registrar(respaldo)
        raise _FalloProveedor(ultimo)


def _modelo_usado(proveedor: ProveedorLLM) -> str:
    info = getattr(proveedor, "ultima_llamada", None)
    return info.modelo if info is not None else proveedor.modelo


def _enrutador() -> Enrutador:
    global _enrutador_por_defecto
    if _enrutador_por_defecto is None:
        _enrutador_por_defecto = crear_enrutador()
    return _enrutador_por_defecto


def analizar(doc: DocumentoPreparado, *, folio: str, referencia: ReferenciaArchivoOriginal,
             tipo_confirmado: str | None = None, enrutador: Enrutador | None = None,
             ahora: datetime | None = None, mrz: VerificacionMrz | None = None) -> Analisis:
    """Analiza el documento. Ficha para extraer: tipo_confirmado > declarado > detectado (ADR-006, 2.5).
    Con tipo_confirmado no se clasifica. Tipo desconocido sin declarado ni confirmado: no se extrae.
    `mrz`: la del pasaporte, si el orquestador la encontro; la usa la confianza calculada (ADR-007)."""
    ctx = _Contexto(enrutador or _enrutador())
    fichas = {f.nombre: f for f in configuracion.listar()}
    declarado = doc.tipo_documental_declarado

    paginas, recortado = recortar_texto(doc.paginas)
    doc_modelo = replace(doc, paginas=paginas)
    if recortado:
        ctx.alerta("SYS-003", Severidad.preventiva,
                   f"El texto del documento supera {MAX_CARACTERES_TEXTO} caracteres y se ha recortado; "
                   "los campos de las paginas finales pueden no haberse extraido")
    contenido = formatear_contenido(paginas)
    texto = texto_del_documento(doc.paginas)  # para verificar valores y marcadores (ADR-007), sin recortar
    confianzas_modelo: dict[str, float] = {}

    datos = {
        "folio_solicitud": folio,
        "identificador_unico_documento": doc.identificador_unico_documento,
        "tipo_documental_declarado": declarado,
        "tipo_documental_detectado": None,
        "tipo_documental_confirmado": tipo_confirmado,
        "referencia_archivo_original": referencia,
        "estado_analisis": EstadoAnalisis.completado,
    }
    fecha_modelo: tuple[str, str, str] | None = None  # (proveedor, version_prompt, modelo real)
    version_clasificacion: str | None = None

    ocr_pobre: str | None = None  # motivo si la clasificacion ya detecto un OCR pobre
    try:
        detectado = None
        if tipo_confirmado is None:
            prompt, version = renderizar("clasificacion", contenido=contenido,
                                         tipos_posibles=formatear_tipos(fichas.values()),
                                         contexto_rag=formatear_contexto_rag(doc.contexto_rag))
            clasificacion, proveedor = ctx.con_respaldo(
                Tarea.clasificacion, None, lambda p: p.clasificar(doc_modelo, list(fichas), prompt))
            # Senal 2 de OCR pobre: con texto da desconocido -> se reclasifica con vision y CLS-001 se decide con ella
            reclasificada = _reclasificar_con_vision(ctx, proveedor, doc_modelo, list(fichas), prompt, clasificacion)
            if reclasificada is not None:
                clasificacion = reclasificada
                ocr_pobre = "OCR pobre (la clasificacion con texto dio desconocido)"
            detectado = clasificacion.tipo_documental_detectado
            datos["tipo_documental_detectado"] = detectado
            confianzas_modelo["clasificacion"] = clasificacion.confianza
            ficha_detectada = fichas.get(detectado)
            datos["confianza_clasificacion"] = confianza_clasificacion(ficha_detectada, texto)
            fecha_modelo = (proveedor.nombre, version, _modelo_usado(proveedor))
            version_clasificacion = version
            if declarado is not None and detectado != declarado:
                ctx.alerta("CLS-001", Severidad.critica,
                           f"Tipo declarado '{declarado}' distinto del detectado '{detectado}'")
            # CLS-002 solo con un tipo concreto: con desconocido ya avisa CLS-001 (D4)
            if (ficha_detectada is not None
                    and datos["confianza_clasificacion"] < ficha_detectada.confianza_minima_clasificacion):
                ctx.alerta("CLS-002", Severidad.preventiva,
                           f"Confianza de clasificacion {datos['confianza_clasificacion']:.2f} menor que el minimo "
                           f"{ficha_detectada.confianza_minima_clasificacion:.2f} de '{detectado}'")
        # Con tipo_confirmado no se clasifica: detectado y confianza_clasificacion quedan None (ADR-009, como el
        # stub de la ingesta); el 1,0 lo pone la plataforma (D2).

        tipo = tipo_confirmado or declarado or (detectado if detectado != DESCONOCIDO else None)
        if tipo is not None:
            ficha = configuracion.obtener(tipo)
            prompt, version = renderizar("extraccion", tipo_documental=ficha.nombre, contenido=contenido,
                                         esquema_campos=formatear_esquema(ficha),
                                         campos_a_extraer=formatear_campos(ficha))
            esquema = {n: c.model_dump(mode="json") for n, c in ficha.campos.items()}
            # CLS-001 con un tipo concreto distinto del declarado: los vacios se explican por la ficha equivocada
            cls_concreto = declarado is not None and detectado not in (None, declarado, DESCONOCIDO)
            if ocr_pobre and not cls_concreto and any(p.imagen_png for p in doc_modelo.paginas):
                motivo = f"extraccion con vision: {ocr_pobre}"
                extraccion, proveedor = ctx.con_respaldo(
                    Tarea.extraccion, ficha.nombre,
                    lambda p: p.extraer_con_vision(doc_modelo, esquema, prompt, motivo)
                    if hasattr(p, "extraer_con_vision") else p.extraer(doc_modelo, esquema, prompt))
                modelo = _modelo_usado(proveedor)
            else:
                extraccion, proveedor = ctx.con_respaldo(
                    Tarea.extraccion, ficha.nombre, lambda p: p.extraer(doc_modelo, esquema, prompt))
                extraccion, modelo = _reintento_vision(ctx, proveedor, doc_modelo, esquema, prompt, extraccion,
                                                       cls_concreto)
            fecha_modelo = (proveedor.nombre, version, modelo)
            valores = dict(extraccion.datos_extraidos)
            confianzas_modelo.update(extraccion.nivel_confianza_por_campo)
            evidencias = dict(extraccion.evidencia_por_campo)
            confianzas = confianzas_de_campos(valores, ficha, texto, mrz if ficha.nombre == "pasaporte" else None)
            datos.update(datos_extraidos=valores, nivel_confianza_por_campo=confianzas, evidencia_por_campo=evidencias)
    except _FalloProveedor as fallo:
        if isinstance(fallo.ultimo, ErrorRespuestaInvalida):
            ctx.alerta("SYS-002", Severidad.critica, "La respuesta del modelo no es un JSON valido tras el reintento de correccion")
        else:
            ctx.alerta("SYS-001", Severidad.critica, "Fallo del proveedor principal y no hay respaldo disponible")
        datos["estado_analisis"] = EstadoAnalisis.error

    if fecha_modelo is not None:
        nombre_proveedor, version, modelo = fecha_modelo
        datos["fecha_y_modelo_utilizado"] = FechaYModelo(
            fecha_analisis=ahora or datetime.now(timezone.utc), proveedor=nombre_proveedor,
            modelo=modelo, version_prompt=version)
    datos["alertas_encontradas"] = ctx.alertas
    return Analisis(ResultadoDocumento(**datos), ctx.llamadas, confianzas_modelo, version_clasificacion)


def _reclasificar_con_vision(ctx: _Contexto, proveedor: ProveedorLLM, doc: DocumentoPreparado, tipos: list[str],
                            prompt: str, clasificacion):
    """Si la clasificacion con texto da desconocido y hay imagenes, reclasifica con vision. Devuelve la nueva
    clasificacion, o None si no aplica o la vision falla (se conserva la de texto)."""
    info = getattr(proveedor, "ultima_llamada", None)
    if (clasificacion.tipo_documental_detectado != DESCONOCIDO or info is None or info.entrada != "texto"
            or not hasattr(proveedor, "clasificar_con_vision") or not any(p.imagen_png for p in doc.paginas)):
        return None
    motivo = "reclasificacion con vision: la clasificacion con texto dio desconocido"
    try:
        return proveedor.clasificar_con_vision(doc, tipos, prompt, motivo)
    except ErrorProveedor as error:
        logger.warning("clasificacion: fallo la reclasificacion con vision: %s", error)
        fallida = getattr(proveedor, "ultima_llamada", None)
        if fallida is not None and fallida is not info:
            fallida.motivo = f"{motivo}; fallo ({error}): se conserva la clasificacion con texto"
        return None
    finally:
        ctx.registrar(proveedor)


def _reintento_vision(ctx: _Contexto, proveedor: ProveedorLLM, doc: DocumentoPreparado, esquema: dict, prompt: str,
                      extraccion: ResultadoExtraccion, cls_concreto: bool) -> tuple[ResultadoExtraccion, str]:
    """Riesgo 2 del plan (OCR malo -> vision). Si la extraccion se hizo con texto y deja a null la mitad o mas
    de los obligatorios (senal 3) o algun campo con formato invalido (senal 4), se repite con vision; manda la
    vision y el texto rellena sus nulos. No se reintenta si salta CLS-001 con un tipo concreto distinto del
    declarado: los vacios se explican por la ficha equivocada. Si el reintento falla, se conserva el texto.
    Devuelve (extraccion, modelo real usado)."""
    modelo = _modelo_usado(proveedor)
    info = getattr(proveedor, "ultima_llamada", None)
    if (info is None or info.entrada != "texto" or not hasattr(proveedor, "extraer_con_vision")
            or not any(p.imagen_png for p in doc.paginas)):
        return extraccion, modelo
    vacios, total = obligatorios_vacios(extraccion, esquema)
    por_vacios = necesita_reintento_vision(extraccion, esquema)
    formato = campos_con_formato_invalido(extraccion, esquema)
    if not por_vacios and not formato:
        return extraccion, modelo
    senales = ([f"{vacios}/{total} campos obligatorios vacios"] if por_vacios else []) + \
        ([f"formato invalido en {', '.join(formato)}"] if formato else [])
    if cls_concreto:
        info.motivo = (f"sin reintento con vision ({'; '.join(senales)}): "
                       "el tipo declarado no coincide con el detectado (CLS-001)")
        return extraccion, modelo
    motivo = "reintento con vision: " + "; ".join(senales) + " con texto"
    try:
        vision = proveedor.extraer_con_vision(doc, esquema, prompt, motivo)
    except ErrorProveedor as error:
        logger.warning("extraccion: fallo el reintento con vision: %s", error)
        fallida = getattr(proveedor, "ultima_llamada", None)
        if fallida is not None and fallida is not info:
            fallida.motivo = f"{motivo}; fallo ({error}): se conserva el resultado con texto"
        return extraccion, modelo
    finally:
        ctx.registrar(proveedor)
    return combinar_texto_y_vision(extraccion, vision), _modelo_usado(proveedor)
