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
