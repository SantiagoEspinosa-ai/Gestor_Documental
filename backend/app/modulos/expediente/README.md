# expediente  (responsable: PERSONA_1)

Entrada: un folio con sus `ResultadoDocumento`.
Salida: `ResultadoExpediente` (comparaciones, `alertas_expediente`, `recomendacion_global`) y el
resumen `resumen.md` (plantilla Jinja `plantillas/resumen.md.j2`) guardado en S3.
Regla 9: la decision la toma el revisor; este modulo solo recomienda y bloquea `aprobar` si hay
una bloqueante sin resolver.
