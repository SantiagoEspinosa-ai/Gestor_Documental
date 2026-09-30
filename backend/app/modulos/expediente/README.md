# expediente

Responsable: PERSONA_1. API publica: `servicio.py` (ADR-005). Los errores son `ErrorApi` de `core`.

## servicio.py
- `crear_folio(sesion, proceso, referencia_externa, usuario, ahora=None) -> Folio`
  Folio `{PREFIJO}-{AAAA}-{NNNNNN}`; el anio es el de `ZONA_HORARIA` (no UTC) y la secuencia se
  reinicia cada anio. Numeracion atomica con un solo `INSERT ... ON CONFLICT` en `secuencias_folio`.
  Audita `folio_creado` y hace commit. Errores: 404 `PROCESO_NO_ENCONTRADO`, 409 `SECUENCIA_AGOTADA`.
- `obtener_expediente(sesion, folio) -> ResultadoExpediente`
  Un `ResultadoDocumento` por documento: el de version mayor; los documentos sin resultado no
  aparecen. `comparaciones` y `alertas_expediente` vacias y `recomendacion_global` nula por ahora;
  `decision_humana` = decision del folio. Error: 404 `FOLIO_NO_ENCONTRADO`.
  Pendiente: `referencia_externa` y `fecha_solicitud` (ADR-004) cuando el PR de contratos las anada.
- `listar_folios(sesion, proceso=None, estado_general=None, pagina=1, tamano_pagina=20) -> (elementos, total)`
  Del mas reciente al mas antiguo (`creado_en`, `folio`). Cada elemento tiene la forma de
  `ResumenFolio` (ADR-006 1.1). `n_bloqueantes_sin_resolver`: alertas bloqueantes del folio, de
  documento o de expediente, con `aplica` NULL o true (ADR-006 2.2).
