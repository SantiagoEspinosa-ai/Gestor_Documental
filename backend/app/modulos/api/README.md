# api

Responsable: PERSONA_1. Routers FastAPI: validan con Pydantic, comprueban el rol y llaman a los
servicios; sin logica de negocio ni SQL propio (ADR-005). Contrato: `docs/contratos/endpoints.md`.
Todos los errores salen como `{codigo, mensaje}` (ADR-006 1.4); los 401 llevan `WWW-Authenticate: Bearer`.

## auth.py

### POST /api/v1/auth/login
- Entrada (JSON, sin campos extra): `{usuario, contrasena}`.
- Salida 200: `{access_token, rol, expires_in}` (`expires_in` en segundos).
- Errores: 401 `CREDENCIALES_INVALIDAS` (usuario inexistente, contrasena incorrecta o de mas de
  72 bytes: misma respuesta y mismo tiempo); 422 `PETICION_INVALIDA`.
- Audita `login` con `{"resultado": "ok" | "fallido"}` en cada intento.

### GET /api/v1/auth/yo
- Entrada: cabecera `Authorization: Bearer <token>`.
- Salida 200: `{usuario, rol}` (el rol vigente en BD).
- Errores: 401 `NO_AUTENTICADO` (sin token, token invalido o usuario borrado); 401 `TOKEN_CADUCADO`.

## folios.py
Todos requieren token (401 `NO_AUTENTICADO` / `TOKEN_CADUCADO`); 403 `SIN_PERMISO` si el rol no vale.

### POST /api/v1/folios (integrador, revisor)
- Entrada (JSON, sin campos extra): `{proceso, referencia_externa?}` (`referencia_externa` <= 100).
- Salida 201: `{folio, estado_general}`.
- Errores: 404 `PROCESO_NO_ENCONTRADO`; 409 `SECUENCIA_AGOTADA`; 422 `PETICION_INVALIDA`.

### GET /api/v1/folios (revisor, admin)
- Query: `proceso?`, `estado_general?` (en_revision | aprobado | rechazado), `pagina` >= 1,
  `tamano_pagina` 1-100 (20 por defecto).
- Salida 200: `{elementos: [ResumenFolio], total, pagina, tamano_pagina}`, del mas reciente al mas antiguo.
  `ResumenFolio` (Contrato 1, ADR-006 1.1 y ADR-008) = `{folio, proceso, estado_general,
  recomendacion_global, n_documentos, n_bloqueantes_sin_resolver, fecha_solicitud, referencia_externa}`. `PaginaFolios` es del Contrato 2.
- Errores: 422 `PETICION_INVALIDA`.

### GET /api/v1/folios/{folio} (cualquier rol)
- Salida 200: `ResultadoExpediente` (Contrato 1), con `referencia_externa` y `fecha_solicitud`
  (ADR-004) y los datos de la decision (ADR-006 G).
- Errores: 404 `FOLIO_NO_ENCONTRADO`.

## documentos.py
Todos requieren token (401); 403 `SIN_PERMISO` si el rol no vale.

### POST /api/v1/folios/{folio}/documentos (integrador, revisor)
- Entrada: multipart con `archivo` y `tipo_declarado?`. Se leen como mucho 20 MB + 1 byte.
- Salida 202: `{identificador_unico_documento, estado_analisis: "pendiente"}` y lanza
  `ingesta.servicio.procesar_documento` en segundo plano (motor stub hasta que llegue el de PERSONA_2).
- Errores: 404 `FOLIO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO`; 413 `ARCHIVO_DEMASIADO_GRANDE`;
  415 `FORMATO_NO_PERMITIDO` (extension o contenido); 422 `PETICION_INVALIDA`.
- El Content-Type del cliente se ignora: el del objeto en S3 sale de la extension.

### GET /api/v1/documentos/{id} (cualquier rol)
- Salida 200: `ResultadoDocumento` de la version mayor, con `estado_analisis` y
  `tipo_documental_confirmado` de la BD; sin resultado todavia, uno minimo en `pendiente` con sus alertas.
- Errores: 404 `DOCUMENTO_NO_ENCONTRADO` (tambien si el id no es un UUID).

### GET /api/v1/documentos/{id}/original (revisor, admin)
- Salida 200: `{url}` prefirmada y temporal (`URL_PREFIRMADA_SEGUNDOS`). Sin auditoria hasta la etapa 3.
- Errores: 404 `DOCUMENTO_NO_ENCONTRADO`.

## procesos.py

### GET /api/v1/procesos (admin, integrador, revisor)
- Salida 200: lista de `Proceso` ordenada por nombre: `{nombre, prefijo_folio, tipos_requeridos,
  tipos_opcionales, permitir_antecedentes, caducidad_antecedentes_dias, webhook_url, modelos}`.
  Para el rol revisor se omiten `webhook_url` y `modelos` (no aparecen, ni como null).
- Logica en `core/procesos.py` (`listar_procesos`): la tabla `procesos` es de `core`.
- Errores: 401; 403 `SIN_PERMISO`.

## tipos_documentales.py

### GET /api/v1/tipos-documentales (cualquier rol)
- Salida 200: lista de `TipoDocumental` ordenada por nombre: `{nombre, nombre_visible, categoria,
  descripcion, formatos_permitidos, campos: {<campo>: {tipo, obligatorio, patron?}},
  confianza_minima_clasificacion, confianza_minima_campo, reglas, comparaciones}`.
  `formatos_permitidos` en minusculas y sin punto; `patron` solo si la ficha lo define.
- Fuente: `ingesta.servicio.listar_tipos()`, que arma la forma del contrato desde
  `configuracion.servicio.listar()` de PERSONA_2 (`ingesta/tipos.py`).
- Errores: 401.

