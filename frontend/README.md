# frontend (responsable: PERSONA_3)

React 18 + Vite. Consume `docs/contratos/endpoints.md`. Hasta que la API exista, usar msw con
respuestas construidas a partir del ejemplo de `ResultadoDocumento` en `backend/app/schemas/resultado.py`.

Pantallas MVP: login, lista de folios, carga de documentos, vista de expediente (diapositiva 8):
documentos del folio, detalle, datos extraidos con confianza, alertas por severidad,
comparaciones, acciones del revisor.

Arranque: `npm create vite@latest . -- --template react-ts && npm i && npm run dev`
