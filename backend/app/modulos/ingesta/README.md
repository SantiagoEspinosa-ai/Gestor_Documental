# ingesta

Responsable: PERSONA_1. API publica: `servicio.py` (ADR-005). El router es `api/documentos.py` (tarea 10).

## servicio.py
`ingestar(sesion, almacenamiento, folio, nombre_archivo, datos, tipo_declarado, usuario) -> Documento`

- Entrada: bytes del archivo, su nombre, `tipo_declarado` opcional y el usuario. El tipo MIME no se
  recibe: sale de la extension (pdf, jpg/jpeg, png; el resto `application/octet-stream`).
- Salida: el `Documento` creado en estado `pendiente`, con su original en S3 en
  `{proceso}/{anio}/{secuencia:06d}/{uuid}.{ext}` (nunca se sobrescribe; ver `core/almacenamiento.py`).
- Pasos: folio abierto -> tamano -> nombre (sin ruta, recortado a 255 conservando la extension) ->
  tipo, extension y firma magica del contenido (`%PDF-`, JPEG, PNG) -> SHA-256 -> fila en BD ->
  subida a S3 -> alerta `DUP-001` si hay duplicado -> auditoria `documento_subido` -> commit.
- Duplicado (mismo hash en el mismo folio): no bloquea. Se sube con su propio UUID y lleva una
  alerta `DUP-001` critica que cita el documento anterior.
- La auditoria guarda hash, tamano y si es duplicado, nunca el nombre del archivo (suele llevar el
  nombre de la persona). El nombre si se guarda en `documentos`.
- Errores (`ErrorApi`): 404 `FOLIO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO`; 413 `ARCHIVO_DEMASIADO_GRANDE`
  (`TAMANO_MAXIMO_ARCHIVO_MB`); 415 `FORMATO_NO_PERMITIDO` (extension fuera de `formatos_permitidos`
  del tipo, o de todos los tipos si no se declara, o contenido que no corresponde a la extension);
  422 `PETICION_INVALIDA` (archivo vacio, sin nombre o `tipo_declarado` inexistente);
  500 `ERROR_INTERNO` si falla S3 (sin fila en BD).
- Si el commit falla despues de subir, el objeto queda huerfano en S3 (el IAM no puede borrar): se
  registra con `log.error` y la clave para revisarlo a mano.

`construir_resultado(sesion, documento) -> ResultadoDocumento`: el unico armado del resultado, que
usan `GET /documentos/{id}` y el expediente. Con resultado: la version mayor, con `estado_analisis`,
`tipo_documental_confirmado` y `alertas_encontradas` sobrescritos desde la BD. Sin resultado: uno
minimo con el estado de la fila y sus alertas (con `id`). La tabla `alertas` es la fuente de verdad
de las alertas; en la etapa 2 las alertas del motor se guardan en ella al guardar el resultado.

`obtener_resultado(sesion, documento_id) -> ResultadoDocumento`: `construir_resultado` del documento;
404 `DOCUMENTO_NO_ENCONTRADO` si no existe o el id no es un UUID.

`url_original(sesion, almacenamiento, documento_id) -> str`: URL prefirmada del original.

`procesar_documento(documento_id, tipo_confirmado=None)`: lo que lanza la API como BackgroundTask;
delega en `procesamiento.procesar` (la API solo importa `servicio.py`, ADR-005).

## tipos.py
Lee `formatos_permitidos` de `config/tipos/*.yaml`. Provisional hasta que `configuracion` de
PERSONA_2 este en main.

## procesamiento.py
`procesar(documento_id, tipo_confirmado=None)`: se lanza como BackgroundTask y abre su propia sesion.
`pendiente -> procesando`, descarga el original de S3, llama al motor y guarda:
- un `Resultado` nuevo (version = mayor + 1), sin sobrescribir los anteriores;
- cada alerta del motor en la tabla `alertas` con `version_resultado` = esa version (asi tiene `id`);
- `estado_analisis` = el que devuelva el motor (`completado` o `error`);
- auditoria `documento_procesado` con `modelo` y `version_prompt` en sus columnas y el resto de
  `datos_auditoria` (proveedor, respaldo_usado, confianzas_modelo, tiempos, tokens) en `detalle`.
Si falla la descarga, el motor lanza o el resultado es de otro documento/folio: estado `error`, sin
`Resultado` y sin relanzar. Al reprocesar solo se muestran las alertas del motor de la version nueva;
las de plataforma (`DUP-001`, `EXP-001`, `CMP-001`, con `version_resultado` NULL) se conservan.
Antes del commit llama a `expediente.servicio.recalcular_exp001` (en la misma transaccion). El import
es diferido (`_expediente_servicio()`) para romper el ciclo expediente -> ingesta.servicio ->
procesamiento -> expediente.

## Interfaz acordada con el motor (PERSONA_2)
`app.modulos.orquestador.servicio.procesar_documento(contenido: bytes, *, identificador: str,
nombre_archivo: str, tipo_declarado: str | None, folio: str, referencia: ReferenciaArchivoOriginal,
tipo_confirmado: str | None = None) -> tuple[ResultadoDocumento, dict]`
- No toca la BD ni S3: la plataforma le pasa los bytes.
- `datos_auditoria`: modelo, version_prompt, proveedor, respaldo_usado, confianzas_modelo (ADR-007),
  tiempos y tokens.
- Errores: proveedor caido o sin respaldo -> resultado en `error` con `SYS-001`; JSON invalido tras el
  reintento -> `error` con `SYS-002`; cualquier otra cosa -> excepcion.
- Reparto: el motor hace las reglas del documento (VAL, REG, CLS) y su recomendacion; la plataforma,
  `CMP-001`, el recalculo de `EXP-001` y la recomendacion global.

Mientras ese modulo no este en `main`, `procesamiento.py` importa `motor_stub.procesar_documento`,
con la misma firma: devuelve un `ResultadoDocumento` ficticio valido, sin alertas, y
`{"proveedor": "stub", "modelo": "stub", "version_prompt": "stub@v0", "respaldo_usado": False}`.
