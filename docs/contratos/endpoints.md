# CONTRATO 2 - Endpoints de la API

Base: `/api/v1`. Auth: `Authorization: Bearer <JWT>`. Roles: `admin`, `revisor`, `integrador`.
Errores: `{ "codigo": "...", "mensaje": "..." }`. Cambios solo mediante ADR.

| Metodo | Ruta | Rol | Descripcion | Respuesta |
|---|---|---|---|---|
| POST | /auth/login | - | `{usuario, contrasena}` | `{access_token, rol}` |
| GET | /procesos | admin, integrador | Procesos configurados (prefijo, webhook, modelos) | lista |
| POST | /folios | integrador, revisor | `{proceso, referencia_externa?}` | `{folio, estado_general}` |
| GET | /folios/{folio} | todos | Expediente consolidado | `ResultadoExpediente` |
| POST | /folios/{folio}/documentos | integrador, revisor | multipart: `archivo`, `tipo_declarado?` -> lanza BackgroundTask | `202 {identificador_unico_documento, estado_analisis: "pendiente"}` |
| GET | /documentos/{id} | todos | Resultado del documento | `ResultadoDocumento` |
| GET | /documentos/{id}/original | revisor, admin | URL prefirmada S3 (o stream) | `{url}` |
| PATCH | /documentos/{id}/datos | revisor | `{campo: valor}` corrige datos; se guarda en `correcciones` | `ResultadoDocumento` |
| POST | /documentos/{id}/confirmar-clasificacion | revisor | `{tipo_documental}` | `ResultadoDocumento` |
| POST | /documentos/{id}/alertas/{codigo}/resolver | revisor | `{aplica: bool, comentario?}` | `ResultadoDocumento` |
| POST | /folios/{folio}/decision | revisor | `{decision: aprobar\|rechazar, comentario?}` (bloqueante impide aprobar) | `ResultadoExpediente` |
| GET | /folios/{folio}/resumen.md | todos | Memoria sintetica en Markdown | text/markdown |
| GET | /folios/{folio}/antecedentes | revisor | Folios previos relacionados (RAG memoria), si `permitir_antecedentes` | lista |
| GET | /tipos-documentales | todos | Fichas cargadas desde config/tipos | lista |
| GET | /auditoria?folio= | admin | Registro de acciones | lista |

## Webhook (salida)
Configurable por proceso. `POST <url>` con cabecera `X-Firma: sha256=<HMAC(cuerpo, WEBHOOK_SECRET_HMAC)>`.
Eventos: `documento.completado`, `documento.error`, `folio.estado_cambiado`.
Cuerpo: `{evento, fecha, folio, identificador_unico_documento?, datos: ResultadoDocumento | ResultadoExpediente}`.

## Estados
Documento: `pendiente -> procesando -> completado | error`.
Expediente: `en_revision -> aprobado | rechazado`.
