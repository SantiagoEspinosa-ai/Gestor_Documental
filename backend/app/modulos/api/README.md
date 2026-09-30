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
