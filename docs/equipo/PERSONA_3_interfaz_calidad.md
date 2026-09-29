# Prompt de arranque - PERSONA_3 (Frontend, fixtures, tests e2e, memoria de folios)

Copia todo este bloque como primer mensaje en Claude Code dentro del repo.

---

Eres mi asistente de desarrollo en este repositorio. Lee primero `CLAUDE.md`, `README.md`,
`docs/adr/*.md`, `docs/contratos/endpoints.md`, `backend/app/schemas/resultado.py`,
`config/tipos/*.yaml` y `frontend/README.md`. Los contratos estan congelados.

Soy PERSONA_3 y soy responsable de `frontend/`, `scripts/generar_fixtures.py`, los tests e2e y,
en la etapa 3, la memoria de folios en `modulos/rag`. PERSONA_1 hace la plataforma (API) y PERSONA_2
el motor de IA. Hasta que su API exista, el frontend trabaja contra mocks (msw) construidos desde
el Contrato 1 y el Contrato 2; nunca inventes campos que no esten en los contratos.

## Objetivo de la etapa 1 (dias 2-5)
(a) Set de fixtures ficticios en `fixtures/generados/` cubriendo 3 tipos x 3 modalidades y los
4 casos. (b) UI navegable con mocks: login, folios, carga, expediente y revision.

## Tareas, en este orden
1. `scripts/generar_fixtures.py`: con Pillow y PyMuPDF genera para cada persona ficticia de
   `PERSONAS_FICTICIAS` un pasaporte, una credencial de elector y un comprobante de domicilio.
   Aspecto aproximado (bloques de texto con las etiquetas, una silueta gris como foto, dos lineas
   tipo MRZ inventadas). Nada de escudos, logotipos ni nombres de organismos reales. Por documento:
   `*_digital.pdf` (texto real), `*_escaneado.pdf` (render a imagen con ruido y ligera rotacion, sin
   capa de texto) y `*_foto.jpg` (perspectiva, sombra). Casos: `sano`, `domicilio_distinto`,
   `vencido` (pasaporte con fecha pasada), `duplicado` (copia byte a byte). Escribe
   `fixtures/generados/INDICE.md` con caso, archivo y valores esperados de cada campo (sirve de
   verdad de referencia para los tests de PERSONA_2).
2. Frontend: `npm create vite@latest . -- --template react-ts`. Router (react-router), cliente
   HTTP con el JWT en cabecera, `.env` con `VITE_API_URL`. Sin librerias pesadas: CSS modules o
   Tailwind, iconos lucide-react.
3. Mocks con msw en `frontend/src/mocks/`: handlers para TODOS los endpoints del Contrato 2, con
   fixtures JSON que respeten `ResultadoDocumento` y `ResultadoExpediente` (incluye un folio con
   alertas de las 4 severidades y una comparacion que no coincide).
4. Pantallas:
   - Login (usuario/contrasena -> token; guardar rol).
   - Folios: lista con estado general; boton "Nuevo folio" (elige proceso).
   - Carga: arrastrar archivos, seleccionar `tipo_declarado`, mostrar `pendiente -> procesando ->
     completado` con polling a `GET /documentos/{id}` cada 3 s.
   - Expediente (diapositiva 8): cabecera con folio, referencia y estado; columna izquierda con
     documentos y su estado; centro con visor del original (URL prefirmada), clasificacion
     declarada vs detectada y tabla de datos extraidos con barra de confianza y evidencia; derecha con
     alertas agrupadas por severidad (colores: informativa azul, preventiva amarillo, critica naranja,
     bloqueante rojo), comparaciones entre documentos y resultado individual/global.
   - Acciones del revisor (solo rol revisor): corregir dato (inline, PATCH), confirmar clasificacion,
     marcar alerta como aplica / falso positivo, decision del folio (deshabilitada si hay bloqueante
     sin resolver, con el motivo visible).
   - Boton "Ver resumen" que muestra el `resumen.md` renderizado.
5. Enmascaramiento en UI (extra 1, adelantalo si vas bien): CURP y numero de documento se muestran
   parcialmente (`****1234`) salvo que el revisor pulse "mostrar", y esa accion queda en auditoria.
6. Tests: Playwright con los mocks recorriendo el flujo completo; Vitest para el componente de
   confianza y el de alertas.

## Etapa 2 (dias 6-8)
- Cambiar msw por la API real de PERSONA_1 (mismo contrato, solo cambia la URL). Reportar cualquier
  desviacion del contrato como issue, no adaptar el frontend en silencio.
- Pruebas e2e reales con los 4 casos de fixtures sobre `docker compose`.

## Etapa 3 (dias 9-12): memoria de folios (con PERSONA_2, que hace la base de conocimiento)
- `modulos/rag/memoria.py`: al generarse `resumen.md` de un folio, dividir en chunks, embeddings con
  Ollama `nomic-embed-text` y guardar en tabla `memoria_folios(folio, proceso, referencia_persona,
  chunk, embedding vector, caduca_en)`.
- `buscar_antecedentes(referencia_persona, proceso)`: solo si `permitir_antecedentes` del proceso,
  solo chunks no caducados. Endpoint `GET /folios/{folio}/antecedentes` (coordinar router con
  PERSONA_1) y pantalla "Antecedentes" en el expediente.
- Pantalla de configuracion de procesos (prefijo, webhook, `permitir_antecedentes`).

## Como trabajar
- Ningun dato real en fixtures, mocks ni capturas. Nombres inventados.
- Commits `feat(frontend): ...`, `feat(fixtures): ...`, `feat(rag): ...`.
- Si el contrato no cubre algo que la UI necesita, propon un ADR en vez de anadir campos.
