# PERSONA_1 - Estado y siguientes pasos (traspaso)

Actualizado: 2026-09-30, al cerrar la etapa 1 en `feat/plataforma`. Sirve para retomar el trabajo en
otra maquina o en otro chat de Claude Code. La especificacion completa sigue en
`docs/equipo/PERSONA_1_plataforma.md`; este fichero dice en que punto estamos y que toca ahora.

## Hecho en la etapa 1 (rama `feat/plataforma`)
| Tarea | Que | Commit |
|---|---|---|
| 1 | `core/config.py`: settings con pydantic-settings (+ fix del `.env` de la raiz y `CONFIG_DIR`) | e3ec810, a3ff7db |
| 2 | `core/db.py` (SQLAlchemy 2, engine perezoso) e inicializacion de Alembic | 68d9d4e |
| 3 | `core/modelos.py` y migracion 0001 (8 tablas, CHECK y UNIQUE) | 93d74fe |
| 4 | `core/procesos.py`: `procesos.yaml` -> tabla `procesos` en el lifespan (+ migrar antes de arrancar en Docker) | 5a70f19, b3f0a9a |
| 5 | `core/seguridad.py`: bcrypt, JWT, `usuario_actual`, `requiere_rol`; `scripts/crear_usuario.py` | 5c1041b |
| 6 | `POST /auth/login`, `GET /auth/yo` y manejo global de errores `{codigo, mensaje}` | 94b6194 |
| 7 | Folios: crear (numeracion atomica, migracion 0002), consultar y listar; alineado con ADR-004/006 | 7368f77, db6e54c |
| 8 | `core/almacenamiento.py`: S3 real, SSE-S3, nunca sobrescribe (+ fix URL prefirmada regional) | 721d494, 7a6fdb7 |
| 9 | Ingesta: hash, duplicados (`DUP-001`), subida a S3, stub de `procesar_documento` | f9c3aa6 |
| 10 | Router de documentos: subir (202), resultado y URL del original; tipo MIME por extension y firma magica | 9a24406 |
| - | `GET /procesos` (revisor sin `webhook_url` ni `modelos`) | 3cdeb4d |
| - | `GET /tipos-documentales` | d1326d9 |
| - | `GET /auditoria` (solo admin, paginado) | 2d5b8eb |

Entregable de la etapa 1 probado el 2026-09-30 contra el bucket real (us-east-2) y PostgreSQL local:
login -> folio de prueba `ONB-2026-000002` -> subida de un PDF ficticio -> `completado` (stub) ->
descarga por URL prefirmada con bytes identicos -> objeto con `AES256` y `application/pdf` ->
documento, resultado v1 y auditoria en BD. La prueba destapo el fallo de la URL prefirmada con el
endpoint global (307 fuera de us-east-1), corregido en 7a6fdb7. En el bucket quedan 2 PDFs ficticios
de prueba (el IAM no puede borrar). Tests: 155 en verde con SQLite + moto, y la concurrencia de folios
tambien contra PostgreSQL (20 hilos, sin huecos ni duplicados).

## Decisiones del dia (2026-09-30)
| Tema | Decision | Donde |
|---|---|---|
| Contratos | ADR-004 y ADR-006 aceptados y aplicados; catalogos `codigos_error.md` y `codigos_alertas.md` en `main` | PR #1 y #2 |
| ADR-007 | Rechazado: la confianza la sigue dando el modelo | - |
| Bucket | S3 real en us-east-2, privado, IAM solo con Put/Get/ListBucket (sin Delete); claves solo en `.env` | tarea previa del prompt |
| PostgreSQL local | Lo arranca el usuario con `docker compose up -d db` | - |
| Decidir un folio con documentos `pendiente` o `procesando` | 409 `DOCUMENTO_EN_PROCESO` | pregunta 1 de PERSONA_3 |
| Corregir datos o confirmar la clasificacion de un documento en `error` | 409 `DOCUMENTO_CON_ERROR` (codigo nuevo: se anade a `codigos_error.md` en el mismo commit que lo use, etapa 2). Resolver sus alertas si se permite | pregunta 2 de PERSONA_3 |
| `EXP-001` | Al crear el folio, una por cada tipo requerido que falte (bloqueante, en `alertas_expediente`, `campo` = tipo). Se recalcula al procesar un documento o confirmar su clasificacion; cuenta el tipo confirmado, si no el detectado, si no el declarado. Si el revisor la marco `aplica=false`, se conserva | pregunta 3 de PERSONA_3 |
| `POST /folios` | 201 (ya implementado) | pregunta 4 de PERSONA_3 |
| Alertas informativas | Propuesta de PERSONA_1, sin acordar: `VAL-003` (falta un campo opcional, la emite PERSONA_2) y `EXP-002` (tipo subido que el proceso no pide, la emite PERSONA_1) | pendiente del equipo |

## Como retomar
1. En la raiz del repo: `cp .env.example .env` y rellenarlo a mano (claves AWS por canal seguro,
   nunca en el repo ni en chats). `.env` nunca se sube.
2. Entorno: `cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt`.
3. PostgreSQL: `docker compose up -d db`. Fuera de Docker el host es `localhost`, no `db`: exporta
   `DATABASE_URL=postgresql+psycopg://gestor:gestor@localhost:5432/gestor` en la terminal (no la
   escribas en ficheros del repo).
4. `alembic upgrade head` (desde `backend/`).
5. Tests: `python -m pytest -q`. Con `TEST_POSTGRES_URL=<la misma URL>` corre tambien la
   concurrencia de folios contra PostgreSQL.
6. Usuarios de desarrollo: `PYTHONPATH=. python ../scripts/crear_usuario.py --usuario revisor_demo --rol revisor`
   (la contrasena se pide por teclado o sale de `NUEVA_CONTRASENA`).

## Pendiente
### Cierre de la etapa 1
- [ ] Pull Request de `feat/plataforma` a `main` el dia 5 (lo revisa otra persona).
- [ ] Cuando el modulo `configuracion` de PERSONA_2 llegue a `main`: `configuracion.cargar()` en el
      lifespan de `main.py` y sustituir `ingesta/tipos.py` por `configuracion.servicio.obtener()/listar()`.
- [ ] Entregar las claves AWS a PERSONA_3 por canal seguro (las necesita para los e2e).
- [ ] Decidir con el equipo la maquina de Ollama (sin GPU de momento) y el resto de `propuesta/base-etapa0`.

### Etapa 2 (dias 6-8), cuando PERSONA_2 entregue `procesar_documento`
- Conectar el pipeline real (sustituye a `ingesta/procesamiento_stub.py`) y guardar `resultados`.
- `EXP-001`: recalculo al procesar o confirmar la clasificacion (la creacion inicial va al crear el folio).
- `modulos/validacion/comparaciones.py`: `ComparacionCampo` y `CMP-001` solo en `alertas_expediente`.
- Recomendacion global.
- Endpoints del revisor: corregir datos (`correcciones` en el resultado), confirmar clasificacion
  (versionado y reproceso si cambia el tipo), resolver alertas por `alerta_id` (documento y
  expediente) y decision del folio (409 `DECISION_BLOQUEADA`, `FOLIO_CERRADO`,
  `DOCUMENTO_EN_PROCESO`, `DOCUMENTO_CON_ERROR`). Todo a auditoria.

### Etapa 3
Como en el prompt: resumen `.md`, webhooks HMAC, enmascaramiento en logs y "mostrar" auditado.
