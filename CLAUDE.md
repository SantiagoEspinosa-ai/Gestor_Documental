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
11. Respeta la arquitectura de `docs/arquitectura.md` (ADR-005): otros modulos solo importan tu
    `servicio.py`; boto3, pytesseract y llamadas a Ollama/OpenRouter solo dentro de su adaptador.

## Stack
Python 3.12 + FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16 + pgvector, boto3 (S3),
Tesseract via pytesseract, PyMuPDF, Ollama, React 18 + Vite. BackgroundTasks para procesamiento.

## Modulos y responsables
- ingesta, api, expediente, auth y, desde el 2026-10-01, frontend, tests e2e y demo: PERSONA_1
- orquestador, motor_ia y, desde el 2026-10-01, fixtures y rag (memoria, embeddings y conocimiento): PERSONA_2
- PERSONA_3 paso a otro proyecto el 2026-10-01 y su linea se repartio entre las dos (traspaso en
  `docs/equipo/PERSONA_3_estado.md`)

## Ramas y flujo de trabajo
| Rama | Persona | Modulos |
|---|---|---|
| `feat/plataforma` | PERSONA_1 | ingesta, core, api, expediente, frontend, tests e2e |
| `feat/motor-ia` | PERSONA_2 | configuracion, orquestador, motor_ia, validacion, rag, fixtures |
| `feat/interfaz` | (sin uso desde el 2026-10-01) | Todo su contenido esta en `main` (PR #10); no se hace commit en ella |

1. Cada persona trabaja y hace commit solo en su rama. Nadie hace commit directo en `main`.
2. Al empezar el dia: `git fetch` y `git merge origin/main` en tu rama para traer lo integrado.
3. Al terminar cada etapa (dias 5, 8 y 12) cada uno abre un Pull Request de su rama a `main`;
   lo revisa otra persona y se fusiona. Asi `main` acaba con el proyecto completo.
4. Cambios en ficheros compartidos (docs, config, contratos) van en un PR pequeno aparte y se avisa.

## Prompts de arranque por persona
Cada persona empieza su sesion de Claude Code pegando su fichero de `docs/equipo/`:
- PERSONA_1 -> `docs/equipo/PERSONA_1_plataforma.md`
- PERSONA_2 -> `docs/equipo/PERSONA_2_motor_ia.md`
- Tareas heredadas de PERSONA_3: seccion "Tareas heredadas de PERSONA_3" del prompt de cada una, y
  `docs/equipo/PERSONA_3_estado.md` (estado, acuerdos, reparto y recortes)
Estado y siguientes pasos de PERSONA_1: `docs/equipo/PERSONA_1_estado.md`.
Spec vigente de PERSONA_2: `docs/motor_ia/SPEC_CONFIGURACION.md`.
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
