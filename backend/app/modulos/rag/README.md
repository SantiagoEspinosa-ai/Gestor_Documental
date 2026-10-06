# rag (responsable: PERSONA_2)

Los demas modulos solo importan `servicio.py` (ADR-005).

## Memoria de folios (H14, ADR-010 C4)
- `indexar_resumen(folio, resumen_md, *, sesion=None)`: guarda el `resumen.md` del folio (ya enmascarado por la
  plataforma) y un fragmento. Nunca lanza. Con `sesion`, hace commit sobre ella (rollback si falla): llamarla
  despues del commit del llamador. La llama `expediente.servicio.avisar_reindexar` al regenerar el resumen (#39).
- `fragmento_resumen(folio) -> str | None`: el fragmento para `GET /folios/{folio}/antecedentes`; `None` si no esta
  indexado.
- Tabla `memoria_folios` (modelo en `modelos.py`; migracion `0005` de la plataforma, #39). Folios anteriores:
  `scripts/reindexar_resumenes.py`.
- Sin embeddings: el fragmento se extrae del Markdown sin modelo y nunca copia valores de los datos.

Detalle y motivo de las decisiones: `docs/motor_ia/SPEC_CONFIGURACION.md`, seccion 16.
