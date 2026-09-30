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
  `ResumenFolio` (Contrato 1, ADR-006 1.1) = `{folio, proceso, estado_general, recomendacion_global,
  n_documentos, n_bloqueantes_sin_resolver, fecha_solicitud}`. `PaginaFolios` es del Contrato 2.
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
  `ingesta.procesamiento.procesar` en segundo plano (motor stub hasta que llegue el de PERSONA_2).
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
- Fuente: `ingesta.servicio.listar_tipos()` sobre `ingesta/tipos.py`, provisional hasta que llegue
  `configuracion.servicio.listar()` de PERSONA_2.
- Errores: 401.

## auditoria.py

### GET /api/v1/auditoria (admin)
- Query: `folio?`, `pagina` >= 1, `tamano_pagina` 1-100 (50 por defecto).
- Salida 200: `{elementos: [EntradaAuditoria], total, pagina, tamano_pagina}`, del mas reciente al
  mas antiguo (`creado_en` desc, `id` desc). `EntradaAuditoria` = `{id, usuario, accion, folio,
  documento_id (str o null), detalle, modelo, version_prompt, creado_en}`.
- La respuesta paginada se aparta de ADR-006 1.5 ("lista de `EntradaAuditoria`"); se formalizara con
  el ADR-008 (lo redacta PERSONA_3), que tambien anade `referencia_externa` a `ResumenFolio`.
- Errores: 401; 403 `SIN_PERMISO` (revisor, integrador); 422 `PETICION_INVALIDA`.
