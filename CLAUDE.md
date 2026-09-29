# Instrucciones para Claude Code en este repo

Idioma: espanol. Responde y comenta codigo en espanol.

## Reglas inquebrantables
1. Antes de proponer codigo, indica en que modulo de `backend/app/modulos/` encaja.
2. Nunca modifiques `backend/app/schemas/resultado.py`, `docs/contratos/endpoints.md` ni
   `backend/app/modulos/motor_ia/interfaces.py` sin proponer primero un ADR en `docs/adr/`.
3. Nunca escribas claves, tokens ni cadenas de conexion reales. Usa `TU_CLAVE_AQUI`.
4. Nunca uses datos personales reales en ejemplos, tests o fixtures. Usa nombres inventados.
5. Los prompts van en `prompts/*.md`, nunca como strings largos en el codigo.
6. Cada modulo tiene un `README.md` con contrato de entrada/salida. Actualizalo si cambias el modulo.
7. Reglas de validacion y parsers llevan test en `backend/tests/`.
8. Nombres de campo JSON: snake_case en espanol (ver `resultado.py`).
9. La IA recomienda; la decision final del expediente es humana. No automatices aprobaciones.
10. Alcance MVP primero. Si algo excede el MVP, dilo antes de implementarlo.

## Stack
Python 3.12 + FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16 + pgvector, boto3 (S3),
Tesseract via pytesseract, PyMuPDF, Ollama, React 18 + Vite. BackgroundTasks para procesamiento.

## Modulos y responsables
- ingesta, api, expediente, auth: PERSONA_1
- orquestador, motor_ia: PERSONA_2
- frontend, fixtures, tests e2e, rag: PERSONA_3

## Prompts de arranque por persona
Cada persona empieza su sesion de Claude Code pegando su fichero de `docs/equipo/`:
- PERSONA_1 -> `docs/equipo/PERSONA_1_plataforma.md`
- PERSONA_2 -> `docs/equipo/PERSONA_2_motor_ia.md`
- PERSONA_3 -> `docs/equipo/PERSONA_3_interfaz_calidad.md`
Esos ficheros son la especificacion vigente de cada linea de trabajo; si cambia el plan, se
actualizan ahi y se avisa al equipo.

## Plan por etapas
- Etapa 0 (dia 1): repo, docker compose, contratos, ADRs. Los tres juntos.
- Etapa 1 (dias 2-5): cimientos en paralelo contra mocks/stubs.
- Etapa 2 (dias 6-8): integracion e2e. Hito: subir 3 documentos y ver resultados en la UI.
- Etapa 3 (dias 9-12): expediente .md, RAG + memoria de folios, webhooks, extras por prioridad
  (1 enmascaramiento + correcciones, 2 calidad/recortes/alteraciones, 3 admin de tipos, 4 factura y gasto).
- Etapa 4 (dias 13-14): congelacion, tests, READMEs, demo desde cero.

## Plan completo
`docs/PLAN_PROYECTO.md` recoge todas las decisiones, el reparto y las tareas por etapa y persona.
Leelo al inicio de cada sesion junto con el prompt de la persona.
