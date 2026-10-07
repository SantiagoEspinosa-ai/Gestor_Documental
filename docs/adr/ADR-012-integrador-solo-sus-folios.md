# ADR-012: El integrador solo accede a los folios que ha creado

Fecha: 2026-10-07. Estado: ACEPTADO (2026-10-07, PERSONA_1 y PERSONA_2, PR #55). Propone: PERSONA_1. Revisa: PERSONA_2.
Afecta al Contrato 2 (`docs/contratos/endpoints.md`) solo con una nota en las filas afectadas: no cambian ni
los roles ni la forma de las respuestas.

## Contexto
- Revision de seguridad del 2026-10-07 y propuesta de PERSONA_2: hoy un integrador autenticado puede leer
  cualquier folio y cualquier documento si conoce su folio o su id, y subir documentos a folios de otros. Los
  folios son correlativos (`ONB-2026-000001`, `...002`), asi que se pueden adivinar.
- La plataforma no guardaba quien creo cada folio.

## Decision
1. Migracion 0007: `folios.creado_por` (texto, NULL), con el usuario que lo crea por `POST /folios`.
2. Para el rol **integrador**, en los endpoints que hoy le admite el contrato y que dependen de un folio:
   `GET /folios/{folio}`, `POST /folios/{folio}/documentos`, `GET /documentos/{id}` y
   `GET /folios/{folio}/resumen.md`. Si el folio no lo creo el, la respuesta es la misma que si no existiera:
   `404 FOLIO_NO_ENCONTRADO` (o `404 DOCUMENTO_NO_ENCONTRADO` para un documento), para no revelar que existe.
3. Los folios anteriores a la migracion (`creado_por` NULL) no son de ningun integrador: no los ve.
4. Revisor y admin, sin cambios: ven y operan todos los folios segun su rol.
5. El integrador sigue sin listado (`GET /folios` 403); abrirlo filtrado seria una evolucion que cambia el
   contrato y la UI.
6. Una sola regla en el codigo: `core.seguridad.es_folio_ajeno(usuario, creado_por)`.

## Alternativas
| Alternativa | Consecuencias |
|---|---|
| 403 en vez de 404 | Confirma que el folio existe: con folios correlativos permite enumerarlos |
| Propiedad por proceso o por organizacion del integrador | Mas flexible (varios usuarios de un mismo cliente), pero exige un modelo de organizaciones que el MVP no tiene |
| Dar los folios antiguos (NULL) al integrador que subio su primer documento | Se puede deducir de la auditoria, pero no es fiable; se prefiere el criterio conservador |

## Consecuencias
- Un integrador no puede leer ni subir a folios de otros, ni saber si existen.
- Si varios usuarios integradores trabajan para el mismo cliente, cada uno solo ve los suyos (ver la
  alternativa por organizacion).
- Los folios creados antes de la migracion solo los ven revisor y admin.
