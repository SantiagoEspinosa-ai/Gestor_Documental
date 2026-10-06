# PERSONA_1 - Estado y siguientes pasos (traspaso)

Actualizado: 2026-10-01. Etapa 1 CERRADA: el PR #3 (`feat/plataforma` -> `main`) se aprobo y fusiono
el 2026-09-30. En curso: la etapa 2. Sirve para retomar el trabajo en
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
| ADR-007 | Aceptado (PR #4 de PERSONA_2): la confianza la calcula el codigo; en la etapa 2 la recomendacion compara esas confianzas, la regla no cambia | ADR-007 |
| Bucket | S3 real en us-east-2, privado, IAM solo con Put/Get/ListBucket (sin Delete); claves solo en `.env` | tarea previa del prompt |
| PostgreSQL local | Lo arranca el usuario con `docker compose up -d db` | - |
| Decidir un folio con documentos `pendiente` o `procesando` | 409 `DOCUMENTO_EN_PROCESO` | pregunta 1 de PERSONA_3 |
| Corregir datos o confirmar la clasificacion de un documento en `error` | 409 `DOCUMENTO_CON_ERROR` (codigo nuevo: se anade a `codigos_error.md` en el mismo commit que lo use, etapa 2). Resolver sus alertas si se permite | pregunta 2 de PERSONA_3 |
| `EXP-001` | Al crear el folio, una por cada tipo requerido que falte (bloqueante, en `alertas_expediente`, `campo` = tipo). Se recalcula al procesar un documento o confirmar su clasificacion; cuenta el tipo confirmado, si no el detectado, si no el declarado. Si el revisor la marco `aplica=false`, se conserva | pregunta 3 de PERSONA_3 |
| `POST /folios` | 201 (ya implementado) | pregunta 4 de PERSONA_3 |
| Alertas informativas | `VAL-003` (campo tomado de la MRZ, PR #4) y `VAL-004` (campo opcional vacio, PR #6) ACEPTADAS; las emite PERSONA_2. `EXP-002` (documento de un tipo que el proceso no pide; informativa, en el documento) ACEPTADA (opcion A) y emitida por la plataforma (`expediente.recalcular_exp002`) | PR #4, PR #6, PR #9 |
| Privacidad de OpenRouter | `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` (PR #5 de PERSONA_2) cierra el riesgo de enviar documentos reales al proveedor gratuito | PR #5 |
| `SYS-004` | Descartado (opcion A): la ingesta rechaza con 415 `FORMATO_NO_PERMITIDO` si el contenido no coincide con la extension | PR #4 |
| ADR-008 | Aceptado (PR #7) y aplicado a los contratos (PR #8): `GET /auditoria` paginado (`PaginaAuditoria`) y `referencia_externa` en `ResumenFolio` | PR #7, PR #8 |

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
- [x] PR #3 de `feat/plataforma` a `main`: aprobado y fusionado el 2026-09-30.
- [x] Cuando el modulo `configuracion` de PERSONA_2 llegue a `main`: `configuracion.cargar()` en el
      lifespan de `main.py` y sustituir `ingesta/tipos.py` por `configuracion.servicio.obtener()/listar()`
      (etapa 2, paso 0; `GET /tipos-documentales` devuelve el mismo JSON).
- [ ] Entregar las claves AWS a PERSONA_3 por canal seguro (las necesita para los e2e).
- [ ] Decidir con el equipo la maquina de Ollama (sin GPU de momento) y el resto de `propuesta/base-etapa0`.

### ADR-008 (aceptado en el PR #7, aplicado a los contratos en el PR #8)
- [x] `expediente.listar_folios` rellena `ResumenFolio.referencia_externa` desde `folios.referencia_externa`
      (`null` si el folio se creo sin ella), con su test (93ac61b).
- [x] `api/README.md`: quitada la nota de desviacion de `GET /auditoria`; la paginacion ya es el contrato (93ac61b).

### Etapa 2 (dias 6-8), cuando PERSONA_2 entregue `procesar_documento`
- [x] E2.1: `ingesta/procesamiento.py` con la interfaz acordada del motor (hoy `motor_stub.py`); cada
      alerta del motor se guarda en `alertas` con `version_resultado` (migracion 0003). Acordado con PERSONA_2.
- [ ] Cambiar el import de `motor_stub` por `orquestador.servicio.procesar_documento` cuando llegue a `main`.
- [x] E2.3: `expediente.recalcular_exp001` al procesar cada documento (98196ea) y al confirmar la
      clasificacion (a1ec2c5).
- [x] E2.4: comparaciones entre documentos (`validacion/comparaciones.py` y `servicio.py`) y `CMP-001`
      critica en `alertas_expediente`, sin valores en el mensaje (3ded622).
- [x] E2.5: recomendacion global al vuelo (`expediente/recomendacion.py`); nunca `rechazar` (1162822).
- [x] E2.6a: resolver alertas de documento y de expediente (d582fcc).
- [x] E2.6b: migracion 0004 (`correcciones.version_resultado`), corregir datos (ADR-006 2.4) y confirmar
      clasificacion con reproceso (ADR-006 2.5); codigo nuevo `DOCUMENTO_CON_ERROR` (ea08277, cd41b1e, a1ec2c5).
- [x] E2.6c: decision del folio y cierre (ADR-006 2.2 y G), con UPDATE condicional contra decisiones
      simultaneas (commit "feat(api): decision del folio y cierre").
- [ ] Pull Request de `feat/plataforma` a `main` al cerrar la etapa 2.

### Etapa 3
Como en el prompt: resumen `.md`, webhooks HMAC, enmascaramiento en logs y "mostrar" auditado.
- [x] Webhooks firmados con HMAC-SHA256 y 3 intentos (`core/webhooks.py`, rama `feat/plataforma-etapa3`):
      `documento.completado`, `documento.error` y `folio.estado_cambiado`. `datos` enmascarado y
      `X-Entrega-Id` (ver abajo).
- [x] Resumen `.md` del expediente (rama `feat/plataforma-etapa3`): `expediente/resumen.py` y plantilla Jinja,
      con los datos extraidos (decision del usuario), regenerado tras cada cambio en S3 y `GET
      /folios/{folio}/resumen.md`. Decision: `ruta_resumen_md` se deriva del folio, sin migracion; un folio
      anterior a esta funcion, o con un fallo de S3 al crearlo, muestra el boton y da 404
      `RESUMEN_NO_DISPONIBLE` hasta el siguiente cambio. Enmascarado (ver abajo).
- [x] Enmascaramiento ADR-010 A2-A6 (PR A, rama `feat/plataforma`): `core/enmascaramiento.py` (mascara unica),
      respuestas de la API enmascaradas para todos los roles, webhook y `resumen.md` con la misma mascara,
      `POST /documentos/{id}/revelar` con `dato_revelado`, filtro de logs (`core/logs.py`) y `X-Entrega-Id` en
      los webhooks. Evidencia: ubicaciones conservadas (acordado con PERSONA_2). Mocks con la misma mascara.
- [ ] H17: boton "mostrar" en la UI (PR B).

## H1 (2026-10-02)
UI contra la API real, probada pantalla a pantalla con un navegador. Sin desviaciones del contrato.

- Entorno: backend en el equipo (`uvicorn`, `backend/.venv`) con el motor stub (H10), S3 real
  (us-east-2), PostgreSQL de `docker compose` y el frontend con `npm run dev` y `VITE_USAR_MOCKS=false`.
  Usuarios de prueba `h1.admin`, `h1.revisor` y `h1.integrador` (contrasenas aleatorias, fuera del repo).
- Comprobado: login; lista de folios; folio nuevo con `EXP-001`; carga con subida a S3; sondeo del
  estado; 415 `FORMATO_NO_PERMITIDO`; `DUP-001`; alerta marcada como falso positivo; confirmar otro
  tipo con reproceso; correccion de datos; decision y folio cerrado; auditoria; roles integrador y admin
  en la UI y en la API; CORS desde `http://localhost:5173`.
- Corregido (commit "fix(h1): ..."):
  1. `motor_stub`: con `tipo_confirmado`, `tipo_documental_detectado` y `confianza_clasificacion` a
     null (ADR-009), como el motor real. Manda el confirmado (tipo efectivo) y cuenta 1.0 (D2).
  2. Frontend: tras "Cerrar sesion" no se guarda la ruta de vuelta; el siguiente usuario entra en
     `/folios` (antes, un integrador caia en "Sin permiso" en la `/auditoria` del admin anterior). Tras
     una sesion caducada (401) la vuelta se mantiene.
  3. Frontend: el mensaje del 415 de la API cubre el formato y el contenido ("El archivo no es valido:
     su formato o su contenido no corresponde a los formatos permitidos."). La validacion de la
     extension en la pantalla de carga conserva su propio mensaje.
- Anotado, sin cambio:
  - Los folios antiguos `ONB-2026-000001` y `000002` de la BD de desarrollo no tienen `EXP-001`: son
    anteriores a E2.3. Solo afecta a datos de dev.
  - Con el stub, un documento con campos vacios recomienda `aprobar`, porque el stub no emite
    `VAL-001`. La demo no se hace con el stub.
  - Visor del original: comprobado en Chrome por PERSONA_1. El navegador integrado no muestra PDF; S3
    responde 200 application/pdf, sin Content-Disposition.

## Tareas heredadas de PERSONA_3 (traspaso del 2026-10-01; reparto ACEPTADO en el PR #13)
Detalle en `PERSONA_1_plataforma.md` (misma seccion) y `docs/equipo/PERSONA_3_estado.md`. Rama:
`feat/plataforma`. El punto "Entregar las claves AWS a PERSONA_3" de arriba ya no hace falta.

### Etapa 2 (sin esperar al motor)
- [x] H1: UI contra la API real con el stub; issue por cada desviacion del contrato. Ver "H1 (2026-10-02)".
- [x] H2: test de rutas de `app.openapi()` frente a `endpoints.md` (`tests/test_openapi_contrato.py`).
- [x] H6: humo con stub y e2e con el motor real HECHOS (hito del dia 8, 2026-10-05). Proyecto aparte `playwright.real.config.ts`
      (`npm run test:e2e:real`, carpeta `frontend/e2e-real/`), contra el backend y Vite locales.
- [ ] H7: borrador del ADR-010 de la etapa 3 (enmascaramiento, edicion de procesos, `/antecedentes`)
      el dia 7; reservar antes el numero en el chat del equipo.
- Prioridad acordada en el PR #13: H1 y H2 primero; H7 para el dia 7.

### Etapa 2 (con el motor de PERSONA_2)
- [ ] H3: mocks con `version_prompt` y evidencias reales (el PR #11 ya esta en `main`).
- [x] H4: "Tipo no reconocido" (ADR-009): UI, aviso sin datos y mensaje de `EXP-002` "Tipo de documento no
      reconocido" (rama `feat/plataforma-etapa3`).
- [ ] H5: etiqueta de la confianza segun la decision sobre ADR-007 (H10: PERSONA_2 ha decidido no
      sustituir el stub hasta entonces; PENDIENTE de tu confirmacion).
- [ ] H6 (completo): folios de `INDICE.md` con el motor real; 5 min por documento, 10 min por folio de 3.
- [x] H10: el motor real (`orquestador.servicio.procesar_documento`) en `ingesta/procesamiento.py`, con
      `MOTOR_ANALISIS` (`real` por defecto, `stub` para el humo sin Ollama). Forma de `tiempos` y `tokens`
      revisada y legible en la auditoria de la UI (rama `feat/plataforma-motor`).
- [x] D3: al corregir datos se vuelven a evaluar las reglas del documento (VAL-001/002/004 y REG-*, VAL-003 del
      campo corregido; falsos positivos conservados; rollback y 500 si falla), rama `feat/plataforma-motor`.
- [ ] La nota del `anio` `"0999"` (del PR #9).
- [x] Reanudar al arrancar los analisis interrumpidos por un reinicio (`ingesta.servicio.reanudar_pendientes`,
      `REANUDAR_ANALISIS_AL_ARRANCAR`, por defecto true), rama `fix/reanudar-analisis`. Un solo proceso uvicorn.

### Etapa 3
- [x] H8: pantalla de procesos en solo lectura (`/procesos`, solo admin; webhook solo con el host).
- [ ] H16: router y pantalla de antecedentes (tras H7 y `buscar_antecedentes` de PERSONA_2).
- [ ] H17: boton "mostrar" en la UI (PR B). La API ya enmascara y tiene `POST /revelar` (PR A).

### Etapa 4
- [ ] H19: guion de la demo, ensayo y `docker compose up` desde cero.
- [ ] `frontend/README.md`: Node >= 22.22 y responsable.
- [ ] `docs/arquitectura_solucion.md` (en `main` desde el PR #12): el reparto nuevo, en un PR pequeno
      cuando se fusione el #13 (comprometido en su revision).

## Hito del dia 8 (2026-10-05): e2e con el motor real
Lo ejecuto PERSONA_2 desde `main` con Ollama y S3 reales.
- Folio con los 3 documentos sanos: completado y "aprobar" en unos 3,5 min (~70 s por documento). El
  primero no recarga el modelo gracias a `python -m app.modulos.motor_ia.calentar` (`num_ctx` igual que
  el motor, PR #31).
- D3 con el motor real: al corregir la fecha de vencimiento a una pasada aparecen `REG-vigencia_documento`
  y `REG-vigencia_proxima` y el documento pasa a `revision_manual`; al restaurarla vuelve a `aprobar`.
- Casos de error: `vencido` da `REG-vigencia`; `domicilio_distinto` da `CMP-001`.
- Los 9 documentos de `fixtures/generados/INDICE.md` dan el resultado esperado.
- Pendiente para la demo: el enmascaramiento (PR #32) aun no estaba en `main` durante el hito; repetir la
  prueba con el #32 fusionado y anotar los tiempos por documento para el guion (H19).
