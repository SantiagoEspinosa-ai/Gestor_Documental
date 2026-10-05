# validacion

Responsable: ver CLAUDE.md. Entrada / salida: (completar al implementar).

## comparar (PERSONA_1)
`servicio.comparar(documentos, fichas) -> list[ComparacionCampo]` (logica en `comparaciones.py`).
- Entrada: los documentos `completado` del folio como `DocumentoComparable(id, tipo, datos)` (tipo
  efectivo y `datos_extraidos` ya corregidos) y las fichas (lista con `nombre` o dict por nombre).
- Que se compara: los campos de `comparaciones` de las fichas, uniendo los dos sentidos (A-B = B-A).
  Participan los documentos con valor en tipos de un par cuyos dos lados tienen valor; con menos de 2
  valores no hay comparacion. `None` y `""` no participan.
- Normalizacion: mayusculas, sin acentos (NFKD), espacios colapsados y sin espacios en los extremos.
  Los campos de tipo `fecha` se comparan como fecha (varios formatos); si no se leen, como texto.
- Salida: un `ComparacionCampo(campo, coincide, valores={id_documento: valor original})` por campo,
  ordenado por campo. La `CMP-001` la crea `expediente.recalcular_cmp001` con esta salida.

## evaluar_reglas (PERSONA_2)
`servicio.evaluar_reglas(datos_extraidos, confianzas, ficha, *, hoy) -> (list[Alerta], Reglas)` (logica en
`reglas.py`). Pura: sin BD, S3 ni modelo.
- Entrada: `datos_extraidos` con las correcciones aplicadas (fechas `AAAA-MM-DD`, anio entero), las confianzas
  (1,0 en los campos corregidos), la ficha del tipo de extraccion (`TipoDocumental` o dict) y `hoy` (zona horaria
  del negocio).
- Salida: alertas `VAL-001`, `VAL-002`, `VAL-004` y `REG-{id}` (nunca `VAL-003`, `CLS`, `SYS`, `DUP`, `EXP` ni `CMP`)
  y `Reglas(cumplidas, incumplidas)`. Una regla sobre un campo vacio no se evalua ni se lista.
- Detalle de cada tipo de regla: `docs/motor_ia/SPEC_CONFIGURACION.md`, seccion 15.

## recomendar_documento (PERSONA_2)
`servicio.recomendar_documento(resultado, ficha) -> Recomendacion` (logica en `recomendacion.py`). Pura.
- `aprobar` si el analisis esta `completado`, sin alertas criticas ni bloqueantes (salvo falsos positivos,
  `aplica=False`) y con las confianzas sobre el minimo (clasificacion y campos con valor); si no, `revision_manual`.
- Nunca `rechazar` (D1). Mismas reglas que la recomendacion global (`expediente/recomendacion.py`).
