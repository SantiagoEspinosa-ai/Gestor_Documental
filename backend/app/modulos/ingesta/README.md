# ingesta

Responsable: PERSONA_1. API publica: `servicio.py` (ADR-005). El router es `api/documentos.py` (tarea 10).

## servicio.py
`ingestar(sesion, almacenamiento, folio, nombre_archivo, datos, tipo_contenido, tipo_declarado, usuario) -> Documento`

- Entrada: bytes del archivo, su nombre y tipo MIME, `tipo_declarado` opcional y el usuario.
- Salida: el `Documento` creado en estado `pendiente`, con su original en S3 en
  `{proceso}/{anio}/{secuencia:06d}/{uuid}.{ext}` (nunca se sobrescribe; ver `core/almacenamiento.py`).
- Pasos: folio abierto -> tamano -> tipo y formato -> SHA-256 -> fila en BD -> subida a S3 ->
  alerta `DUP-001` si hay duplicado -> auditoria `documento_subido` -> commit.
- Duplicado (mismo hash en el mismo folio): no bloquea. Se sube con su propio UUID y lleva una
  alerta `DUP-001` critica que cita el documento anterior.
- La auditoria guarda hash, tamano y si es duplicado, nunca el nombre del archivo (suele llevar el
  nombre de la persona). El nombre si se guarda en `documentos`.
- Errores (`ErrorApi`): 404 `FOLIO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO`; 413 `ARCHIVO_DEMASIADO_GRANDE`
  (`TAMANO_MAXIMO_ARCHIVO_MB`); 415 `FORMATO_NO_PERMITIDO` (extension fuera de `formatos_permitidos`
  del tipo, o de todos los tipos si no se declara); 422 `PETICION_INVALIDA` (archivo vacio o
  `tipo_declarado` inexistente); 500 `ERROR_INTERNO` si falla S3 (sin fila en BD).
- Si el commit falla despues de subir, el objeto queda huerfano en S3 (el IAM no puede borrar): se
  registra con `log.error` y la clave para revisarlo a mano.

## tipos.py
Lee `formatos_permitidos` de `config/tipos/*.yaml`. Provisional hasta que `configuracion` de
PERSONA_2 este en main.

## procesamiento_stub.py
`procesar_documento(documento_id)`: se lanza como BackgroundTask y abre su propia sesion.
`pendiente -> procesando -> completado` con un `ResultadoDocumento` ficticio valido (proveedor y
modelo `stub`, prompt `stub@v0`, alertas del documento con su `id`), guardado como nueva version en
`resultados`, y auditoria `documento_procesado`. Si falla: estado `error`, sin relanzar.
PERSONA_2 lo sustituye en la etapa 2 por el procesamiento real.
