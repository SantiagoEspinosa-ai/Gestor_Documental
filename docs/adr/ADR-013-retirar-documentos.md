# ADR-013: Retirar un documento del folio en lugar de borrarlo

Fecha: 2026-10-07. Estado: ACEPTADO (2026-10-07, PERSONA_1 y PERSONA_2, PR #59).
Propone: PERSONA_2 (la idea) y PERSONA_1 (el diseno y la implementacion). Afecta al Contrato 1
(`backend/app/schemas/resultado.py`: campo opcional `retirado` en `ResultadoDocumento`), al Contrato 2
(`docs/contratos/endpoints.md`: dos rutas nuevas y la nota en "Reglas"), al catalogo de errores (dos codigos
nuevos) y a la BD (migracion 0008: tres columnas en `documentos`).

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| 1 | `POST /documentos/{id}/retirar {motivo}` y `POST /documentos/{id}/restaurar`, solo para el revisor | PERSONA_1 | Aceptada |
| 2 | Un retirado sigue en el folio pero no cuenta: EXP-001, EXP-002, comparaciones y CMP-001, recomendacion global, bloqueantes y duplicados | PERSONA_1 (expediente e ingesta) | Aceptada |
| 3 | Nada se borra (BD ni S3); el motivo se guarda tapado; auditoria `documento_retirado` y `documento_restaurado` | PERSONA_1 | Aceptada |
| 4 | `ResultadoDocumento.retirado: {en, por, motivo} \| null`, opcional y `None` por defecto: el motor no cambia | PERSONA_1 (lo rellena la plataforma) | Aceptada |

## Contexto
- PERSONA_2 propuso poder quitar un documento subido por error (otro fichero, duplicado, de otra persona). Hoy
  no hay forma: el documento cuenta para siempre en el folio (cobertura, comparaciones, recomendacion).
- Borrarlo romperia la trazabilidad (auditoria, resumen, memoria de folios) y los originales en S3 son
  inmutables: el usuario IAM no tiene `s3:DeleteObject`.

## Decision
1. Retirar en lugar de borrar: el documento queda marcado (`retirado_en`, `retirado_por` y `motivo_retirada`
   en `documentos`; retirado = `retirado_en` no nulo), es reversible (`restaurar`) y nada se borra.
2. Condiciones: folio `en_revision` (`409 FOLIO_CERRADO`); retirar exige un documento que no este `pendiente`
   ni `procesando` (`409 DOCUMENTO_EN_PROCESO`; en `error` si se puede, es el caso tipico) y no retirado ya
   (`409 DOCUMENTO_RETIRADO`); restaurar exige que este retirado (`409 DOCUMENTO_NO_RETIRADO`). Solo revisor,
   como las demas operaciones de revision; el admin consulta. Admin e integrador, `403 SIN_PERMISO`.
3. `motivo` obligatorio al retirar (3 a 200 caracteres). Es texto libre: se guarda tapado con la misma barrera
   que el motivo de "mostrar" (ADR-010 A4c, `enmascaramiento.enmascarar_texto`). Restaurar no lleva motivo.
4. Un retirado no cuenta para EXP-001 ni EXP-002, las comparaciones ni CMP-001, la recomendacion global, las
   bloqueantes (se puede aprobar aunque un retirado tenga una) ni los duplicados (`DUP-001` se recalcula: un
   retirado no hace duplicado a otro). `ResumenFolio.n_documentos` si los cuenta: siguen en el folio.
5. Sobre un retirado no se revisa (corregir, confirmar la clasificacion, resolver sus alertas: `409
   DOCUMENTO_RETIRADO`); si se consulta (GET, original, "mostrar").
6. `resumen.md` lo lista al final, en "Documentos retirados" (tipo, fecha, quien y motivo tapado), fuera de
   "Documentos": queda constancia en el registro del expediente y el fragmento de la memoria de folios no lo
   recoge (no es una seccion que lea `rag.extraer_fragmento`).
7. Auditoria: `documento_retirado` con `{motivo}` tapado y `documento_restaurado` sin detalle.
8. Sin webhook: retirar no cambia `estado_general` y no se crean eventos nuevos.
9. Contrato 1: `retirado` es opcional con `None` por defecto; lo rellena `ingesta.construir_resultado` desde la
   BD. El motor (PERSONA_2) no cambia.

## Evolucion
- Borrado real por politica de retencion (BD y S3, con un permiso de borrado aparte), cuando se defina.

## Consecuencias
- Un error de subida se corrige sin perder trazabilidad y se puede deshacer.
- Migracion 0008 (tres columnas nulas, sin datos que migrar), detras de la 0006 y la 0007.
- Si se rechaza: un documento subido por error sigue contando y solo queda rechazar el folio.
