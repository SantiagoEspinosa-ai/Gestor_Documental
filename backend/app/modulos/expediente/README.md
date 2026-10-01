# expediente

Responsable: PERSONA_1. API publica: `servicio.py` (ADR-005). Los errores son `ErrorApi` de `core`.

## servicio.py
- `crear_folio(sesion, proceso, referencia_externa, usuario, ahora=None) -> Folio`
  Folio `{PREFIJO}-{AAAA}-{NNNNNN}`; el anio es el de `ZONA_HORARIA` (no UTC) y la secuencia se
  reinicia cada anio. Numeracion atomica con un solo `INSERT ... ON CONFLICT` en `secuencias_folio`.
  Crea una `EXP-001` por cada tipo de `tipos_requeridos` del proceso (bloqueante, alerta de expediente
  con `documento_id` NULL, `campo` = tipo, mensaje con el `nombre_visible` de la ficha). Todo en la
  misma transaccion; audita `folio_creado`. Errores: 404 `PROCESO_NO_ENCONTRADO`, 409 `SECUENCIA_AGOTADA`.
- `recalcular_exp001(sesion, folio)`: ajusta las EXP-001 a los documentos `completado` del folio. Tipo
  efectivo de cada documento: `tipo_documental_confirmado` > `tipo_documental_detectado` del resultado
  vigente > `tipo_declarado`. Tipo presente: borra sus EXP-001 sin revisar (`aplica` NULL) y conserva
  las revisadas. Tipo que falta: crea su EXP-001 si no hay ninguna. Sin commit (lo hace quien llama) e
  idempotente. La llama `ingesta` al procesar cada documento; en la E2.6 tambien confirmar clasificacion.
- `obtener_expediente(sesion, folio) -> ResultadoExpediente`
  Todos los documentos del folio (por `creado_en` e `id`), tengan resultado o no, armados con
  `ingesta.servicio.construir_resultado` (igual que `GET /documentos/{id}`). `alertas_expediente` =
  alertas del folio sin documento, con `id` y revision (`ingesta.servicio.alerta_desde_bd`).
  `comparaciones` = `comparaciones_actuales`, al vuelo. `recomendacion_global` = la de
  `recomendacion.py`, calculada al vuelo con esos mismos documentos y alertas (no se guarda).
  Traduce columnas de BD al Contrato 1: `referencia_externa` y `fecha_solicitud` (= `creado_en`,
  ADR-004); `decision_humana`, `comentario_decision`, `usuario_decision` y `fecha_decision`
  (= `decision*` del folio, ADR-006 G). Error: 404 `FOLIO_NO_ENCONTRADO`.
- `listar_folios(sesion, proceso=None, estado_general=None, pagina=1, tamano_pagina=20) -> (list[ResumenFolio], total)`
  Del mas reciente al mas antiguo (`creado_en`, `folio`). `referencia_externa` = la del folio
  (ADR-008). `n_bloqueantes_sin_resolver`: alertas bloqueantes VISIBLES (las de documento como
  `construir_resultado`, sin las del motor de versiones anteriores, y las de expediente) con `aplica`
  distinto de false (ADR-006 2.2); la misma regla que bloquea `aprobar`. `recomendacion_global` como en el expediente;
  arma el expediente de cada folio de la pagina aparte (N+1 consultas, aceptable en el MVP).
- `comparaciones_actuales(sesion, folio) -> list[ComparacionCampo]`: compara (via
  `validacion.servicio.comparar`) los documentos `completado` del folio, con su tipo efectivo y los
  `datos_extraidos` de su resultado vigente, segun las `comparaciones` de las fichas. No se guarda.
- `recalcular_cmp001(sesion, folio)`: una `CMP-001` critica de expediente por campo que no coincide,
  con un mensaje que solo nombra el campo (nunca los valores). Borra las sin revisar de campos que ya
  coinciden; conserva las revisadas. Sin commit e idempotente; la llama `ingesta` al procesar.

## recomendacion.py
`calcular_recomendacion_global(documentos, alertas, fichas) -> Recomendacion`, logica pura. La
recomendacion POR DOCUMENTO es del motor de PERSONA_2 (`ResultadoDocumento.recomendacion`) y la
plataforma no la toca; la GLOBAL es de la plataforma. Reglas, en orden (la primera pide
`revision_manual`):
1. Sin documentos, o alguno `pendiente`, `procesando` o `error`.
2. Alguna alerta critica o bloqueante (de documento o de expediente) con `aplica` distinto de false.
   Decision del usuario: una critica o bloqueante marcada `aplica=false` (falso positivo) no cuenta.
   Las preventivas e informativas no cuentan nunca.
3. Algun documento sin ficha para su tipo efectivo, sin `confianza_clasificacion`, o con ella o con
   algun campo por debajo de los minimos de su ficha (un campo corregido vale 1.0, ADR-006 2.4).
4. Si no, `aprobar`. Nunca `rechazar`: la decision final es humana (regla 9 de CLAUDE.md).

## Revision (E2.6)
- `resolver_alerta_documento(sesion, documento_id, alerta_id, aplica, comentario, usuario) -> ResultadoDocumento`
  y `resolver_alerta_expediente(sesion, folio, alerta_id, aplica, comentario, usuario) -> ResultadoExpediente`.
  La alerta tiene que ser visible en ese recurso: de documento, de plataforma o del motor de la version
  vigente; de expediente, del folio y sin documento. Folio cerrado -> 409 `FOLIO_CERRADO`; documento
  `pendiente` o `procesando` -> 409 `DOCUMENTO_EN_PROCESO` (en `error` si se puede, decision del
  usuario). Sobrescribe la resolucion, audita `alerta_resuelta` (sin el comentario) y hace commit.
  Las resueltas se conservan en `recalcular_exp001` y `recalcular_cmp001`.
- `corregir_datos(sesion, documento_id, cambios, usuario) -> ResultadoDocumento`: valida contra la
  ficha del tipo de EXTRACCION (confirmado > declarado > detectado, no el efectivo) y guarda una `Correccion` por campo sobre la version vigente del resultado
  (sin version nueva); recalcula `CMP-001`. Orden comun de las acciones sobre un documento: 404 ->
  `FOLIO_CERRADO` -> `DOCUMENTO_EN_PROCESO` / `DOCUMENTO_CON_ERROR`. Las comparaciones usan los datos
  ya corregidos.
- `confirmar_clasificacion(sesion, documento_id, tipo, usuario) -> (ResultadoDocumento, reprocesar)`:
  tipo usado para extraer = confirmado previo > declarado > detectado. Si coincide, resuelve las
  `CLS-001` sin revisar; si no, el documento vuelve a `pendiente` y quien llama (el router) lanza
  `ingesta.procesar_documento(..., tipo_confirmado=tipo)`. En los dos casos recalcula `EXP-001` y
  `CMP-001` y audita `clasificacion_confirmada`.
- `decidir_folio(sesion, folio, decision, comentario, usuario) -> ResultadoExpediente`: 404 ->
  `FOLIO_CERRADO` -> `DOCUMENTO_EN_PROCESO` -> (solo al aprobar) `DECISION_BLOQUEADA`. Guarda con un
  UPDATE condicional (`estado_general = 'en_revision'`): si otro revisor decidio entre medias, afecta a
  0 filas y da `FOLIO_CERRADO`. Audita `decision_tomada` sin el comentario. Pendiente (etapa 3): webhook
  `folio.estado_cambiado`.
