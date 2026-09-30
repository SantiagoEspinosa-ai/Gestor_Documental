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
