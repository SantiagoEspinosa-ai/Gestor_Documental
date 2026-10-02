# CONTRATO 2 - Endpoints de la API

Base: `/api/v1`. Auth: `Authorization: Bearer <JWT>`. Roles: `admin`, `revisor`, `integrador`.
Errores: `{ "codigo": "...", "mensaje": "..." }`, catalogo en `docs/contratos/codigos_error.md`.
Cambios solo mediante ADR. Ampliado por ADR-004, ADR-006 y ADR-008 (2026-09-30).

| Metodo | Ruta | Rol | Descripcion | Respuesta |
|---|---|---|---|---|
| POST | /auth/login | - | JSON `{usuario, contrasena}` (no formulario OAuth2) | `{access_token, rol, expires_in}` (segundos) |
| GET | /auth/yo | todos | Recuperar la sesion al recargar | `{usuario, rol}` |
| GET | /procesos | admin, integrador, revisor | Procesos configurados | lista de `Proceso` (ver "Formas de respuesta") |
| POST | /folios | integrador, revisor | `{proceso, referencia_externa?}` | `{folio, estado_general}` |
| GET | /folios?proceso=&estado_general=&pagina=1&tamano_pagina=20 | revisor, admin | Lista de folios, del mas reciente al mas antiguo; cada elemento lleva `referencia_externa` (ADR-008) | `PaginaFolios` |
| GET | /folios/{folio} | todos | Expediente consolidado | `ResultadoExpediente` |
| POST | /folios/{folio}/documentos | integrador, revisor | multipart: `archivo` (max. 20 MB), `tipo_declarado?` -> lanza BackgroundTask | `202 {identificador_unico_documento, estado_analisis: "pendiente"}` |
| GET | /documentos/{id} | todos | Resultado del documento | `ResultadoDocumento` |
| GET | /documentos/{id}/original | revisor, admin | URL prefirmada S3 (o stream) | `{url}` |
| PATCH | /documentos/{id}/datos | revisor | `{campo: valor}` corrige datos; se guarda en `correcciones` (ver "Reglas") | `ResultadoDocumento` |
| POST | /documentos/{id}/confirmar-clasificacion | revisor | `{tipo_documental}` (ver "Reglas") | `ResultadoDocumento` |
| POST | /documentos/{id}/alertas/{alerta_id}/resolver | revisor | `{aplica: bool, comentario?}` | `ResultadoDocumento` |
| POST | /folios/{folio}/alertas/{alerta_id}/resolver | revisor | `{aplica: bool, comentario?}` sobre `alertas_expediente` | `ResultadoExpediente` |
| POST | /folios/{folio}/decision | revisor | `{decision: aprobar\|rechazar, comentario?}`; guarda comentario, usuario y fecha y cierra el folio (ver "Reglas") | `ResultadoExpediente` |
| GET | /folios/{folio}/resumen.md | todos | Memoria sintetica en Markdown; `404 RESUMEN_NO_DISPONIBLE` mientras no exista | text/markdown |
| GET | /folios/{folio}/antecedentes | revisor | Folios previos relacionados (RAG memoria), si `permitir_antecedentes` | lista (forma pendiente de ADR de etapa 3) |
| GET | /tipos-documentales | todos | Fichas cargadas desde config/tipos | lista de `TipoDocumental` |
| GET | /auditoria?folio=&pagina=1&tamano_pagina=50 | admin | Registro de acciones, del mas reciente al mas antiguo, paginado (ADR-008) | `PaginaAuditoria` |

`alerta_id` es `Alerta.id`, que asigna la plataforma al guardar la alerta. El `codigo` no identifica
una alerta: puede repetirse en un documento, una vez por campo (ADR-006, 1.3).

## Formas de respuesta (ADR-006 y ADR-008)
- `Proceso`: `{nombre, prefijo_folio, tipos_requeridos, tipos_opcionales, permitir_antecedentes,
  caducidad_antecedentes_dias, webhook_url, modelos}`. Para el rol revisor se omiten `webhook_url` y
  `modelos`.
- `PaginaFolios`: `{elementos: [ResumenFolio], total, pagina, tamano_pagina}` (`ResumenFolio` en el
  Contrato 1). `n_bloqueantes_sin_resolver` cuenta las bloqueantes que impiden aprobar (ver "Reglas").
  `referencia_externa` es la de `folios.referencia_externa` (identificador opaco del integrador, nunca
  el nombre de la persona; ADR-004) o `null` si el folio se creo sin ella (ADR-008, punto 2).
