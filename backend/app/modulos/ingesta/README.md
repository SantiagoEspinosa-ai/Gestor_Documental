# ingesta  (responsable: PERSONA_1)

Entrada: `ingestar(folio, archivo, tipo_declarado, usuario)` desde `POST /folios/{folio}/documentos`.
Salida: `202 {identificador_unico_documento, estado_analisis: "pendiente"}` y una BackgroundTask
`procesar_documento(documento_id)`.

Hace: valida la extension contra `formatos_permitidos` de la ficha, calcula SHA-256, detecta
duplicado en el folio (`DUP-001`, no bloquea), sube el original a S3 (nunca se sobrescribe),
inserta el documento en `pendiente` y registra auditoria.
Especificacion: `docs/equipo/PERSONA_1_plataforma.md`, tareas 8-10.
