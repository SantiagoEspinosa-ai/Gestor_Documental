# validacion  (responsables: PERSONA_2 reglas, PERSONA_1 comparaciones)

`reglas.py`: entrada `ResultadoExtraccion` + ficha + fecha de hoy; salida
`reglas_cumplidas_e_incumplidas` y alertas `REG-{id}`, `VAL-001`, `VAL-002`. Determinista.
`comparaciones.py`: entrada los `ResultadoDocumento` del folio; salida `list[ComparacionCampo]`
y alertas `CMP-001`, normalizando mayusculas, acentos y espacios.
Codigos: `docs/contratos/codigos_alertas.md`. Todo con test en `backend/tests/`.
