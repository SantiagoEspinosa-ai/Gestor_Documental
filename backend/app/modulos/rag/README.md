# rag  (responsables: PERSONA_2 base de conocimiento, PERSONA_3 memoria de folios)

`conocimiento.py`: indexa `CONOCIMIENTO_DIR/*.md` en pgvector; `buscar(consulta, k) -> list[str]`
para `DocumentoPreparado.contexto_rag`.
`memoria.py`: indexa cada `resumen.md`; `buscar_antecedentes(referencia_persona, proceso)` solo si el
proceso tiene `permitir_antecedentes` y solo chunks no caducados (`caducidad_antecedentes_dias`).