- `TipoDocumental`: la ficha YAML tal como la valida `configuracion`: `{nombre, nombre_visible,
  categoria, descripcion, formatos_permitidos, campos: {<campo>: {tipo, obligatorio, patron?}},
  confianza_minima_clasificacion, confianza_minima_campo, reglas, comparaciones}`. Cada regla:
  `{id, tipo, campo, campo_relacionado?, dias?, severidad, mensaje}`; `campo_relacionado` solo en las reglas de
  coherencia entre dos campos (`curp_coincide_con_fecha`, `fecha_anterior_a_campo`) y `dias` solo en las de plazo.
- `EntradaAuditoria`: `{id, usuario, accion, folio, documento_id, detalle, modelo, version_prompt,
  creado_en}`. `accion` es una lista cerrada: `login`, `folio_creado`, `documento_subido`,
  `documento_procesado`, `dato_corregido`, `clasificacion_confirmada`, `alerta_resuelta`,
  `decision_tomada` (y `dato_revelado` en la etapa 3). `detalle` nunca contiene valores sensibles sin
  enmascarar.
- `PaginaAuditoria` (ADR-008, punto 1): `{elementos: [EntradaAuditoria], total, pagina,
  tamano_pagina}`, la misma forma que `PaginaFolios`. `pagina` >= 1 (por defecto 1) y `tamano_pagina`
  de 1 a 100 (por defecto 50); fuera de rango, `422 PETICION_INVALIDA`. Orden: `creado_en` desc y, en
  empate, `id` desc. `folio` opcional filtra por folio y `total` cuenta las entradas que cumplen el
  filtro.

## Reglas (ADR-006)
- Bloqueo de la aprobacion (2.2): `aprobar` devuelve `409 DECISION_BLOQUEADA` mientras exista una
  alerta bloqueante, de documento o de expediente, con `aplica` distinto de `false`. Una bloqueante
  marcada `aplica=true` confirma el problema: el folio solo puede rechazarse.
- Folio cerrado (G): tras aprobar o rechazar, el folio queda cerrado y no se reabre. Cualquier accion
  posterior sobre el folio o sus documentos devuelve `409 FOLIO_CERRADO`.
- Documento en proceso: las acciones del revisor sobre un documento `pendiente` o `procesando`
  devuelven `409 DOCUMENTO_EN_PROCESO`.
- Alertas de comparacion (2.3): `CMP-001` va solo en `alertas_expediente`, una por campo comparado que
  no coincide y con `campo` relleno. Nunca se duplica en los documentos.
- Correcciones (2.4): `datos_extraidos` refleja el valor corregido; su confianza pasa a 1.0, su
  evidencia a `"correccion_revisor"`, y la correccion se anade a `ResultadoDocumento.correcciones`.
- Extraccion (2.5): se extrae con la ficha del tipo declarado; si no hay `tipo_declarado`, con la del
  detectado. Si el detectado difiere del declarado se emite `CLS-001` y decide el revisor.
- Confirmar clasificacion (2.5): se guarda en `tipo_documental_confirmado`.
  - Si es el tipo con el que se extrajo: `CLS-001` queda resuelta y no se reprocesa.
  - Si es distinto: el documento vuelve a `pendiente` y se relanza el procesamiento con
    `tipo_confirmado`, que manda sobre el declarado y el detectado. El resultado anterior se conserva
    como version previa en la tabla `resultados`.
- Reprocesar un documento en `error` queda fuera del MVP (ADR-006, I).

## Webhook (salida)
Configurable por proceso. `POST <url>` con cabecera `X-Firma: sha256=<HMAC(cuerpo, WEBHOOK_SECRET_HMAC)>`.
Eventos: `documento.completado`, `documento.error`, `folio.estado_cambiado`.
Cuerpo: `{evento, fecha, folio, identificador_unico_documento?, datos: ResultadoDocumento | ResultadoExpediente}`.

## Estados
Documento: `pendiente -> procesando -> completado | error`. Ademas `completado -> pendiente` solo al
confirmar una clasificacion distinta de la usada para extraer (ADR-006, 2.5).
Expediente: `en_revision -> aprobado | rechazado`. `aprobado` y `rechazado` son finales (ADR-006, G).
