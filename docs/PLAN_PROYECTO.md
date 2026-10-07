# Plan del proyecto - Gestor Documental Inteligente con IA

Fecha de acuerdo: 2026-09-29. Duracion: 2 semanas (14 dias). Equipo: PERSONA_1, PERSONA_2, PERSONA_3
(desde el 2026-10-01, PERSONA_1 y PERSONA_2: ver seccion 8).
Este documento es la fuente de verdad del plan. Si algo cambia, se actualiza aqui y se avisa al equipo.
Para anadirlo al proyecto de Claude: pegar este fichero en las instrucciones del proyecto.

## 1. Decisiones cerradas (grill-me del 2026-09-29)

| Area | Decision | Motivo |
|---|---|---|
| Alcance | MVP completo obligatorio; extras de la presentacion solo cuando el flujo e2e funcione | Riesgo de llegar al dia 14 sin nada que funcione |
| Backend | Python 3.12 + FastAPI | Ecosistema IA/OCR |
| Frontend | React 18 + Vite (SPA) | Mismo contrato que los integradores externos |
| BD y RAG | PostgreSQL 16 + pgvector | Una sola BD para datos y vectores |
| Originales | Amazon S3 real (boto3), bucket privado + usuario IAM con permisos minimos, creado y administrado por PERSONA_1. Sin MinIO. Tests con `moto` | Requisito "S3 o equivalente"; decidido el 2026-09-30 |
| OCR | Tesseract tras interfaz `OCRProvider` | Gratis; cambiar a Textract = una clase |
| Modelo local | Ollama (`llama3.2-vision:11b` o `qwen2.5vl:7b`) | Privacidad, sin coste |
| Modelo comercial | **OpenRouter gratuito (ADR-003, aceptado 2026-09-30)**: solo modelos `:free`, sin saldo; respaldo de Ollama en todas las tareas; solo fixtures ficticios. Cuenta y clave: PERSONA_2, etapa 1 dia 2 | Sin API key de Anthropic y sin presupuesto; los datos se procesan con Ollama |
| Tipos documentales | Credencial de elector, pasaporte, comprobante de domicilio (caso onboarding) | Permite comparar nombre, fecha de nacimiento y domicilio entre documentos |
| Configuracion de tipos | Ficheros YAML en `config/tipos/` cargados al arrancar | Mas rapido; pantalla de admin es extra 3 |
| Procesamiento | `BackgroundTasks` de FastAPI; estados `pendiente -> procesando -> completado | error` | Sin Redis ni workers en MVP |
| Folio | `{PREFIJO}-{AAAA}-{NNNNNN}`, prefijo por proceso (`ONB-2026-000001`) | Separacion logica por proceso |
| JSON | snake_case en espanol, identico a la diapositiva 7 | Coincide con la presentacion |
| Auth | JWT con usuarios en BD; roles admin / revisor / integrador | Requisito de seguridad |
| Validaciones MVP | tipo declarado vs detectado, campos obligatorios, fechas/vigencia, consistencia entre documentos, duplicados por hash, confianza minima | Testeables de forma determinista |
| RAG | Base de conocimiento (.md indexados) + memoria de folios anteriores con `permitir_antecedentes` y caducidad | Diapositiva 9 |
| Salida | API REST + webhook por proceso firmado HMAC-SHA256 | Diapositiva 3 |
| Fixtures | Generados por script (Pillow/PyMuPDF) + fotos de especimenes de muestra impresos | Solo datos ficticios |
| Resumen .md | Plantilla Jinja, regenerada en cada cambio, guardada en S3 y reindexada | Determinista y testeable |
| Ramas y commits | Una rama por persona: `feat/plataforma` (PERSONA_1), `feat/motor-ia` (PERSONA_2), `feat/interfaz` (PERSONA_3). Cada uno solo trabaja en la suya; integracion a `main` por Pull Request al final de cada etapa. Conventional commits | Trabajo en paralelo sin pisarse; `main` siempre estable |
| Herramienta | Todo el codigo se escribe con Claude Code; cada persona arranca con su prompt de `docs/equipo/` | |
| Arquitectura | Monolito modular con puertos y adaptadores (ADR-005, `docs/arquitectura.md`); reglas de dependencia solo documentadas | Paralelismo por modulos y proveedores intercambiables sin sobrecarga para un MVP |
| Contratos 1 y 2 ampliados | ADR-004 y ADR-006 aceptados el 2026-09-30: lista de folios, alertas con `id`, estado de revision y regla de bloqueo, correcciones, folio cerrado, enums; catalogos `docs/contratos/codigos_alertas.md` y `codigos_error.md` | La UI y la API usan el mismo contrato sin campos inventados |
| Equipo y reparto (2026-10-01) | PERSONA_3 pasa a otro proyecto, sin persona nueva. Su linea se reparte: frontend, e2e, pantallas y demo a PERSONA_1; fixtures y `modulos/rag` a PERSONA_2. Reparto y recortes: ACEPTADOS por PERSONA_1 y PERSONA_2 en el PR del traspaso (#13, 2026-10-02; seccion 8) | Traspaso en `docs/equipo/PERSONA_3_estado.md` |
| Revision del traspaso (2026-10-02) | Reparto H1-H19 sin cambios; `rag/memoria.py` (H14) para PERSONA_2; recortes R1-R9 ACEPTADOS; el ADR de la etapa 3 sera el ADR-010 (el 009 es del PR #14). H10 (no sustituir el stub hasta ADR-007): decidido por PERSONA_2, pendiente de que PERSONA_1 lo confirme | PR #13 |
| Recomendacion del documento (2026-10-02) | El motor tampoco recomienda `rechazar` por documento, igual que la global. La aplica PERSONA_2 en la etapa 2 con su propio PR, incluido el ajuste de `codigos_alertas.md` si hace falta | Propuesta de PERSONA_2 (PR #15), aceptada por PERSONA_1 (PR #13) |

Extras de la presentacion, por prioridad (solo en etapa 3 si el hito de la etapa 2 esta verde):
1. Enmascaramiento de datos sensibles en logs/UI + guardado de correcciones como retroalimentacion.
2. Calidad/legibilidad, paginas recortadas y alteraciones visibles (via modelo de vision).
   ACEPTADO (2026-10-02): solo si el dia 11 esta todo en verde (seccion 8, R4).
3. Pantalla de administracion de tipos documentales. ACEPTADO (2026-10-02): fuera (seccion 8, R2).
4. Tipos factura y comprobante de gasto (dos YAML + fixtures; demuestra extensibilidad).
   ACEPTADO (2026-10-02): fuera (seccion 8, R1).

Fuera de alcance salvo peticion expresa: conectores a terceros, aprendizaje automatico con correcciones, multi-tenant completo.

## 2. Contratos congelados (cambian solo con ADR + aviso)
1. `backend/app/schemas/resultado.py` - JSON de resultado por documento y expediente.
2. `docs/contratos/endpoints.md` - API REST, webhook, estados.
3. `backend/app/modulos/motor_ia/interfaces.py` - orquestador, `ProveedorLLM`, `Enrutador`.

## 3. Reparto de modulos

| Persona | Linea | Modulos | Prompt de arranque |
|---|---|---|---|
| PERSONA_1 | Plataforma | ingesta, core (BD, auth, S3, auditoria, webhooks), api, expediente | `docs/equipo/PERSONA_1_plataforma.md` |
| PERSONA_2 | Motor IA (modulo mas pesado) | configuracion, orquestador, motor_ia, validacion (reglas) | `docs/equipo/PERSONA_2_motor_ia.md` |
| PERSONA_3 | Interfaz y calidad (repartida el 2026-10-01) | frontend, fixtures, tests e2e, rag (memoria de folios) | `docs/equipo/PERSONA_3_interfaz_calidad.md` (solo como especificacion original) |

Refuerzos: PERSONA_1 apoya a PERSONA_2 en validacion en la etapa 2; PERSONA_3 apoya en RAG en la etapa 3.
Regla de paralelismo: nadie toca modulos ajenos. Se usa stub, CLI o mock hasta la integracion.

Reparto de la linea de PERSONA_3 desde el 2026-10-01 (ACEPTADO en el PR #13; tabla completa con
dependencias en `docs/equipo/PERSONA_3_estado.md`):

| Persona | Hereda | Rama | Donde estan sus tareas |
|---|---|---|---|
| PERSONA_1 | frontend (paso a la API real, comparacion con `openapi.json`, mocks, pantallas de antecedentes y procesos, enmascaramiento en la UI), tests e2e, ADR-010 de la etapa 3 y demo | `feat/plataforma` | `PERSONA_1_plataforma.md` y `PERSONA_1_estado.md`, "Tareas heredadas de PERSONA_3" |
| PERSONA_2 | fixtures (generador, verificador OCR, especimenes, formato de `INDICE.md`), `modulos/rag` completo (memoria, embeddings y conocimiento), ADR de `desconocido` y decision de ADR-007 antes de sustituir el stub | `feat/motor-ia` | `PERSONA_2_motor_ia.md`, "Tareas heredadas de PERSONA_3" |

`feat/interfaz` queda sin uso: todo su contenido esta en `main` (PR #10). El refuerzo de PERSONA_3 en
RAG pasa a ser trabajo propio de PERSONA_2.

## 4. Etapas

### Etapa 0 - Dia 1 (los tres juntos) [HECHA: esqueleto en el repo]
Repo, docker compose, `.env.example`, los tres contratos, YAML de tipos/modelos/procesos, prompts v1,
ADR-001/002/003/005, `docs/arquitectura.md`, `CLAUDE.md`, prompts por persona. Queda: `git init`, revisar contratos entre los tres,
ramas `feat/plataforma`, `feat/motor-ia`, `feat/interfaz` creadas (2026-09-30), decidir maquina con GPU para Ollama.
PERSONA_1: crear el bucket S3 real y el usuario IAM del proyecto y entregar las claves a quien las
necesite por canal seguro (nunca por el repo ni por chats con IA).

### Etapa 1 - Dias 2-5: cimientos en paralelo
| PERSONA_1 | PERSONA_2 | PERSONA_3 |
|---|---|---|
| Settings, BD (SQLAlchemy + Alembic), modelos y tablas | Cargador y validacion de YAML de tipos | `generar_fixtures.py`: 3 tipos x 3 modalidades, casos sano / domicilio_distinto / vencido / duplicado + `INDICE.md` |
| Auth JWT, roles, `crear_usuario.py` | Deteccion de modalidad (pdf_digital / pdf_escaneado / imagen) | Fotos de especimenes de muestra |
| `POST /folios` con secuencia atomica por proceso y anio | `OCRProvider` Tesseract + extraccion con PyMuPDF, orden de paginas | Vite + React + router + cliente HTTP con JWT |
| Cliente S3, ingesta (hash, duplicados, S3, BD, BackgroundTask con stub) | `OllamaProvider`, `prompts.py`, enrutador desde `modelos.yaml` | Mocks msw de TODOS los endpoints del Contrato 2 |
| `GET /documentos/{id}`, `GET /folios/{folio}` | `servicio.analizar` + CLI con archivo local | Pantallas: login, folios, carga, expediente/revision |
| Tests: folios, hash, auth, ingesta con S3 simulado con `moto` | Tests: modalidad, parseo de respuestas guardadas, enrutador | Playwright con mocks, Vitest |
| **Entregable**: archivo subido visible en el bucket S3 real y en BD en `pendiente` | **Entregable**: CLI devuelve `ResultadoDocumento` valido con Ollama | **Entregable**: UI navegable con mocks + fixtures en el repo |

### Etapa 2 - Dias 6-8: integracion de extremo a extremo
Desde el 2026-10-01 la columna de PERSONA_3 se reparte (ACEPTADO en el PR #13): cada celda dice quien la hace y
el id de la tarea en `docs/equipo/PERSONA_3_estado.md`.

| PERSONA_1 | PERSONA_2 | Linea de PERSONA_3 (repartida) |
|---|---|---|
| Conectar ingesta -> `procesar_documento` real; guardar resultados | `procesar_documento(documento_id)` completo; reintentos y respaldo | PERSONA_1 (H1, H2): sustituir msw por API real (misma URL base, mismo contrato) y comparar con `openapi.json` |
| Comparaciones entre documentos del folio + alertas `CMP-xxx` | Motor de reglas deterministas (`patron`, vigencias, obligatorios, confianza minima) con tests, con apoyo de PERSONA_1 | PERSONA_1 (H3-H5): pantalla de revision con datos reales: confianza, alertas por severidad, comparaciones, `desconocido` |
| Recomendacion global (bloqueante impide aprobar) | Evidencia y confianza por campo desde el modelo | PERSONA_1: acciones del revisor (hechas sobre mocks en la etapa 1), probadas contra la API |
| Endpoints del revisor + auditoria | Ajuste de prompts con los 4 fixtures | PERSONA_1 (H6): pruebas e2e reales sobre docker compose. PERSONA_2 (H9-H13): ADR de `desconocido`, ADR-007 antes del stub, formato de `INDICE.md`, tiempos maximos y fixtures |
| **Hito dia 8**: subir 3 documentos por la web -> clasificados, extraidos, validados, con alertas y recomendacion en la UI | | |

### Etapa 3 - Dias 9-12: expediente, RAG, salida y extras
| PERSONA_1 | PERSONA_2 | Linea de PERSONA_3 (repartida) |
|---|---|---|
| Resumen `.md` con Jinja, regeneracion, S3, `GET /resumen.md` | Base de conocimiento: `docs/conocimiento/*.md` -> chunks -> embeddings pgvector -> `contexto_rag` (R10 ACEPTADO: fuera del MVP; el RAG del MVP es la memoria de folios, H14) | PERSONA_2 (H14): memoria de folios, indexar cada `.md`, `rag/embeddings.py`, `buscar_antecedentes` con permisos y caducidad. PERSONA_1 (H16): endpoint y pantalla |
| Webhooks HMAC, reintentos, eventos del contrato | Extra 2: `extraccion_v2.md` con observaciones visuales -> alertas `VIS-xxx` (R4 ACEPTADO: solo si el dia 11 esta en verde) | PERSONA_1 (H7, H17): ADR-010 de la etapa 3 y extra 1 (UI): enmascaramiento parcial con "mostrar" auditado. PERSONA_2 (H15): `sensible: true` |
| Extra 1 (backend): enmascaramiento en logs y prompts; tabla `correcciones` | Proveedor OpenRouter como respaldo (ADR-003) (R6 ACEPTADO: al final y opcional en la demo) | PERSONA_1 (H8): pantalla de configuracion de procesos en solo lectura (R3 ACEPTADO) |
| Auditoria completa y `GET /auditoria` | | Extra 3 y 4: fuera (R1 y R2 ACEPTADOS) |

### Etapa 4 - Dias 13-14: cierre
Dia 13: congelacion de funcionalidad; bugs; tests que faltan; README por modulo; `docker compose up`
desde cero en maquina limpia. Dia 14: guion de demo (recibir -> procesar -> validar -> consolidar ->
exponer por API y webhook + antecedentes), ADRs pendientes, revision de que no hay secretos ni datos reales.
Con dos personas (ACEPTADO en el PR #13): PERSONA_1 lleva el guion, el ensayo y el `docker compose up` desde cero
(H19) y pone al dia `docs/arquitectura_solucion.md`; PERSONA_2 lleva la maquina de Ollama, los
tiempos y los README de fixtures y `rag`. Cada una revisa los README de la otra.

## 5. Riesgos y mitigaciones
1. Ollama sin GPU hace la demo lenta -> decidir la maquina el dia 1.
2. Tesseract falla con fotos de movil -> el enrutador envia imagenes al modelo de vision, no solo a OCR.
3. Cambios al Contrato 1 a mitad de proyecto rompen a los tres -> ADR de una linea + aviso.
4. Auth completa consume 1,5-2 dias de PERSONA_1 -> si se atasca, API key temporal y JWT al final de la etapa 1.
5. OpenRouter gratuito con limite diario agotado o caido -> todo funciona con Ollama; es solo respaldo.
6. Equipo de dos desde el dia 3 (2026-10-01) -> recortes de la seccion 8, `procesar_documento` como
   ruta critica de la etapa 2 y revision cruzada de todos los PR.

## 6. Definicion de hecho
Funciona de extremo a extremo, tiene test, esta documentado (README del modulo) y no expone secretos
ni datos reales.

## 7. Pendientes [A ACORDAR]
- ~~Proveedor comercial de IA (ADR-003).~~ Cerrado 2026-09-30: OpenRouter como respaldo de Ollama.
  Solo modelos gratuitos, sin saldo. Cuenta y API key: PERSONA_2, etapa 1 dia 2.
- Maquina para Ollama.
- ~~Quien administra la cuenta AWS y crea el bucket + usuario IAM con permisos minimos.~~
  Cerrado 2026-09-30: PERSONA_1 (duena de S3 en `core`). Si la cuenta AWS es de la empresa,
  PERSONA_1 solicita el acceso y configura bucket e IAM.

## 8. Traspaso de PERSONA_3, recortes y PR (2026-10-01, revisado el 2026-10-02)
PERSONA_3 pasa a otro proyecto; no entra nadie. Estado, acuerdos, reparto con dependencias y riesgos:
`docs/equipo/PERSONA_3_estado.md`. El reparto y los recortes de esta seccion estan ACEPTADOS por
PERSONA_1 y PERSONA_2 en el PR del traspaso (#13). Queda pendiente que PERSONA_1 confirme H10.

### Es realista con dos personas
- Punto de partida (dia 3): la etapa 1 de las tres lineas esta hecha (PR #3 y #10 en `main`; el #11
  aprobado y sin fusionar) y la etapa 2 de la plataforma ya esta en `main` (PR #9). Quedan los dias
  4 a 14.
- Etapa 2: realista. La ruta critica es PERSONA_2 (`procesar_documento`, confianza de ADR-007 y
  reglas). PERSONA_1 tiene holgura los dias 4-6 para la API real en la UI, `openapi.json`, el humo de
  los e2e con el stub, la pantalla de procesos y el borrador del ADR de la etapa 3.
- Etapa 3: con todo lo previsto (resumen, webhooks, enmascaramiento en API y UI, antecedentes,
  memoria, conocimiento, OpenRouter y extras 2 a 4) no cabe en cuatro dias para dos. Con los recortes
  de abajo, si.
- Etapa 4: se mantienen los dos dias sin funcionalidad nueva.

### `rag/memoria.py` (H14)
DECIDIDO en el PR #13: la hace PERSONA_2, junto con el resto de `rag` (lo confirman PERSONA_1 y
PERSONA_2). PERSONA_2 da prioridad a la ruta critica de la etapa 2 y deja la memoria para la etapa 3.

### Recortes (decididos en el PR #13, 2026-10-02; el MVP no se recorta)
| Id | Recorte | Estado |
|---|---|---|
| R1 | Extra 4 (factura y comprobante de gasto): fuera | ACEPTADO |
| R2 | Extra 3 (administracion de tipos documentales): fuera; basta `GET /tipos-documentales` | ACEPTADO |
| R3 | Edicion de procesos: solo lectura (pantalla del admin con `GET /procesos`), como ya dicen ADR-006 (bloque 4) y el PR #12 | ACEPTADO |
| R4 | Extra 2 (`VIS-xxx`): solo si el dia 11 el hito y la memoria estan en verde | ACEPTADO |
| R5 | No repetir las 4 fotos de especimenes descartadas (H18 no se hace) | ACEPTADO |
| R6 | `openrouter.py` al final de la etapa 3 y opcional en la demo (con la barrera a `false` no se usa) | ACEPTADO |
| R7 | Antecedentes por `referencia_externa` del folio (opcion a de ADR-006), sin HMAC de la CURP | ACEPTADO |
| R8 | Enmascaramiento solo de CURP, numero de pasaporte y clave de elector; las correcciones del extra 1 ya se guardan (PR #9) | ACEPTADO |
| R9 | e2e reales: humo en cada cambio; los folios de `INDICE.md` solo antes de cada PR de etapa | ACEPTADO |
| R10 | Base de conocimiento con embeddings (`docs/conocimiento` -> embeddings -> `contexto_rag`): fuera del MVP (2026-10-07). Motivo medido: con `OLLAMA_MAX_LOADED_MODELS=1`, el modelo de embeddings expulsa a `gemma4:e2b` de la memoria y cada documento tardaria ~25 s mas (lo que tarda en volver a cargarse). **El requisito RAG del MVP lo cubre la memoria de folios** (H14: `rag.servicio.indexar_resumen` y `fragmento_resumen`) con los antecedentes (H16). Evolucion futura, sin cambiar la arquitectura: spec de PERSONA_2, seccion 16 | ACEPTADO (PERSONA_1 y PERSONA_2) |

### Efecto de los PR #11, #12, #14 y #15
- PR #11 (etapa 1 del motor, FUSIONADO el 2026-10-02): usa los fixtures de PERSONA_3 y convierte
  `INDICE.md` en un contrato de hecho (`test_fixtures_ocr.py`). Deja cuatro tareas que antes eran de
  PERSONA_3 o la necesitaban: el ADR de `desconocido`, la decision sobre ADR-007 antes de sustituir el
  stub, el formato de `INDICE.md` y los tiempos maximos para los e2e (H9 a H12). PERSONA_2 ya ha
  avanzado en ellas: ADR-009 en el PR #14; el stub no se sustituye hasta ADR-007; el test solo usa los
  casos conocidos; tiempos en la seccion 13 de su spec. Ya fusionado, PERSONA_1 integra
  `configuracion`.
- PR #12 (arquitectura de solucion con vistas C4, FUSIONADO el 2026-10-02) y PR #15 (sus ajustes,
  FUSIONADO): solo documentacion, no cambian contratos, ADR ni el plan. Dejan la edicion de procesos
  fuera del MVP (coincide con R3) y Textract como opcion futura con la barrera de privacidad, fuera de
  este plan. Su reparto queda desfasado con este traspaso: PERSONA_1 lo pone al dia en un PR pequeno
  cuando se fusione el #13.
- PR #14 (ADR-009, `desconocido`, ABIERTO): desbloquea H3 y H4.
- Orden de fusion: el #11 y el #12 ya estan en `main`; quedan el #13 (traspaso) y el #14.
