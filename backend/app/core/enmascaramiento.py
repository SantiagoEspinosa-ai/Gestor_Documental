"""Mascara de los campos sensibles (ADR-010 A2 y A5): la UNICA funcion de mascara de la plataforma.

`****` + los 4 ultimos caracteres; con 4 o menos, `****`; `None` sigue siendo `None`. La usan las
respuestas de la API, el webhook y el `resumen.md`, para que no se separen.

Puro y sin importar modulos (ADR-005): quien llama pasa los nombres de los campos sensibles (los de la
ficha, `sensible: true`). Nunca muta la entrada: devuelve una copia. La BD y la logica interna (reglas,
comparaciones, recomendacion) siguen con los valores reales; esto es solo para la salida.
"""
import re
from typing import Any

from app.core import logs
from app.schemas.resultado import ResultadoDocumento, ResultadoExpediente

MASCARA = "****"
# Linea MRZ: 30 o mas caracteres de [A-Z0-9<] seguidos. La 1 del pasaporte empieza por "P<" (tipo, pais y
# nombre) y se deja; cualquier otra (la 2 lleva el numero de pasaporte) se tapa entera (ADR-010 A5)
_MRZ = re.compile(r"(?<![A-Z0-9<])[A-Z0-9<]{30,}(?![A-Z0-9<])")
# Evidencia que es una ubicacion, no texto del documento: la misma validacion que `_EVIDENCIA` del motor
# (motor_ia/proveedores/base.py) o "correccion_revisor" (ADR-006 2.4)
_UBICACION = re.compile(r"pagina_[1-9]\d*(:.+)?|correccion_revisor")


def mascara(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = valor if isinstance(valor, str) else str(valor)
    return f"{MASCARA}{texto[-4:]}" if len(texto) > 4 else MASCARA


def _tapar_mrz(texto: str) -> str:
    return _MRZ.sub(lambda m: m.group(0) if m.group(0).startswith("P<") else MASCARA, texto)


def literales_sensibles(resultado: ResultadoDocumento, sensibles: set[str]) -> list[str]:
    """Valores sensibles que pueden aparecer escritos en una evidencia o en un texto libre: el vigente, el leido por el motor
    (antes de corregir) y cada corregido. Los mas largos primero, para no dejar trozos."""
    valores = [resultado.datos_extraidos.get(campo) for campo in sensibles]
    for correccion in resultado.correcciones:
        if correccion.campo in sensibles:
            valores += [correccion.valor_anterior, correccion.valor_nuevo]
    textos = {str(v) for v in valores if v is not None and str(v)}
    return sorted(textos, key=len, reverse=True)


def _evidencia(campo: str, texto: str, literales: list[str], sensibles: set[str]) -> str:
    # ADR-010 A5 (acordado con PERSONA_2 al implementarlo): la evidencia hoy es una ubicacion
    # (pagina_N[:seccion], correccion_revisor), no texto del documento. La de un campo sensible se conserva
    # si es una ubicacion; cualquier otro contenido se tapa entero. Despues, en todas, MRZ y literales
    if campo in sensibles and not _UBICACION.fullmatch(texto):
        return MASCARA
    texto = _tapar_mrz(texto)  # antes que los literales: si no, la mascara partiria la linea MRZ
    for literal in literales:
        texto = texto.replace(literal, mascara(literal))
    return texto


def enmascarar_texto(texto: str, literales: list[str]) -> str:
    """Texto libre (p. ej. el motivo de "mostrar", ADR-010 A4c) listo para guardar o devolver: cada literal
    sensible del documento (`literales_sensibles`) pasa por `mascara`, y despues `logs.tapar`, la misma
    barrera que los logs (A5), tapa lo que tenga forma de CURP, clave de elector, pasaporte o MRZ, sea o no
    del documento. Lo que tapa `logs.tapar` queda en `****` sin los 4 ultimos: en un texto libre no hacen
    falta y es mas seguro."""
    for literal in literales:
        texto = texto.replace(literal, mascara(literal))
    return logs.tapar(texto)


def enmascarar_resultado(resultado: ResultadoDocumento, sensibles: set[str]) -> ResultadoDocumento:
    """Copia de `resultado` con los campos sensibles enmascarados en datos, evidencias y correcciones.

    En TODAS las evidencias se tapa ademas la linea 2 de la MRZ, aunque el documento no tenga campos
    sensibles: contiene el numero de pasaporte aunque no coincida letra a letra con el valor leido."""
    literales = literales_sensibles(resultado, sensibles)
    datos = {campo: mascara(valor) if campo in sensibles else valor
             for campo, valor in resultado.datos_extraidos.items()}
    evidencias = {campo: _evidencia(campo, texto, literales, sensibles)
                  for campo, texto in resultado.evidencia_por_campo.items()}
    correcciones = [c.model_copy(update={"valor_anterior": mascara(c.valor_anterior),
                                         "valor_nuevo": mascara(c.valor_nuevo)}) if c.campo in sensibles
                    else c.model_copy() for c in resultado.correcciones]
    return resultado.model_copy(deep=True, update={"datos_extraidos": datos, "evidencia_por_campo": evidencias,
                                                   "correcciones": correcciones})


def enmascarar_expediente(expediente: ResultadoExpediente,
                          sensibles_por_documento: dict[str, set[str]]) -> ResultadoExpediente:
    """Copia del expediente con cada documento enmascarado (sensibles de su ficha, por
    `identificador_unico_documento`) y los valores de las comparaciones de un campo que es sensible en
    alguno de los documentos comparados (en todos sus valores: es el mismo dato)."""
    documentos = [enmascarar_resultado(d, sensibles_por_documento.get(d.identificador_unico_documento, set()))
                  for d in expediente.documentos]
    comparaciones = []
    for comparacion in expediente.comparaciones:
        sensible = any(comparacion.campo in sensibles_por_documento.get(documento_id, set())
                       for documento_id in comparacion.valores)
        valores = ({documento_id: mascara(v) for documento_id, v in comparacion.valores.items()} if sensible
                   else dict(comparacion.valores))
        comparaciones.append(comparacion.model_copy(update={"valores": valores}))
    return expediente.model_copy(deep=True, update={"documentos": documentos, "comparaciones": comparaciones})

