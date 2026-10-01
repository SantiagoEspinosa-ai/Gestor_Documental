# PERSONA_3 - Estado y traspaso (linea repartida)

Actualizado: 2026-10-01 (dia 3 del plan). PERSONA_3 pasa a otro proyecto y su linea (frontend,
fixtures, tests e2e y memoria de folios) se reparte entre PERSONA_1 y PERSONA_2, sin persona nueva.
La etapa 1 de la linea esta CERRADA y en `main` (PR #10). Este fichero dice que hay hecho, que se
acordo, en que punto estan los PR abiertos y quien hereda cada tarea. Las tareas de cada persona estan
tambien en su prompt (`PERSONA_1_plataforma.md` y `PERSONA_2_motor_ia.md`, seccion "Tareas heredadas
de PERSONA_3"). La especificacion original sigue en `PERSONA_3_interfaz_calidad.md`.

El reparto y los recortes de este fichero son una PROPUESTA hasta que PERSONA_1 y PERSONA_2 aprueben
el PR del traspaso.

## Como retomar en una maquina nueva
1. Requisitos: Git, Python 3.12, Node >= 22.22 (algunas dependencias del `package-lock.json` piden
   `^22.22.2`; el `^20.19 o >=22.12` de `frontend/README.md` se queda corto) y Docker Desktop.
   Tesseract no hace falta en local: el OCR se prueba en el contenedor del backend.
2. Rama: el frontend y los e2e siguen en `feat/plataforma` (PERSONA_1); fixtures y `modulos/rag`, en
   `feat/motor-ia` (PERSONA_2). `feat/interfaz` se conserva, pero ya no se usa (ver "En curso").
   ```
   git fetch
   git switch feat/plataforma        # o feat/motor-ia
   git merge origin/main
   ```
3. Python: un `.venv` en la raiz del repo. Usar siempre su `python.exe`, no el del PATH, que puede
   ser de otro proyecto.
   ```
   py -3.12 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```
4. Frontend: `cd frontend` y `npm ci` (instala exactamente el lock; `npm install` solo si cambias
   dependencias). Despues, `copy .env.example .env`: `VITE_USAR_MOCKS=true` para los mocks;
   `VITE_USAR_MOCKS=false` y `VITE_API_URL=http://localhost:8000` para la API real. Solo variables
   `VITE_*`: acaban en el navegador, nunca secretos.
5. `.env` de la raiz desde `.env.example` (`copy .env.example .env`), rellenado a mano. Nunca se sube
   ni se pega en un chat con IA. Variables:
   - `APP_ENV`, `SECRET_KEY`, `JWT_EXPIRA_MINUTOS`, `WEBHOOK_SECRET_HMAC`: valores propios en local.
   - `DATABASE_URL`, `CONFIG_DIR`, `PROMPTS_DIR`, `TAMANO_MAXIMO_ARCHIVO_MB`, `ZONA_HORARIA`,
     `URL_PREFIRMADA_SEGUNDOS`, `TESSERACT_LANG`: los de `.env.example` valen.
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`: los del bucket real
     (us-east-2, no el `us-east-1` del ejemplo). Las claves las da PERSONA_1 por canal seguro.
   - `OLLAMA_BASE_URL`, `OLLAMA_MODELO_VISION`, `OLLAMA_MODELO_TEXTO`, `MAX_PROCESAMIENTOS_SIMULTANEOS`:
     segun donde corra Ollama (tabla en `frontend/README.md`, "e2e reales").
   - `PROVEEDOR_COMERCIAL`, `PROVEEDOR_COMERCIAL_BASE_URL`, `PROVEEDOR_COMERCIAL_MODELO`,
     `PROVEEDOR_COMERCIAL_API_KEY`, `PERMITIR_PROVEEDORES_NO_PRIVADOS`: dejar la barrera en `false`.
     La clave de OpenRouter solo hace falta para probar el respaldo y la da PERSONA_2 por canal seguro.
6. Fixtures (no se suben; el script es la fuente de verdad). Con la fecha de los mocks:
   ```
   .venv\Scripts\python.exe scripts\generar_fixtures.py --hoy 2026-09-30
   ```
   Genera 42 ficheros e `INDICE.md` en `fixtures/generados/`. `test_generar_fixtures.py` compara los
   SHA-256 con `backend/tests/sha256_fixtures_existentes.txt` (PyMuPDF 1.28.2 y Pillow 12.3.0).
7. Arrancar con mocks: `cd frontend; npm run dev` -> http://localhost:5173. Usuarios ficticios del
   mock en `frontend/README.md` ("Mocks").
8. Arrancar con `docker compose` (API real):
   - `docker compose up -d db`, y despues `docker compose up backend frontend` (el backend aplica
     `alembic upgrade head` al arrancar; `frontend/.env` con `VITE_USAR_MOCKS=false`).
   - Usuarios de desarrollo con `scripts/crear_usuario.py`: ver `PERSONA_1_estado.md`, "Como
     retomar", punto 6.
   - Ollama en el equipo, arrancado con `OLLAMA_MAX_LOADED_MODELS=1`, con `qwen2.5vl:3b` y
     `gemma4:e2b` descargados. Antes de probar, `GET <OLLAMA_BASE_URL>/api/tags` debe listar los dos.
9. Comprobaciones:
   ```
   cd backend; ..\.venv\Scripts\python.exe -m pytest -q
   cd frontend; npm test; npx tsc -b; npm run lint; npm run build
   npx playwright install chromium; npm run test:e2e
   ```
   OCR de los fixtures (contenedor del backend, PowerShell, desde la raiz):
   ```
   docker compose run --rm --no-deps -v "${PWD}\fixtures:/fixtures" -v "${PWD}\scripts:/scripts:ro" `
       backend python /scripts/verificar_ocr_fixtures.py --control
   ```

## Como trabajar con Claude Code en esta linea
Prompt de inicio de sesion (pegarlo como primer mensaje, despues del prompt de tu persona):
```
Heredo tareas de PERSONA_3. Lee CLAUDE.md, docs/PLAN_PROYECTO.md, la seccion "Tareas heredadas de
PERSONA_3" de mi prompt de docs/equipo/, docs/equipo/PERSONA_3_estado.md y el README del modulo que
vayamos a tocar (frontend/README.md, fixtures/README.md o backend/app/modulos/rag/README.md).
Reglas: no hagas commit ni push hasta que todo este en verde y me hayas ensenado el diff; usa las
herramientas de edicion, no sed ni perl; las ramas de docs, en un worktree temporal fuera del repo;
no leas ningun .env; si hay otra sesion de Claude Code en paralelo, esa solo lee.
Hoy toca: <tarea de la tabla del reparto>.
```
Reglas que se fijaron en esta linea:
- Sin commit ni push hasta que tests, lint y build esten en verde y se haya revisado el diff completo.
  El push y los PR, solo cuando se piden.
- Ediciones con las herramientas de edicion de Claude Code (Edit/Write), no con `sed` ni `perl`: se
  ven en el diff y no rompen la codificacion.
- Ramas de documentacion (ADR, contratos, docs compartidos) en un worktree temporal fuera del repo
  (`git worktree add -b docs/<tema> <carpeta> origin/main`), y quitarlo al terminar
  (`git worktree remove`). Asi no se toca la rama de trabajo.
- Nunca leer ni mostrar `.env`; en ejemplos, `TU_CLAVE_AQUI`.
- Una sesion paralela (por ejemplo, para revisar un PR) es de solo lectura: ni cambia de rama ni
  edita ficheros.
- PR y comentarios de GitHub: sin `gh`, se leen por la API publica y los publica la persona. Los
  autores se nombran como PERSONA_n, nunca por su usuario.
- Antes de instalar algo nuevo, avisar. El numero de un ADR nuevo se reserva antes en el chat del
  equipo.

## Hecho en la etapa 1 (rama `feat/interfaz`, en `main` por el PR #10)
| Tarea | Que | Commits clave |
|---|---|---|
| 1 | `generar_fixtures.py`: 3 tipos x 3 modalidades, casos `sano`, `vencido`, `domicilio_distinto` y `duplicado`, `INDICE.md` con valores y alertas esperadas por folio de prueba; determinista con `--hoy` | 9d8a524, fb82440 |
| 1 | Niveles `dificil` y `extremo` del caso `sano` (12 ficheros) para decidir el paso a vision | 78a0369 |
| 1 | Hashes fijados con las versiones de PyMuPDF y Pillow; con otras, los tests de hashes se omiten | 27795a5 |
| 1 | `verificar_ocr_fixtures.py` (Tesseract en el contenedor, por nivel) | cdb3672 |
| 1 | Especimenes: 5 fotos de movil de los impresos, sin metadatos (`procesar_especimenes.py`) | 7160df4 |
| 1 | `generar_datos_mock.py` (datos de los mocks desde los fixtures) y `fixtures/README.md` | 84dde8e, d774815 |
| 2 | Vite + React 18 + router + cliente HTTP con JWT | ed860fa |
| 3 | Mocks msw de todos los endpoints del Contrato 2; build sin mocks | 6e1e9df, f734ca8, f809b79 |
| 3 | Mocks alineados con la API real (PR #3 y PR #9) | 1855855, 0ed30b8 |
| 4 | Login, layout y roles; folios y carga; expediente; acciones del revisor; resumen | 37166d3, 7ac4fb5, 16daa09, 56025ed, 6ae0677 |
| 4 | Sondeo progresivo (3-15 s, se para a los 10 min); auditoria del admin; `referencia_externa` (ADR-008) | 7856959, 128df5c, 257657f |
| 4 | Obligatorios no se vacian y `anio` entero; URL completa tras el login | eb10b30, 8f5e85e |
| 4 | Codigos oficiales tras el PR #9 (`DOCUMENTO_CON_ERROR`, `EXP-002`) | 7b85ac4, 299ab49 |
| 5 | Enmascaramiento en la UI: NO hecho; pasa al ADR de la etapa 3 (ADR-006, bloque 4) | - |
| 6 | Playwright sobre los mocks y Vitest | e42cd6c |
| ADR | ADR-006 y su aplicacion a los contratos; ADR-008 (PR #1, #2, #7 y #8); `VAL-004` (PR #6) | e41f0bc, fed33c6, 4d0f9f9 |

Tests al cerrar el PR #10 (2026-10-01, `0ed30b8` con `main` integrado):

| Suite | Resultado |
|---|---|
| pytest (backend completo) | 400 pasan, 2 se omiten (requieren Postgres) |
| Vitest | 177 en 18 ficheros |
| Playwright sobre mocks | 10 en 6 ficheros, 3 ejecuciones seguidas sin fallos |
| lint (oxlint) y build | sin avisos; build sin rastro de mocks |
| pytest con el PR #11 fusionado (prueba en local) | 665 pasan, 7 se omiten (sin fixtures, sin Tesseract o sin Postgres) |

## Decisiones y acuerdos
| Tema | Acuerdo | Donde |
|---|---|---|
| ADR-004 | `referencia_externa` (identificador opaco, nunca el nombre) y `fecha_solicitud` en el expediente | ADR-004 |
| ADR-006 | Huecos del contrato para la UI: lista de folios, `Alerta.id`, catalogo de errores, resolver alertas, correcciones, reproceso, folio cerrado, enums. Bloque 4 (edicion de procesos, enmascaramiento, `/antecedentes`) aplazado al ADR de la etapa 3 | ADR-006 |
| ADR-007 | La confianza la calcula el codigo. La UI la titula "Confianza verificada" y no muestra `confianzas_modelo` | ADR-007, `utilidades/etiquetas.ts` |
| ADR-008 | `GET /auditoria` paginado (50, de 1 a 100) y `referencia_externa` en `ResumenFolio` | ADR-008 |
| Codigos informativos | `VAL-003` (campo de la MRZ) y `VAL-004` (opcional vacio) los emite el motor. `EXP-002` (tipo que el proceso no pide) la emite la plataforma, en `alertas_encontradas` del documento | `codigos_alertas.md` |
| Errores 409 | `DOCUMENTO_EN_PROCESO` al decidir con documentos en curso; `DOCUMENTO_CON_ERROR` al corregir o confirmar un documento en `error` (sus alertas si se pueden resolver) | `codigos_error.md` |
| `SYS-004` | Descartado: la ingesta da 415 `FORMATO_NO_PERMITIDO`. Sin `SYS-005` en los mocks mientras la barrera de ADR-003 este en `false` | PR #4 |
| Regla de bloqueo (2.2) | Una bloqueante con `aplica` distinto de `false` impide aprobar (409 `DECISION_BLOQUEADA`). Cuentan las alertas visibles: las del expediente y las de la version vigente de cada documento | `endpoints.md`, PR #9 |
| Tipo efectivo y tipo de extraccion | Efectivo (EXP-001, EXP-002, comparaciones, recomendacion): confirmado > detectado > declarado. Extraccion (PATCH de datos, reproceso): confirmado > declarado > detectado | ADR-006 2.5, PR #9 |
| Recalculos | `EXP-001`, `CMP-001` y `EXP-002` solo conservan el falso positivo (`aplica=false`) cuando la condicion desaparece | PR #9 |
| Recomendacion global | Nunca `rechazar` y no usa la del documento (esa la da el motor y no se recalcula) | `expediente/README.md` |
| PATCH de datos | `null` solo en opcionales; `anio` entero de 4 cifras o texto `"AAAA"`; fecha `AAAA-MM-DD` y `patron` | `api/README.md` |
| `modulos/rag` | ADR-006 ("Coordinacion") daba `memoria.py` y `embeddings.py` a PERSONA_3. Con el traspaso pasan a PERSONA_2 (PROPUESTA). Se mantienen las reglas: `servicio.py` es la unica API, el router lo hace PERSONA_1 en `api` y la migracion se encadena en la historia de Alembic de PERSONA_1 avisando antes | ADR-006, este fichero |
| Fixtures | `fixtures/generados/` e `INDICE.md` no se suben (`.gitignore`); se generan con `--hoy`. `--hoy 2026-09-30` es la fecha de los mocks y de los tests | `fixtures/README.md` |
| `INDICE.md` | Es un contrato de hecho: lo leen `test_fixtures_ocr.py` y `evaluar_fixtures.py` de PERSONA_2. No cambiar su formato sin avisar | PR #11 |
| Especimenes | Si se suben. Siempre sin metadatos (EXIF, GPS, XMP, ICC, MPO) y solo con el documento ficticio en el encuadre | `fixtures/especimenes/README.md` |
| ADR nuevos | El numero se reserva en el chat del equipo antes de abrir la rama | - |

## En curso (2026-10-01, comprobado por la API publica de GitHub y con git)
- **PR #10** (`feat/interfaz` -> `main`): FUSIONADO (merge `17098b2`), aprobado por PERSONA_1 y
  PERSONA_2. La etapa 1 de la linea esta en `main`. `feat/interfaz` se conserva en `0ed30b8`, sin
  ningun commit ni diferencia respecto a `main` (`git log origin/main..feat/interfaz` vacio y
  `git diff` vacio). No hay que recuperar nada de ella.
- **PR #11** (`feat/motor-ia` -> `main`, etapa 1 de PERSONA_2): aprobado por PERSONA_3 (revision) y
  por PERSONA_1 (comentario), sin conflictos, PENDIENTE DE FUSIONAR. De la revision de PERSONA_3:
  los puntos 1 (spec desfasada) y 2 (`desconocido`) conviene resolverlos antes de fusionar; del 3 al 8
  son menores. Los que tocaban a PERSONA_3 estan en el reparto (H9 a H12); el resto son de PERSONA_2
  (resumen en el anexo B). Despues de esa revision, PERSONA_2 subio `7c84720` y `96f7425` (head del
  PR): spec al dia, tiempo por documento (seccion 13), `test_fixtures_ocr.py` solo con los casos y el
  nivel conocidos, y la decision de no sustituir el stub hasta ADR-007 (670 tests pasan y 2 se saltan
  en el contenedor, segun la spec).
- **ADR-009** (`desconocido` en `tipo_documental_detectado`): PROPUESTO por PERSONA_2 en la rama
  `docs/adr-009-desconocido` (`4dc4906`), todavia sin PR. El ADR de la etapa 3 necesitara otro
  numero (reservarlo en el chat).
- **PR #12** (`feat/plataforma` -> `main`, PERSONA_1): `docs/arquitectura_solucion.md` con vistas C4.
  Solo documentacion; no cambia contratos ni ADR. PERSONA_2 pidio tres ajustes. Sale de
  `feat/plataforma`, asi que lo que PERSONA_1 suba a esa rama entra en ese PR hasta que se fusione.
- **Issues:** ninguno en GitHub. Del PR #9 quedan dos notas sin issue, ahora de PERSONA_1: la API
  acepta un `anio` `"0999"` y lo guarda como `999` (la UI nunca lo envia), y revisar la forma de
  `tiempos` y `tokens` en el `detalle` de `documento_procesado` cuando llegue el motor real.

## Reparto propuesto (PROPUESTA)
Criterio: PERSONA_1 tiene la etapa 2 de la plataforma ya fusionada (PR #9) y es duena de la API, las
claves AWS y la historia de migraciones, asi que hereda la UI, los e2e y la demo. PERSONA_2 va por la
ruta critica de la etapa 2 (`procesar_documento`, ADR-007 y reglas), pero es quien consume los
fixtures y quien hace la base de conocimiento: hereda los fixtures y toda la carpeta `modulos/rag`,
porque `memoria.py` comparte con `conocimiento.py` el troceado, los embeddings y pgvector.

| Id | Tarea | Persona | Etapa | Dependencias |
|---|---|---|---|---|
| H1 | Frontend contra la API real (`VITE_USAR_MOCKS=false`); cada desviacion del contrato, como issue | PERSONA_1 | 2 (ya, con el stub) | Ninguna; los campos del motor, tras `procesar_documento` |
| H2 | Comparar `endpoints.md` y `frontend/src/tipos/contrato.ts` con el `openapi.json` de FastAPI (test con `app.openapi()`: rutas, metodos y esquemas) | PERSONA_1 | 2 | Ninguna |
| H3 | Mocks con el motor real: `version_prompt` `extraccion_{tipo}@v3`, evidencias `pagina_1:seccion_*`, un documento `desconocido`, una fecha no normalizable y `fecha_analisis` con microsegundos; regenerar con `generar_datos_mock.py` | PERSONA_1 | 2 | PR #11 en `main`; H9 para `desconocido` |
| H4 | UI: `desconocido` como "Tipo no reconocido" y aviso, en vez de tabla vacia, si no hay ficha ni datos | PERSONA_1 | 2 | H9 |
| H5 | Etiqueta de la confianza: "Confianza verificada" solo si la calcula el codigo; si no, "Confianza". Con H10 decidido, se queda como esta salvo que se conecte el motor antes de ADR-007 | PERSONA_1 | 2 | H10 |
| H6 | e2e reales: proyecto de Playwright aparte, `workers: 1`. Humo ya con el stub; con el motor real, los folios de `INDICE.md` con fixtures normales (maximo medido, 73 s). Espera de 5 min por documento y `test.setTimeout` de 10 min por folio de 3; calentar Ollama antes. El peor caso de la spec (540 s por documento con OCR pobre) no entra en los e2e | PERSONA_1 | 2 (hito del dia 8) | `procesar_documento` real; H12 |
| H7 | ADR de la etapa 3: enmascaramiento en el backend con "mostrar" auditado, edicion de procesos y forma de `/antecedentes` (`referencia_persona`, respuesta si `permitir_antecedentes=false`) | PERSONA_1 redacta; PERSONA_2 revisa | Borrador el dia 7 | Numero reservado en el chat |
| H8 | Pantalla de configuracion de procesos (admin), en solo lectura con `GET /procesos` | PERSONA_1 | 3 | Ninguna (recorte R3) |
| H9 | ADR para `desconocido` en `tipo_documental_detectado` (Contrato 1 y `endpoints.md`). EN CURSO: ADR-009 propuesto en `docs/adr-009-desconocido`; falta abrir el PR | PERSONA_2 redacta; PERSONA_1 revisa | 2 (dias 4-5) | Ninguna |
| H10 | Decidir ADR-007 antes de sustituir `motor_stub.py`. DECIDIDO por PERSONA_2 (spec, `96f7425`): `procesar_documento` no sustituye al stub hasta que la confianza la calcule el codigo. Falta que PERSONA_1 lo confirme | PERSONA_2 decide; PERSONA_1 conecta | 2 | Ninguna |
| H11 | Formato estable de `INDICE.md`. EN PARTE: `test_fixtures_ocr.py` ya filtra por los casos y el nivel conocidos (`7c84720`). Falta documentar el formato en `fixtures/README.md` (o generar un `INDICE.json`), porque el test sigue leyendo el Markdown | PERSONA_2 | 2 | Ninguna |
| H12 | Tiempo maximo esperado por documento y por pagina escaneada. HECHO en la spec, seccion 13 (llega con el PR #11): ~60 s normal, 244 s maximo medido, 540 s peor caso de una pagina | PERSONA_2 | 2 | Ninguna; lo usa H6 |
| H13 | Mantener `generar_fixtures.py` (tipos de regla nuevos en su evaluador), `verificar_ocr_fixtures.py` (mismo preprocesado que `orquestador/ocr.py`) y `procesar_especimenes.py`; PR pequeno para fijar PyMuPDF y Pillow | PERSONA_2 | 2-3 | Al cambiar reglas u OCR |
| H14 | `rag/embeddings.py` (Ollama `nomic-embed-text`), `rag/memoria.py`, migracion de `memoria_folios`, `buscar_antecedentes` con permisos y caducidad, `rag/servicio.py` y `rag/README.md` | PERSONA_2 | 3 (dias 9-11) | H7; `resumen.md` de PERSONA_1 (se puede probar antes con un `.md` ficticio) |
| H15 | `sensible: true` en los YAML y en el cargador | PERSONA_2 | 3 | H7 |
| H16 | Router `GET /folios/{folio}/antecedentes` y pantalla "Antecedentes" en el expediente | PERSONA_1 | 3 (dias 10-11) | H7, H14 |
| H17 | Enmascaramiento en la UI con "mostrar" auditado (`dato_revelado`) | PERSONA_1 | 3 | H7, H15 y el enmascaramiento de la API |
| H18 | Repetir o recortar las 4 fotos de especimenes descartadas, solo si se rechaza R5 | PERSONA_2 | 3, solo si se rechaza R5 | Ninguna |
| H19 | Demo: guion (recibir -> procesar -> validar -> consolidar -> exponer + antecedentes), ensayo y `docker compose up` desde cero | PERSONA_1 lidera; PERSONA_2, motor y maquina de Ollama | 4 | Todo lo anterior |

Para no bloquearse:
- PERSONA_1 no espera al motor: los dias 4-6 hace H1, H2, el humo de H6 con el stub, H8 y el
  borrador de H7.
- PERSONA_2 cierra H9 (abrir el PR del ADR-009) antes que nada, porque desbloquea H3 y H4, y no
  espera a `resumen.md` para H14:
  la memoria indexa cualquier Markdown y se prueba con uno ficticio y embeddings simulados.
- Orden de fusion propuesto: #11 -> #12 (con los ajustes) -> traspaso. Ninguno choca con los demas
  (ver la descripcion del PR del traspaso).
- Cada PR lo sigue revisando la otra persona; con dos, cada una revisa todo lo de la otra.

PREGUNTA PARA EL EQUIPO (se decide en la reunion; hasta entonces el reparto de arriba no cambia):
con este reparto, PERSONA_2 lleva la ruta critica de la etapa 2 (`procesar_documento`, ADR-007 y
reglas) y ademas toda la carpeta `rag`. Alternativa: que `rag/memoria.py` (H14) la haga PERSONA_1,
que ya tiene las migraciones, el expediente que genera `resumen.md`, el router `/antecedentes` y la
pantalla de antecedentes (H16), reutilizando `rag/embeddings.py` y el troceado de PERSONA_2.

## Recortes propuestos (PROPUESTA: los decide el equipo; el MVP no se recorta)
| Id | Recorte | Por que |
|---|---|---|
| R1 | Extra 4 (factura y comprobante de gasto): fuera | Dos YAML, casos nuevos en el generador, `INDICE.md` y `test_fixtures_ocr.py` que cambian; no aporta al MVP |
| R2 | Extra 3 (administracion de tipos documentales): fuera | `GET /tipos-documentales` ya basta para la UI; editar tipos exige decidir la fuente de verdad de los YAML |
| R3 | Edicion de procesos: solo lectura | ADR-006 (bloque 4) dice que excede el MVP y el PR #12 la deja fuera; el ADR de la etapa 3 solo lo deja escrito |
| R4 | Extra 2 (`VIS-xxx`): solo si el dia 11 el hito y la memoria estan en verde | Es el primero que cae si PERSONA_2 va justa |
| R5 | No repetir las 4 fotos de especimenes | Las 5 actuales cubren los 3 tipos y el caso dificil del comprobante (0/4 con OCR) |
| R6 | `openrouter.py` al final de la etapa 3 y opcional en la demo | Con `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` no se usa nunca |
| R7 | Antecedentes con la opcion a) de ADR-006: `referencia_externa` del folio | Sin HMAC de la CURP ni clave nueva; un folio sin referencia no tiene antecedentes |
| R8 | Enmascaramiento minimo: CURP, numero de pasaporte y clave de elector | Menos campos `sensible`, menos pruebas; la parte de correcciones del extra 1 ya existe (tabla `correcciones`, PR #9) |
| R9 | e2e reales: humo en cada cambio y los folios de `INDICE.md` solo antes de cada PR de etapa; los de dificultad, fuera | Con Ollama sin GPU, 14 documentos son unos 15 min por ejecucion |

## Riesgos y avisos
- **Hashes de los fixtures:** dependen de PyMuPDF 1.28.2 y Pillow 12.3.0. `requirements.txt` usa
  `>=`: si suben al reconstruir la imagen, los tests de hashes se omiten (`versiones_fixtures.py`) en
  vez de fallar, y `DUP-001` deja de coincidir con los mocks. Para fijar versiones nuevas hay que
  regenerar `sha256_fixtures_existentes.txt`, `frontend/public/mock-originales` y los mocks.
- **OCR y resolucion:** en los niveles dificiles el OCR cae de golpe al bajar la resolucion (en la foto
  extrema, 115 dpi da 12 % y 118 dpi da 0 %). Tras tocar `PARAMETROS`, volver a verificar.
- **Especimenes:** sus fechas no se mueven. Desde el 2026-12-14 el comprobante da
  `REG-antiguedad_maxima` (critica); no afecta a la demo de los dias 13-14.
- **Tiempos de Ollama sin GPU** (VM de 2 nucleos y 16 GB, un documento cada vez): 48-73 s por
  documento normal (59 s de media) y hasta 244 s en dificil o extremo. El peor caso teorico de una
  pagina es de 9-11 min. El sondeo se para a los 10 min sin cambios; "Comprobar de nuevo" lo reanuda.
- **`test_fixtures_ocr.py`** (PR #11) parsea el Markdown de `INDICE.md`. Desde `7c84720` solo usa los
  casos y el nivel conocidos, asi que un caso nuevo ya no lo rompe, pero un cambio de formato si (H11).
- **`test_contrato_frontend.py`** compara `contrato.ts` con `resultado.py`, los catalogos y `config/`:
  un ADR que cambie el Contrato 1 (H9) obliga a tocar `contrato.ts` en el mismo PR.
- **Build sin mocks:** `npm run build` falla si queda algun rastro de msw. No quitar la comprobacion.
- **Maquina de la demo:** sigue sin decidir (sin GPU). Repetir los tiempos en ella y ajustar H6.

## Anexo: notas de adaptacion de PERSONA_3
Resumen de las notas de trabajo de PERSONA_3 sobre los PR #9, #10 y #11, que no estaban en el repo.

### A. Adaptacion al PR #9 (HECHA, en `main` con el PR #10)
Revision del PR #9 (plataforma, etapa 2): los 9 puntos quedaron resueltos al fusionarse.

| Punto | Como quedo |
|---|---|
| 1. Ficha de `corregir_datos` | Ficha de extraccion (confirmado > declarado > detectado); el tipo efectivo sigue en EXP-001/EXP-002, comparaciones y recomendacion |
| 2. `anio` y `null` | `null` solo en opcionales y `anio` entero. Queda la nota del `"0999"` (no bloquea) |
| 3. `n_bloqueantes_sin_resolver` | Alertas visibles de la version vigente, la misma regla que `DECISION_BLOQUEADA` |
| 4. Conservar solo `aplica=false` | En EXP-001, CMP-001 y EXP-002 |
| 5. Recomendacion global | No usa la del documento |
| 6. Documento en `error` sin `SYS-00x` | Documentado en `ingesta/README.md`: sin resultado ni codigo; hay que volver a subirlo |
| 7. Forma del `detalle` de auditoria | Tabla por accion en `api/README.md` |
| 8. Ficheros compartidos | Nombrados en la descripcion, salvo `.env.example` (menor) |
| 9. `EXP-002` | En el documento, informativa |

Cambios hechos en el frontend y los mocks:
- Codigos oficiales: `DOCUMENTO_CON_ERROR` y `EXP-002`; `CODIGOS_PENDIENTES_DE_MAIN` queda vacia.
- PATCH de datos como `_valor_corregido`; `""` da 422 tambien en un opcional; una entrada
  `dato_corregido` por PATCH.
- Reproceso: no toca `CLS-001`; mientras esta pendiente se ve la version anterior; al completar
  desaparecen las alertas del motor de esa version y sus correcciones.
- EXP-001 solo con documentos completados; CMP-001 como `validacion.comparar` (sin vacios, con
  fechas normalizadas); recomendacion global como `recomendacion.py`; `detalle` de auditoria con la
  forma real; un documento en error sin `SYS-00x` en `ONB-2026-000003`.
- Arreglado: el aviso de tipos que faltan de la carga contaba los documentos en error.

### B. Plan de adaptacion al PR #11 (PENDIENTE, heredado)
Punto de partida comprobado: el #10 y el #11 no tienen ficheros en comun y se fusionan sin
conflictos; el #11 no toca contratos ni catalogos, y los codigos que emite (`CLS-001`,
`SYS-001/002/003/005`, `VAL-003`) ya estan en `codigos.ts`. Su evaluacion uso los fixtures de este
generador con `--hoy 2026-09-30` (coinciden byte a byte).
- Tras fusionar el #11: avisar a PERSONA_2 de que la seccion 8 de su spec ya puede usar
  `scripts/generar_fixtures.py --hoy 2026-09-30` de `main`; quitar del docstring del generador el
  pendiente de `ejemplos_referencia` (el #11 lo resuelve). -> PERSONA_2 (H13).
- Fixtures: documentar en `fixtures/README.md` lo que no se puede cambiar sin avisar en `INDICE.md`
  (titulos `### caso / tipo`, linea `Archivos:`, filas `| campo | valor |`, bloque de la MRZ y la
  seccion `## Fixtures de dificultad`), o publicar un `INDICE.json` (H11). Cuando PERSONA_2 anada
  tipos de regla (`coherencia_curp_fecha`, `fechas_ordenadas`), el evaluador del generador fallara
  con "Tipo de regla desconocido": implementarlos alli y regenerar (H13). Las personas ficticias ya
  son coherentes con la CURP. Si `GET /tipos-documentales` expone claves nuevas del cargador
  (`sensible`, `marcadores_clasificacion`), anadirlas a `tipos_documentales.json` y al test de
  `test_contrato_frontend.py`.
- Mocks (H3): `VERSION_PROMPT` de `extraccion@v1` a `extraccion_{tipo}@v3` (tambien en `logica.ts`);
  evidencias `pagina_1:seccion_superior` y `pagina_1:seccion_central`; un documento `desconocido`
  con tipo declarado (`CLS-001` y datos con la ficha declarada) y, si se puede, otro sin declarado
  (`datos_extraidos: {}` y sin alertas); un campo con fecha no normalizable (texto tal cual y
  confianza 0). Mantener `VAL-002`, `CLS-002`, `REG-*` y la recomendacion en los mocks, porque son el
  contrato final, pero sin esperarlos en los e2e reales hasta que existan `validacion/reglas.py` y
  ADR-007.
- UI: H4 y H5; comprobar con un test que `fechaHora()` acepta `2026-10-01T19:42:53.362052Z`.
- Tiempos (H6): mantener el limite del sondeo en 10 min (cada documento que termina lo reinicia);
  e2e reales solo con fixtures normales, 5 min por documento y 10 min por folio de 3; los de
  dificultad, como mucho en un test marcado como lento de 20 min; calentar Ollama (`KEEP_ALIVE`
  10 min) antes de cronometrar; repetir las medidas en la maquina de la demo.
- Especimenes: PERSONA_2 los evalua con `evaluar_fixtures.py` (nivel `especimen`) contra el caso
  `sano` con `--hoy 2026-09-30`.
- Hashes: proponer en un PR pequeno fijar `pymupdf==1.28.2` y `pillow==12.3.0` hasta la demo (H13).
- Comprobaciones tras fusionar: generar los fixtures desde `main` y comparar los SHA-256; pasar
  `test_fixtures_ocr.py` en el contenedor con `fixtures/` montado (153 campos, linea base 150);
  comparar la salida del CLI con `pasaporte_sano_digital.pdf` con el documento de los mocks (mismos
  valores; difieren `version_prompt`, evidencia y confianzas).

Revision de PERSONA_3 en el #11 (aprobada, nada bloquea): 1) spec desfasada (42 ficheros, variables
ya en `.env.example`, `extraccion_v3`, PR #4 fusionado); 2) `desconocido` es un valor reservado que el
contrato no recoge (H9); 3) formato de `INDICE.md` (H11); 4) ADR-007 antes de sustituir el stub
(H10); 5) `version_prompt` solo guarda el de extraccion, quiza llevar el de clasificacion a
`datos_auditoria`; 6) formalizar en `interfaces.py` con un ADR los metodos de vision que hoy se usan
con `hasattr`, cuando llegue `openrouter.py`; 7) tiempo maximo por documento (H12).

### C. PR #10 (etapa 1 de la interfaz)
- OCR de referencia (2026-10-01): control 50/51 (98 %), normal 100/102 (98 %), dificil 24/34 (71 %),
  extremo 5/34 (15 %), especimen 23/27 (85 %).
- Folios de los mocks: `ONB-2026-000001` (con bloqueante), `000002` (un documento pendiente),
  `000003` (dos en error: uno con `SYS-001` y otro sin codigo) y `000004` (aprobado, con resumen).
- Decisiones que afectan a otros: la UI usa los contratos ampliados sin campos inventados; si se
  acuerda un codigo antes de que llegue a los catalogos, va en `CODIGOS_PENDIENTES_DE_MAIN`; el
  preprocesado de `verificar_ocr_fixtures.py` es el de `orquestador/ocr.py` (gris + autocontraste) y
  cambian juntos; si la API anade claves al `detalle` de auditoria, la UI las enmascara (`****` y los
  4 ultimos caracteres), nunca las muestra completas; el enmascaramiento no se hace solo en la UI.
- Que mirar al tocar el frontend: el cliente HTTP (401 cierra sesion salvo en el login; 409
  `FOLIO_CERRADO` pasa a solo lectura), los handlers frente a la API, `test_contrato_frontend.py` y
  que `fixtures/especimenes/` siga sin metadatos.