## auditoria.py

### GET /api/v1/auditoria (admin)
- Query: `folio?`, `pagina` >= 1, `tamano_pagina` 1-100 (50 por defecto).
- Salida 200: `PaginaAuditoria` (ADR-008) = `{elementos: [EntradaAuditoria], total, pagina,
  tamano_pagina}`, del mas reciente al mas antiguo (`creado_en` desc, `id` desc). `EntradaAuditoria` = `{id, usuario, accion, folio,
  documento_id (str o null), detalle, modelo, version_prompt, creado_en}`.
- Errores: 401; 403 `SIN_PERMISO` (revisor, integrador); 422 `PETICION_INVALIDA`.

## revision.py
Acciones del revisor (E2.6). Solo rol revisor (403 para el resto; 401 sin token). La logica esta en
`expediente.servicio`.

### POST /api/v1/documentos/{id}/alertas/{alerta_id}/resolver
### POST /api/v1/folios/{folio}/alertas/{alerta_id}/resolver
- Entrada (JSON, sin campos extra): `{aplica: bool, comentario?}` (`comentario` <= 1000).
- Salida 200: `ResultadoDocumento` (documento) o `ResultadoExpediente` (expediente, con la
  `recomendacion_global` ya recalculada).
- Guarda `aplica`, `comentario_revisor`, `resuelta_por`, `resuelta_en`; se puede volver a resolver
  mientras el folio este abierto. Audita `alerta_resuelta` sin el comentario.
- Errores: 404 `DOCUMENTO_NO_ENCONTRADO` / `FOLIO_NO_ENCONTRADO`; 404 `ALERTA_NO_ENCONTRADA` (no
  existe, no es UUID, es de otro documento o folio, de expediente por la ruta de documento o al reves,
  o del motor de una version anterior); 409 `FOLIO_CERRADO`; 409 `DOCUMENTO_EN_PROCESO` (documento
  `pendiente` o `procesando`; en `error` si se puede); 422 `PETICION_INVALIDA`.

### PATCH /api/v1/documentos/{id}/datos (ADR-006 2.4)
- Entrada: `{campo: valor}` no vacio. Cada campo tiene que estar en la ficha con la que se extrajo
  (confirmado > declarado > detectado). Regla de valores:
  - `null`: solo en campos con `obligatorio: false`; vacia el campo (en un obligatorio, 422);
  - tipo `anio`: entero de 4 cifras o texto `"AAAA"`; se guarda como entero, igual que lo da el motor;
  - el resto: texto no vacio; tipo `fecha` en `AAAA-MM-DD`; si la ficha tiene `patron`, cumplirlo.
- Salida 200: `ResultadoDocumento` con el valor corregido, confianza 1.0, evidencia
  `correccion_revisor` y la correccion en `correcciones`. Audita `dato_corregido` solo con los
  nombres de los campos.
- Errores: 404 `DOCUMENTO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO`, `DOCUMENTO_EN_PROCESO`,
  `DOCUMENTO_CON_ERROR`; 422 `PETICION_INVALIDA` (nombra el campo, nunca el valor).

### POST /api/v1/documentos/{id}/confirmar-clasificacion (ADR-006 2.5)
- Entrada: `{tipo_documental}` (tiene que existir su ficha).
- Mismo tipo con el que se extrajo: guarda `tipo_documental_confirmado` y resuelve las `CLS-001`
  visibles sin revisar (`aplica=false`). Otro tipo: guarda, pasa el documento a `pendiente` y lanza el
  reproceso con `tipo_confirmado` en segundo plano (version N+1; la anterior se conserva).
- Salida 200: `ResultadoDocumento` (en `pendiente` si se reprocesa). Audita `clasificacion_confirmada`
  con `{tipo, reproceso}`.
- Errores: 404 `DOCUMENTO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO`, `DOCUMENTO_EN_PROCESO`,
  `DOCUMENTO_CON_ERROR`; 422 `PETICION_INVALIDA`.

### POST /api/v1/folios/{folio}/decision (ADR-006 2.2 y G)
- Entrada (JSON, sin campos extra): `{decision: aprobar | rechazar, comentario?}` (`comentario` <= 1000).
- Salida 200: `ResultadoExpediente` con el folio cerrado (`aprobado` o `rechazado`), `decision_humana`,
  `comentario_decision`, `usuario_decision` y `fecha_decision`. Audita `decision_tomada` sin el comentario.
- Errores: 404 `FOLIO_NO_ENCONTRADO`; 409 `FOLIO_CERRADO` (ya decidido; no se reabre nunca);
  409 `DOCUMENTO_EN_PROCESO` (algun documento `pendiente` o `procesando`, al aprobar y al rechazar);
  409 `DECISION_BLOQUEADA` (solo al aprobar: alguna bloqueante visible con `aplica` distinto de false);
  422 `PETICION_INVALIDA`. Un documento en `error` no bloquea la decision.

## Detalle de la auditoria por accion
`modelo` y `version_prompt` van en sus columnas; `detalle` nunca lleva valores de campos, comentarios
ni contrasenas.

| accion | detalle |
|---|---|
| `login` | `{resultado: "ok" \| "fallido"}` |
| `folio_creado` | sin detalle (`{}`) |
| `documento_subido` | `{hash_sha256, tamano_bytes, duplicado}` |
| `documento_procesado` | `{proveedor, respaldo_usado, confianzas_modelo, tiempos, tokens, ...}` (lo serializable de `datos_auditoria` del motor) |
| `dato_corregido` | `{campos: [nombres]}` |
| `clasificacion_confirmada` | `{tipo, reproceso}` |
| `alerta_resuelta` | `{alerta_id, codigo, aplica}` |
| `decision_tomada` | `{decision}` |
