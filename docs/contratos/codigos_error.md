# Catalogo de codigos de error de la API

Referencia comun para el campo `codigo` de los errores del Contrato 2 (ADR-006, 1.4). No es un
contrato congelado: anadir un codigo nuevo es libre (se anade aqui en el mismo commit); cambiar el
significado de uno existente requiere ADR.

Formato: todo error de la API usa `{"codigo": "...", "mensaje": "..."}`, tambien los de validacion
de FastAPI y los de rutas o metodos inexistentes. Nunca el `{"detail": ...}` por defecto de FastAPI.
`mensaje` es un texto para personas y no incluye detalles internos ni datos personales.

| HTTP | codigo | Cuando |
|---|---|---|
| 401 | `CREDENCIALES_INVALIDAS` | Login con usuario o contrasena incorrectos |
| 401 | `NO_AUTENTICADO` | Falta la cabecera Authorization o el token es invalido |
| 401 | `TOKEN_CADUCADO` | JWT expirado (la UI vuelve al login) |
| 403 | `SIN_PERMISO` | Rol sin acceso al endpoint |
| 404 | `FOLIO_NO_ENCONTRADO` | El folio no existe |
| 404 | `DOCUMENTO_NO_ENCONTRADO` | El documento no existe |
| 404 | `ALERTA_NO_ENCONTRADA` | El `alerta_id` no existe en ese documento o folio |
| 404 | `PROCESO_NO_ENCONTRADO` | El proceso no existe |
| 404 | `RESUMEN_NO_DISPONIBLE` | `GET /folios/{folio}/resumen.md` antes de que exista el resumen (ADR-006, J) |
| 404 | `RUTA_NO_ENCONTRADA` | La ruta pedida no existe en la API |
| 405 | `METODO_NO_PERMITIDO` | La ruta existe pero no admite ese metodo HTTP |
| 409 | `DECISION_BLOQUEADA` | `aprobar` con una bloqueante que impide aprobar (ADR-006, 2.2) |
| 409 | `DOCUMENTO_EN_PROCESO` | Accion del revisor sobre un documento `pendiente` o `procesando` |
| 409 | `FOLIO_CERRADO` | Accion sobre un folio `aprobado` o `rechazado` (ADR-006, G) |
| 413 | `ARCHIVO_DEMASIADO_GRANDE` | El archivo supera 20 MB |
| 415 | `FORMATO_NO_PERMITIDO` | Extension fuera de `formatos_permitidos` del tipo |
| 422 | `PETICION_INVALIDA` | Cuerpo o parametros invalidos |
| 500 | `ERROR_INTERNO` | Error no controlado |

Un duplicado no es un error: la subida devuelve 202 y el documento lleva la alerta `DUP-001`
(ver `codigos_alertas.md`).
