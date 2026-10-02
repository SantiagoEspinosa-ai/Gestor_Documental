"""Stub del motor de PERSONA_2 con la interfaz acordada; lo sustituye
`app.modulos.orquestador.servicio.procesar_documento` cuando llegue a main.

Acuerdo con PERSONA_2: el motor no toca la BD ni S3 (recibe los bytes). Proveedor caido -> resultado
en `error` con SYS-001; JSON invalido tras reintentar -> `error` con SYS-002; cualquier otra cosa lanza.
"""
from datetime import datetime, timezone

from app.schemas.resultado import (EstadoAnalisis, FechaYModelo, Recomendacion, ReferenciaArchivoOriginal,
                                   ResultadoDocumento)


def procesar_documento(contenido: bytes, *, identificador: str, nombre_archivo: str,
                       tipo_declarado: str | None, folio: str, referencia: ReferenciaArchivoOriginal,
                       tipo_confirmado: str | None = None) -> tuple[ResultadoDocumento, dict]:
    """Resultado ficticio pero valido, sin alertas, y los datos de auditoria del stub.

    Con `tipo_confirmado` no se clasifica (ADR-009): detectado y confianza de clasificacion a null, como
    el motor real. El confirmado manda en el tipo efectivo y vale 1.0 en la recomendacion (D2).
    """
    resultado = ResultadoDocumento(
        folio_solicitud=folio,
        identificador_unico_documento=identificador,
        tipo_documental_declarado=tipo_declarado,
        tipo_documental_detectado=None if tipo_confirmado else tipo_declarado,
        confianza_clasificacion=None if tipo_confirmado else 1.0,
        datos_extraidos={},
        alertas_encontradas=[],
        recomendacion=Recomendacion.revision_manual,
        estado_analisis=EstadoAnalisis.completado,
        fecha_y_modelo_utilizado=FechaYModelo(fecha_analisis=datetime.now(timezone.utc), proveedor="stub",
                                              modelo="stub", version_prompt="stub@v0"),
        referencia_archivo_original=referencia,
    )
    return resultado, {"proveedor": "stub", "modelo": "stub", "version_prompt": "stub@v0",
                       "respaldo_usado": False}
