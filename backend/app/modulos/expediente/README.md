# expediente

Responsable: PERSONA_1. API publica: `servicio.py` (ADR-005). Los errores son `ErrorApi` de `core`.

## servicio.py
- `crear_folio(sesion, proceso, referencia_externa, usuario, ahora=None) -> Folio`
  Folio `{PREFIJO}-{AAAA}-{NNNNNN}`; el anio es el de `ZONA_HORARIA` (no UTC) y la secuencia se
  reinicia cada anio. Numeracion atomica con un solo `INSERT ... ON CONFLICT` en `secuencias_folio`.
  Audita `folio_creado` y hace commit. Errores: 404 `PROCESO_NO_ENCONTRADO`, 409 `SECUENCIA_AGOTADA`.
- `obtener_expediente(sesion, folio) -> ResultadoExpediente`
  Un `ResultadoDocumento` por documento: el de version mayor; los documentos sin resultado no
  aparecen. `comparaciones` y `alertas_expediente` vacias y `recomendacion_global` nula por ahora.
  Traduce columnas de BD al Contrato 1: `referencia_externa` y `fecha_solicitud` (= `creado_en`,
  ADR-004); `decision_humana`, `comentario_decision`, `usuario_decision` y `fecha_decision`
  (= `decision*` del folio, ADR-006 G). Error: 404 `FOLIO_NO_ENCONTRADO`.
- `listar_folios(sesion, proceso=None, estado_general=None, pagina=1, tamano_pagina=20) -> (list[ResumenFolio], total)`
  Del mas reciente al mas antiguo (`creado_en`, `folio`). `n_bloqueantes_sin_resolver`: alertas
  bloqueantes del folio, de documento o de expediente, con `aplica` NULL o true (ADR-006 2.2).
