# api  (responsable: PERSONA_1)

Routers FastAPI de `docs/contratos/endpoints.md` (Contrato 2), bajo `/api/v1`.
Entrada: HTTP con `Authorization: Bearer <JWT>`. Salida: `ResultadoDocumento` / `ResultadoExpediente`
(Contrato 1) o errores `{codigo, mensaje}`. Sin logica de negocio: delega en los modulos.
Excepcion: `GET /folios/{folio}/antecedentes` lo implementa PERSONA_3 (rag) y se registra aqui.
