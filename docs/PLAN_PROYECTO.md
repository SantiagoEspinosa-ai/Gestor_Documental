# Plan del proyecto - Gestor Documental Inteligente con IA

Fecha de acuerdo: 2026-09-29. Duracion: 2 semanas (14 dias). Equipo: PERSONA_1, PERSONA_2, PERSONA_3.
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
| Modelo comercial | **OpenRouter (ADR-003, aceptado 2026-09-30)** como respaldo de Ollama en todas las tareas; `data_collection: deny` + retencion cero; modelos `:free` solo con fixtures ficticios | Sin API key de Anthropic; una clave da acceso a varios modelos; los datos se procesan con Ollama |
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
| Ramas y commits | Trunk-based, ramas cortas por modulo, conventional commits | |
| Herramienta | Todo el codigo se escribe con Claude Code; cada persona arranca con su prompt de `docs/equipo/` | |
| Arquitectura | Monolito modular con puertos y adaptadores (ADR-005, `docs/arquitectura.md`); reglas de dependencia solo documentadas | Paralelismo por modulos y proveedores intercambiables sin sobrecarga para un MVP |

Extras de la presentacion, por prioridad (solo en etapa 3 si el hito de la etapa 2 esta verde):
1. Enmascaramiento de datos sensibles en logs/UI + guardado de correcciones como retroalimentacion.
2. Calidad/legibilidad, paginas recortadas y alteraciones visibles (via modelo de vision).
3. Pantalla de administracion de tipos documentales.
4. Tipos factura y comprobante de gasto (dos YAML + fixtures; demuestra extensibilidad).

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
| PERSONA_3 | Interfaz y calidad | frontend, fixtures, tests e2e, rag (memoria de folios) | `docs/equipo/PERSONA_3_interfaz_calidad.md` |

Refuerzos: PERSONA_1 apoya a PERSONA_2 en validacion en la etapa 2; PERSONA_3 apoya en RAG en la etapa 3.
Regla de paralelismo: nadie toca modulos ajenos. Se usa stub, CLI o mock hasta la integracion.

## 4. Etapas

### Etapa 0 - Dia 1 (los tres juntos) [HECHA: esqueleto en el repo]
Repo, docker compose, `.env.example`, los tres contratos, YAML de tipos/modelos/procesos, prompts v1,
ADR-001/002/003/005, `docs/arquitectura.md`, `CLAUDE.md`, prompts por persona. Queda: `git init`, revisar contratos entre los tres,
abrir ramas `feat/ingesta`, `feat/motor-ia`, `feat/frontend`, decidir maquina con GPU para Ollama.
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
| PERSONA_1 | PERSONA_2 | PERSONA_3 |
|---|---|---|
| Conectar ingesta -> `procesar_documento` real; guardar resultados | `procesar_documento(documento_id)` completo; reintentos y respaldo | Sustituir msw por API real (misma URL base, mismo contrato) |
| Comparaciones entre documentos del folio + alertas `CMP-xxx` | Motor de reglas deterministas (`patron`, vigencias, obligatorios, confianza minima) con tests, con apoyo de PERSONA_1 | Pantalla de revision con datos reales: confianza, alertas por severidad, comparaciones |
| Recomendacion global (bloqueante impide aprobar) | Evidencia y confianza por campo desde el modelo | Acciones del revisor: corregir, confirmar clasificacion, resolver alerta, decision |
| Endpoints del revisor + auditoria | Ajuste de prompts con los 4 fixtures | Pruebas e2e reales sobre docker compose |
| **Hito dia 8**: subir 3 documentos por la web -> clasificados, extraidos, validados, con alertas y recomendacion en la UI | | |

### Etapa 3 - Dias 9-12: expediente, RAG, salida y extras
| PERSONA_1 | PERSONA_2 | PERSONA_3 |
|---|---|---|
| Resumen `.md` con Jinja, regeneracion, S3, `GET /resumen.md` | Base de conocimiento: `docs/conocimiento/*.md` -> chunks -> embeddings pgvector -> `contexto_rag` | Memoria de folios: indexar cada `.md`, `buscar_antecedentes` con permisos y caducidad, endpoint y pantalla |
| Webhooks HMAC, reintentos, eventos del contrato | Extra 2: `extraccion_v2.md` con observaciones visuales -> alertas `VIS-xxx` | Extra 1 (UI): enmascaramiento parcial con "mostrar" auditado |
| Extra 1 (backend): enmascaramiento en logs y prompts; tabla `correcciones` | Proveedor OpenRouter como respaldo (ADR-003) | Pantalla de configuracion de procesos |
| Auditoria completa y `GET /auditoria` | | Extra 3 y 4 solo si el dia 11 todo sigue verde |

### Etapa 4 - Dias 13-14: cierre
Dia 13: congelacion de funcionalidad; bugs; tests que faltan; README por modulo; `docker compose up`
desde cero en maquina limpia. Dia 14: guion de demo (recibir -> procesar -> validar -> consolidar ->
exponer por API y webhook + antecedentes), ADRs pendientes, revision de que no hay secretos ni datos reales.

## 5. Riesgos y mitigaciones
1. Ollama sin GPU hace la demo lenta -> decidir la maquina el dia 1.
2. Tesseract falla con fotos de movil -> el enrutador envia imagenes al modelo de vision, no solo a OCR.
3. Cambios al Contrato 1 a mitad de proyecto rompen a los tres -> ADR de una linea + aviso.
4. Auth completa consume 1,5-2 dias de PERSONA_1 -> si se atasca, API key temporal y JWT al final de la etapa 1.
5. OpenRouter sin saldo o caido -> todo funciona con Ollama; es solo respaldo.

## 6. Definicion de hecho
Funciona de extremo a extremo, tiene test, esta documentado (README del modulo) y no expone secretos
ni datos reales.

## 7. Pendientes [A ACORDAR]
- ~~Proveedor comercial de IA (ADR-003).~~ Cerrado 2026-09-30: OpenRouter como respaldo de Ollama.
  Pendiente solo: quien abre la cuenta de OpenRouter y carga el saldo.
- Maquina para Ollama.
- ~~Quien administra la cuenta AWS y crea el bucket + usuario IAM con permisos minimos.~~
  Cerrado 2026-09-30: PERSONA_1 (duena de S3 en `core`). Si la cuenta AWS es de la empresa,
  PERSONA_1 solicita el acceso y configura bucket e IAM.
