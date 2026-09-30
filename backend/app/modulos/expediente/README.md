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
  `ingesta.servicio.construir_resultado` (igual que `GET /documentos/{id}`). `alertas_expediente` = alertas del folio sin documento, con `id` y revision (convertidas
  con `ingesta.servicio.alerta_desde_bd`). `comparaciones` vacias y `recomendacion_global` nula por ahora.
  Traduce columnas de BD al Contrato 1: `referencia_externa` y `fecha_solicitud` (= `creado_en`,
  ADR-004); `decision_humana`, `comentario_decision`, `usuario_decision` y `fecha_decision`
  (= `decision*` del folio, ADR-006 G). Error: 404 `FOLIO_NO_ENCONTRADO`.
- `listar_folios(sesion, proceso=None, estado_general=None, pagina=1, tamano_pagina=20) -> (list[ResumenFolio], total)`
  Del mas reciente al mas antiguo (`creado_en`, `folio`). `n_bloqueantes_sin_resolver`: alertas
  bloqueantes del folio, de documento o de expediente, con `aplica` NULL o true (ADR-006 2.2).
