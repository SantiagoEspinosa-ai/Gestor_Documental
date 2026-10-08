"""
`procesar_documento`: lo que conecta la plataforma (spec, seccion 11). Prepara el archivo, lo analiza con
motor_ia, completa la MRZ, evalua las reglas del documento y da la recomendacion por documento. No toca la BD
ni S3: recibe los bytes y devuelve (ResultadoDocumento, datos_auditoria).
Dependencias en un solo sentido: orquestador -> motor_ia, validacion, configuracion.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia import servicio as motor_ia
from app.modulos.motor_ia.interfaces import Enrutador
from app.modulos.motor_ia.servicio import AlAvanzar, avisar_fase
from app.modulos.orquestador import reloj
from app.modulos.orquestador.completar_mrz import completar_sexo, verificacion_mrz
from app.modulos.orquestador.preparador import preparar
from app.modulos.validacion import servicio as validacion
from app.schemas.resultado import EstadoAnalisis, FaseAnalisis, Recomendacion, ReferenciaArchivoOriginal, ResultadoDocumento

DESCONOCIDO = configuracion.NOMBRE_RESERVADO


def procesar_documento(contenido: bytes, *, identificador: str, nombre_archivo: str, tipo_declarado: str | None,
                       folio: str, referencia: ReferenciaArchivoOriginal, tipo_confirmado: str | None = None,
                       al_avanzar: AlAvanzar | None = None, enrutador: Enrutador | None = None,
                       ahora: datetime | None = None) -> tuple[ResultadoDocumento, dict[str, Any]]:
    """Analisis completo de un documento. Errores (acordados con PERSONA_1): proveedor caido o sin respaldo ->
    `estado_analisis=error` + SYS-001; JSON invalido -> `error` + SYS-002; cualquier otra cosa lanza (formato no
    soportado, tipo inexistente, configuracion invalida). `enrutador` y `ahora` son para los tests y el CLI.
    `al_avanzar` recibe la fase del analisis (ADR-014): preparando, ocr, clasificando, vision y extrayendo. Es
    solo informativo: si lanza, se ignora y el resultado no cambia."""
    avisar_fase(al_avanzar, FaseAnalisis.preparando)
    doc = preparar(contenido, nombre_archivo, tipo_declarado, identificador=identificador, al_avanzar=al_avanzar)
    mrz = verificacion_mrz(doc)
    analisis = motor_ia.analizar(doc, folio=folio, referencia=referencia, tipo_confirmado=tipo_confirmado,
                                 enrutador=enrutador, ahora=ahora, mrz=mrz, al_avanzar=al_avanzar)
    resultado = analisis.resultado
    ficha = _ficha_de_extraccion(resultado)

    if resultado.estado_analisis is EstadoAnalisis.completado and ficha is not None:
        resultado = completar_sexo(resultado, doc, ficha, mrz)
        hoy = reloj.hoy(ahora) if ahora is not None and ahora.tzinfo is not None else reloj.hoy()
        alertas, reglas = validacion.evaluar_reglas(resultado.datos_extraidos, resultado.nivel_confianza_por_campo,
                                                    ficha, hoy=hoy)
        existentes = {(a.codigo, a.campo) for a in resultado.alertas_encontradas}
        nuevas = [a for a in alertas if (a.codigo, a.campo) not in existentes]  # ADR-006, 1.3
        resultado = resultado.model_copy(update={"alertas_encontradas": [*resultado.alertas_encontradas, *nuevas],
                                                 "reglas_cumplidas_e_incumplidas": reglas})
    recomendacion = (validacion.recomendar_documento(resultado, ficha)
                     if resultado.estado_analisis is EstadoAnalisis.completado else Recomendacion.revision_manual)
    resultado = ResultadoDocumento.model_validate(resultado.model_copy(update={"recomendacion": recomendacion}).model_dump())
    return resultado, datos_auditoria(resultado, analisis, doc)


def _ficha_de_extraccion(resultado: ResultadoDocumento):
    """Ficha con la que se extrajo (ADR-006, 2.5): confirmado > declarado > detectado (si no es desconocido)."""
    tipo = (resultado.tipo_documental_confirmado or resultado.tipo_documental_declarado
            or (resultado.tipo_documental_detectado if resultado.tipo_documental_detectado != DESCONOCIDO else None))
    return configuracion.obtener(tipo) if tipo else None


def datos_auditoria(resultado: ResultadoDocumento, analisis, doc) -> dict[str, Any]:
    """Para `documento_procesado` (ADR-006 1.5 y ADR-007): solo valores serializables a JSON y sin datos del
    documento. `modelo` y `version_prompt` van a sus columnas; el resto, a `detalle`."""
    fecha = resultado.fecha_y_modelo_utilizado
    llamadas = [{"proveedor": i.proveedor, "modelo": i.modelo, "entrada": i.entrada or None, "motivo": i.motivo,
                 "segundos": i.segundos, "tokens_entrada": i.tokens_entrada, "tokens_salida": i.tokens_salida,
                 "peticiones": i.peticiones, "reintentos": i.reintentos, "lotes": i.lotes}
                for i in analisis.llamadas]
    return {
        "modelo": fecha.modelo if fecha else None,
        "proveedor": fecha.proveedor if fecha else None,
        "version_prompt": fecha.version_prompt if fecha else None,
        "version_prompt_clasificacion": analisis.version_prompt_clasificacion,
        "respaldo_usado": any(a.codigo == "SYS-005" for a in resultado.alertas_encontradas),
        "confianzas_modelo": {k: float(v) for k, v in analisis.confianzas_modelo.items()},
        "tiempos": {"segundos_modelo": round(sum(i.segundos for i in analisis.llamadas), 2)},
        "tokens": {"entrada": sum(i.tokens_entrada for i in analisis.llamadas),
                   "salida": sum(i.tokens_salida for i in analisis.llamadas)},
        "llamadas": llamadas,
        "modalidad": doc.modalidad.value,
        "paginas": len(doc.paginas),
    }
