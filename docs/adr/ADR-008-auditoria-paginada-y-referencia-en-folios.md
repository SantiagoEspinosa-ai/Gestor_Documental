# ADR-008: Auditoria paginada y referencia externa en la lista de folios

Fecha: 2026-09-30. Estado: ACEPTADO el 2026-09-30 (revision del PR #7: aprobado por PERSONA_1, que
implementa los dos puntos, y por PERSONA_2).
Propone: PERSONA_3. Afecta a: Contrato 1 (`backend/app/schemas/resultado.py`, `ResumenFolio`) y
Contrato 2 (`docs/contratos/endpoints.md`, `GET /auditoria`). Modifica el punto 1.5 del ADR-006 en
lo que se refiere a `/auditoria`. Este ADR no cambia ninguno de los dos contratos: los cambios se
aplican en un PR de contratos aparte cuando se acepte (ver "Aplicacion").

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| 1 | `GET /auditoria` paginado con `{elementos, total, pagina, tamano_pagina}` | PERSONA_1 (ya en `main`, PR #3) | Aceptada la propuesta: formaliza lo implementado, sin cambios de codigo |
| 2 | `referencia_externa: str \| None = None` en `ResumenFolio` | PERSONA_1 | Aceptada la propuesta: se implementa cuando el PR de contratos este en `main` |

## Contexto
- El ADR-006 (1.5) acepto `/auditoria` como lista: `[{id, usuario, accion, folio, documento_id,
  detalle, modelo, version_prompt, creado_en}]`, del mas reciente al mas antiguo. `endpoints.md`
  dice "lista de `EntradaAuditoria`".
- El PR #3 de PERSONA_1 (fusionado en `main` el 2026-09-30) implementa `GET /auditoria` paginado,
  con la misma forma que `PaginaFolios`. `backend/app/modulos/api/README.md` lo anota como
  pendiente de reflejar en `endpoints.md`. Hoy la API y el contrato no coinciden, y el frontend lo
  trata como desviacion conocida (`PaginaAuditoria` en `frontend/src/tipos/contrato.ts`).
- La auditoria crece con cada accion (logins, subidas, procesamientos, correcciones, decisiones).
  Una lista sin limite hace cada vez mas pesada la respuesta y la pantalla de administracion.
- La cabecera del expediente ya muestra `referencia_externa` (ADR-004). La pantalla "Folios"
  (ADR-006, 1.1) tambien deberia mostrarla, para que el revisor reconozca el tramite sin abrirlo.
  Pero `ResumenFolio` no la tiene. Pedirla con `GET /folios/{folio}` por cada fila supone 20
  peticiones por pagina, asi que el frontend ha quitado la columna hasta que se decida este ADR.

---

### Punto 1. `GET /auditoria` paginado
Problema: el contrato dice "lista" y la API real devuelve una pagina. Hay que elegir una forma y
que contrato, API y mocks coincidan.

Propuesta: se formaliza lo que ya hace la API.

    GET /auditoria?folio=&pagina=1&tamano_pagina=50        (rol admin)

    {"elementos": [EntradaAuditoria], "total": int, "pagina": int, "tamano_pagina": int}

- `pagina` >= 1 (por defecto 1); `tamano_pagina` de 1 a 100 (por defecto 50). Fuera de rango:
  422 `PETICION_INVALIDA`.
- Orden: del mas reciente al mas antiguo (`creado_en` desc y, en empate, `id` desc).
- `folio` opcional filtra por folio. `total` cuenta las entradas que cumplen el filtro.
- `EntradaAuditoria` no cambia. Tampoco la lista cerrada de `accion` ni la regla de que `detalle`
  nunca lleva valores sensibles sin enmascarar.
- En "Formas de respuesta" de `endpoints.md` se anade `PaginaAuditoria` junto a `PaginaFolios`.
  Es una forma del Contrato 2 (como `PaginaFolios`): no se anade a `resultado.py`.

Confirmado por PERSONA_1 en la revision del PR #7: coincide con lo implementado en el PR #3
(`tamano_pagina` 50 por defecto y de 1 a 100, orden `creado_en` desc e `id` desc, filtro por `folio`,
422 `PETICION_INVALIDA` fuera de rango).

Implementa: PERSONA_1, ya implementado (`api/auditoria.py`, `core/auditoria.py`); al aceptarse,
quita la nota de pendiente de `api/README.md`. PERSONA_3: `PaginaAuditoria` en los tipos y en el
mock (ya hecho, marcado como desviacion conocida) y la pantalla de auditoria.

Alternativa (si se rechaza): vuelve la lista completa del ADR-006 1.5. PERSONA_1 cambia el router
para devolver `list[EntradaAuditoria]` y ajusta sus tests. PERSONA_3 quita `PaginaAuditoria` y pagina
en el navegador. Coste: la respuesta crece sin limite con el uso.

### Punto 2. `referencia_externa` en `ResumenFolio`
Problema: la lista de folios no puede mostrar la referencia del solicitante sin una peticion por
fila.

Propuesta: anadir un campo opcional a `ResumenFolio` en el Contrato 1:

    referencia_externa: str | None = None  # ADR-008; = folios.referencia_externa (ADR-004)

- Mismo significado que en `ResultadoExpediente` (ADR-004): identificador opaco del sistema que
  integra (p. ej. `CLI-000123`), nunca el nombre de la persona.
- `GET /folios` lo rellena desde `folios.referencia_externa`. `null` si el folio se creo sin
  referencia.
- Solo se anade el campo. Filtrar o buscar por `referencia_externa` en `GET /folios` queda fuera
  de este ADR (fuera del MVP).

Implementa: PERSONA_1 (`expediente.listar_folios` y su test), cuando el PR de contratos que anade
el campo a `resultado.py` este en `main` (confirmado en la revision del PR #7). PERSONA_3:
`ResumenFolio` en `contrato.ts`, mocks (`resumenFolio` en `mocks/logica.ts`) y columna "Referencia"
en `PaginaFolios.tsx`.

Alternativa (si se rechaza): la lista muestra solo el folio. La referencia se ve al abrir el
expediente o la carga (viene en `ResultadoExpediente`). No se piden expedientes por fila.

---

## Aplicacion
1. Al aceptarse, PERSONA_3 abre un PR de contratos pequeno y aparte, que revisa PERSONA_1:
   - `resultado.py`: `referencia_externa` en `ResumenFolio` (punto 2);
   - `endpoints.md`: fila de `GET /auditoria` con `pagina` y `tamano_pagina` y respuesta
     `PaginaAuditoria`, `PaginaAuditoria` en "Formas de respuesta" (punto 1) y la nota de
     "Ampliado por" con ADR-008.
   Se avisa al equipo al abrirlo y al fusionarlo (CLAUDE.md, "Ramas y flujo de trabajo", punto 4).
2. PERSONA_1: rellenar `referencia_externa` en `listar_folios` con su test y quitar la nota de
   `api/README.md`.
3. PERSONA_3: quitar la marca de desviacion de `contrato.ts` y `mocks/handlers.ts`, anadir
   `referencia_externa` a `ResumenFolio` y la columna de la lista. `backend/tests/test_contrato_frontend.py`
   comprueba que `contrato.ts` coincide con `resultado.py`.

## Consecuencias
- Punto 1: el contrato pasa a describir lo que ya hace la API. No hay cambio de codigo en el
  backend, y `endpoints.md`, la API y los mocks vuelven a coincidir.
- Punto 2: campo opcional con valor por defecto, no rompe a nadie. Los webhooks no se ven
  afectados, porque envian `ResultadoDocumento` o `ResultadoExpediente`, no `ResumenFolio`.
- La lista de folios gana la referencia sin peticiones extra. `GET /folios` sigue siendo solo para
  revisor y admin.
- Si algun punto se rechaza, su alternativa ya esta escrita y no hace falta otra ronda.
