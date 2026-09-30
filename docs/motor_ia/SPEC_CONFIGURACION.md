# Spec de configuracion del motor IA (PERSONA_2)

Documento vivo: cada decision de configuracion del motor IA se anota aqui, en el mismo commit que el
codigo que la aplica, con su entrada en el [registro de cambios](#registro-de-cambios).
Ambito: `configuracion`, `orquestador`, `motor_ia` y `validacion/reglas.py`.
Pruebas que justifican las decisiones: [pruebas_ollama.md](pruebas_ollama.md).

Estados: **implementado** (en el codigo de `feat/motor-ia`), **decidido** (acordado, sin codigo aun),
**pendiente** (por decidir o por hacer).

## 1. Donde vive cada configuracion

| Configuracion | Donde | Destino en el codigo | Estado |
|---|---|---|---|
| Fichas de tipos documentales | `config/tipos/*.yaml` (repo) | `configuracion/cargador.py`, expuesto por `configuracion/servicio.py` | implementado |
| `ejemplos_referencia` de las fichas | `config/tipos/*.yaml`: fixtures del caso sano en `fixtures/generados/`, con las mismas modalidades que ya tenia cada ficha (acordado con PERSONA_3) | referencia; test de nombres en `test_configuracion.py` | implementado |
| Fixtures de prueba | `fixtures/generados/` (en `.gitignore`): 30 ficheros + `INDICE.md`, generados en local con `scripts/generar_fixtures.py` de `feat/interfaz` (seccion 8) | tests de `ocr.py` y del preparador; valores esperados en `INDICE.md` | generados en local el 2026-09-30 |
| Asignacion de modelos por tarea | `config/modelos.yaml` (repo) | `motor_ia/enrutador.py` (`crear_enrutador`), validacion estricta | implementado |
| Barrera de privacidad | `.env`: `PERMITIR_PROVEEDORES_NO_PRIVADOS` (por defecto `false`) | `motor_ia/enrutador.py` | implementado; falta en `.env.example` (PR pendiente) y avisar al equipo |
| Nombres de los modelos de Ollama | `.env`: `OLLAMA_MODELO_TEXTO`, `OLLAMA_MODELO_VISION` | leidos por el enrutador via `modelos.yaml` (`modelo_texto_env`, `modelo_vision_env`) | implementado; `.env.example` pendiente de PR |
| URL de Ollama | `.env`: `OLLAMA_BASE_URL` | la lee el enrutador y la pasa a `OllamaProvider(base_url, ...)` | implementado |
| Proveedor comercial (respaldo) | `.env`: `PROVEEDOR_COMERCIAL_*` (ADR-003) | `motor_ia/proveedores/openrouter.py` | pendiente (cuenta sin crear) |
| Carpeta de configuracion | `.env` opcional: `CONFIG_DIR`; por defecto `config/` de la raiz del repo | `configuracion/cargador.py` | implementado; falta en `.env.example` |
| Carpeta de prompts | `.env` opcional: `PROMPTS_DIR` (en Docker, `/prompts`); por defecto `prompts/` de la raiz del repo | `motor_ia/prompts.py` | implementado; falta en `.env.example` |
| Prompts versionados | `prompts/<id>_<version>.md` (repo), con frontmatter `id`, `version`, `salida` | `motor_ia/prompts.py` (`renderizar`) | implementado: v1 y v2 |
| Version vigente de cada prompt | constante `VERSIONES_VIGENTES` en `motor_ia/prompts.py` (`clasificacion: v2`, `extraccion: v2`, `correccion_json: v1`) | `motor_ia/prompts.py` | implementado |
| Borradores de prompts | `docs/motor_ia/pruebas_ollama/prompts_borrador/` (repo) | `extraccion_v2b.md` paso a `prompts/extraccion_v2.md` | referencia |
| Parametros de llamada (`TEMPERATURA`, `NUM_PREDICT`, `NUM_CTX`, `ANCHO_MAX_IMAGEN`, `MAX_PAGINAS_POR_LLAMADA_VISION`, `MAX_CARACTERES_TEXTO`, timeouts, `KEEP_ALIVE`) | constantes en `motor_ia/proveedores/base.py` | `motor_ia/proveedores/*.py` | implementado (valores en la seccion 4) |
| Procesos (`procesos.yaml`) | `config/procesos.yaml` (repo) | modulo de PERSONA_1 | fuera de este ambito |
| Scripts, imagenes y resumenes de las pruebas | `docs/motor_ia/pruebas_ollama/` (repo) | referencia; no los importa el backend | implementado |
| Respuestas crudas del modelo | 7 seleccionadas en `backend/tests/respuestas_modelo/` (nombre = modalidad, modelo y caso); el resto, en la carpeta local de pruebas | tests de `proveedores/` | implementado |

## 2. Modelos de Ollama

| Uso | Modelo | Variable del `.env` | Resultado en las pruebas | Estado |
|---|---|---|---|---|
| Texto (clasificacion y extraccion de `pdf_digital`) | `gemma4:e2b` | `OLLAMA_MODELO_TEXTO=gemma4:e2b` | 7/7 campos en 2 de 2 ejecuciones; ~37 s por documento | decidido |
| Vision (`pdf_escaneado`, `imagen`) | `qwen2.5vl:3b` | `OLLAMA_MODELO_VISION=qwen2.5vl:3b` | 7/7 tras normalizar fechas en 4 de 4; ~110 s por pagina nueva | decidido |
| URL de Ollama | - | `OLLAMA_BASE_URL`: depende de donde corre el backend (ver tabla siguiente) | - | decidido |
| Embeddings (RAG, etapa 3) | `nomic-embed-text` (plan) | `OLLAMA_MODELO_EMBEDDINGS` (propuesta) | sin probar | pendiente |

Valor de `OLLAMA_BASE_URL` segun donde corre el backend (o el CLI) y donde corre Ollama:

| Backend / CLI | Ollama | `OLLAMA_BASE_URL` | Uso |
|---|---|---|---|
| En local (venv, fuera de Docker) | Instalado en la misma maquina | `http://localhost:11434` | Desarrollo y CLI de la etapa 1. Valor del `.env` local de PERSONA_2 |
| Dentro de un contenedor | Instalado en el Windows anfitrion (Docker Desktop) | `http://host.docker.internal:11434` | Backend en docker compose sin levantar el servicio `ollama` |
| Dentro de un contenedor | Servicio `ollama` de docker-compose | `http://ollama:11434` | Solo si se levanta ese servicio. Es el valor actual de `.env.example` |

Notas:
- `localhost` dentro de un contenedor apunta al propio contenedor, no al anfitrion: por eso hace falta
  `host.docker.internal`.
- No levantar a la vez el Ollama local y el servicio `ollama` de docker-compose: los dos usan el
  puerto 11434.
- `http://ollama:11434` solo se resuelve dentro de la red de docker compose.

Modelos descartados:

| Modelo | Motivo |
|---|---|
| `gemma4:e2b` como vision | En Windows no procesa imagenes: no lee ni una imagen con la palabra "HOLA" y se inventa los datos con confianza 0,95. Fallo conocido, issue [ollama#16532](https://github.com/ollama/ollama/issues/16532), abierto; sin arreglo en 0.35.0 ni 0.35.1-rc0 |
| `gemma4:e4b` | Ocupa ~9,6 GB y la maquina tiene ~8 GB libres; ademas tiene el mismo fallo de vision |
| `llama3.2-vision:11b` (valor inicial del `.env.example`) | Sin probar: demasiado grande para esta maquina (CPU de 2 nucleos, sin GPU) |
| `qwen2.5:7b` como texto (valor inicial del `.env.example`) | Funciona (6/7 y 7/7) pero tarda el doble (65-75 s) y no es determinista: omitio un campo en una ejecucion |
| `qwen2.5vl:3b` como texto | 4/7: no convierte fechas ni respeta la evidencia; `gemma4:e2b` es mejor con texto |
| `gemma4:e4b-it-qat` | Sin probar. Segun el issue #16532 si ve imagenes en Windows; candidato si hay mas RAM |

## 3. Regla del enrutador

Regla: **modelo de texto si `doc.modalidad == pdf_digital`; modelo de vision en el resto.**
Se aplica a clasificacion y a extraccion. Se decide sin ADR: `Enrutador.obtener(tarea, tipo)`
(Contrato 3) devuelve el proveedor configurado y el proveedor elige su modelo de texto o de vision
segun `DocumentoPreparado.modalidad`. Documentado en `backend/app/modulos/motor_ia/README.md`.

Enrutador (`motor_ia/enrutador.py`, implementado):

| Regla | Detalle |
|---|---|
| `obtener(tarea, tipo)` | `por_tipo` del YAML si existe para ese tipo; si no, `principal`. Una instancia por proveedor, compartida entre tareas |
| `respaldo(tarea, tipo)` | El `respaldo` del YAML, o `None` si es el mismo que el principal o no esta disponible |
| Variables de entorno | Solo las que nombra el YAML; ni modelos ni claves en el codigo. Los errores y avisos nombran la variable, nunca su valor. Un valor de ejemplo (`TU_CLAVE_AQUI`, `TU_MODELO_AQUI...`) cuenta como no configurado |
| Barrera de privacidad (ADR-003) | Un proveedor con `privado: false` solo se usa con `PERMITIR_PROVEEDORES_NO_PRIVADOS=true` (desarrollo con fixtures ficticios). Principal no privado con la barrera cerrada: error al arrancar. Respaldo no privado: `None` y aviso |
| Proveedor no disponible | Principal (falta una variable, valor de ejemplo o tipo sin implementar): `ErrorEnrutador` al arrancar. Respaldo: `None` y aviso en el log; si falla el principal, el servicio emite `SYS-001` |
| Validacion de `modelos.yaml` | Estricta: claves desconocidas, tipo de proveedor (`ollama`, `openrouter`), variables de cada tipo, tareas validas, `clasificacion` y `extraccion` obligatorias, proveedores y tipos documentales de `por_tipo` existentes; todos los errores a la vez |
| Tipos de proveedor | `ollama` implementado; `openrouter` aceptado en el YAML pero sin implementar (queda como respaldo no disponible) |

| Modalidad | Que prepara el orquestador | Modelo | Que se envia al modelo |
|---|---|---|---|
| `pdf_digital` | Texto por pagina (PyMuPDF) + PNG a 150 dpi | texto: `gemma4:e2b` | Solo el texto, en `{{ contenido }}`. Los PNG no se envian |
| `pdf_escaneado` | PNG a 200 dpi; por pagina, capa de texto si supera el umbral (PDF mixto) y OCR si no | vision: `qwen2.5vl:3b` | Imagenes reducidas a 1000 px de ancho + texto OCR en `{{ contenido }}` (ver pendiente OCR frente a vision) |
| `imagen` | La propia imagen, orientada segun EXIF y en PNG, + OCR | vision: `qwen2.5vl:3b` | Igual que `pdf_escaneado` |

Respaldo: si el proveedor principal falla, se usa el `respaldo` de `modelos.yaml` (OpenRouter
gratuito, ADR-003, solo con fixtures ficticios). Sin respaldo disponible: `estado_analisis=error` +
`SYS-001`.

## 4. Reglas de vision y parseo

| Regla | Valor | Motivo | Donde | Test |
|---|---|---|---|---|
| Fechas | El prompt pide las fechas **tal como aparecen**; el codigo las normaliza con `normalizar_fecha` (dia/mes/anio -> `AAAA-MM-DD`, separadores `/ . -` y espacio; ISO valido se deja igual; fecha imposible -> `None`) | Al convertirlas, `qwen2.5vl:3b` intercambia dia y mes (`10/05/2024` -> `2024-10-05`). Sin convertir: 3/3 correctas en 4 de 4 | `motor_ia/proveedores/base.py` (tarea 7). Referencia: `pruebas_ollama/prueba_fechas.py` | unitario con los 11 casos del autotest |
| Tamano de imagen | `ANCHO_MAX_IMAGEN = 1000`: `reducir_imagen` antes de enviar; solo reduce y mantiene la proporcion | Sube los aciertos de 5/7 a 6/7 y ahorra ~20 % de tiempo; 800 px no mejora | `proveedores/base.py` | unitario |
| Lotes de vision | `MAX_PAGINAS_POR_LLAMADA_VISION = 4`. Con mas paginas no se ignora ninguna: se procesan por lotes de 4 y se combinan (`combinar_lotes`). Por campo, el valor no nulo con evidencia valida; ante empate, el de la pagina mas baja; si ningun lote tiene evidencia valida, el primer valor no nulo. La clasificacion solo usa el primer lote. En un lote, `pagina_1..k` relativa a las imagenes enviadas se traduce a la pagina real | Cada pagina A4 a 1000 px suma ~1 850 tokens y ~130 s en CPU | `proveedores/base.py`, `proveedores/ollama.py` | unitario con Ollama simulado |
| Contexto | `NUM_CTX = 16384`. Medido (`pruebas_ollama/prueba_num_ctx.py`): 1 pagina A4 + prompt = 2 457 tokens; 4 paginas + prompt + 20 000 caracteres = 13 476; con `NUM_PREDICT` quedan ~2 100 de margen (13 %) | Si no se fija, Ollama usa un contexto menor y recorta la entrada sin avisar | `proveedores/base.py` | unitario del cuerpo de la peticion |
| Timeouts | Texto: 120 s. Vision: 60 s + 150 s por imagen (4 imagenes -> 660 s). El reintento de correccion, sin imagenes, usa el de texto | Medido: 4 paginas = 499 s solo de lectura del prompt; un timeout fijo de 300 s fallaria siempre | `proveedores/base.py` (`timeout_vision`) | unitario |
| Texto largo | `MAX_CARACTERES_TEXTO = 20000`: `recortar_texto` respeta el orden de las paginas y marca `[texto recortado]`. Si se recorta, alerta **`SYS-003`** (preventiva): "El texto del documento supera `MAX_CARACTERES_TEXTO` y se ha recortado; los campos de las paginas finales pueden no haberse extraido". En el PR unico `docs/adr-007-y-alertas` (PR #4, `4263190`), pendiente de fusionar en `main` | Mantener el prompt dentro de `NUM_CTX` | `proveedores/base.py`; la alerta, en `motor_ia/servicio.py` (tarea 9) | unitario |
| Evidencia | Valida: `pagina_<n>[:detalle]` de una pagina del documento. En vision solo `pagina_<n>`; en texto se conserva el detalle (p. ej. `pagina_1:Fecha de caducidad`). Si es invalida, se quita: el Contrato 1 no admite valores nulos | `qwen2.5vl:3b` copia la seccion del ejemplo o devuelve `seccion_superior` sin pagina | `proveedores/base.py` | unitario con respuestas guardadas |
| Campos y tipos | Solo se conservan los campos de la ficha (`qwen` anadio `tipo` y `pais_emisor`); un campo ausente queda `null` con confianza 0. `anio` de 4 cifras -> entero; si no, texto original con confianza 0. Los valores que no son texto se convierten a texto | La regla `anio_mayor_o_igual_actual` compara numeros | `proveedores/base.py` | unitario |
| Fecha no normalizable | Se conserva el texto original con confianza 0 (p. ej. `"mayo 2034"`). **Las reglas de fecha de la etapa 2 deben tratarlo como fecha invalida y generar una alerta, sin fallar** | Que el revisor vea el dato y no salte un falso `VAL-001` (obligatorio ausente) | `proveedores/base.py`; reglas en `validacion/reglas.py` (etapa 2) | unitario |
| Clasificacion fuera de la lista | Un tipo que no esta entre los posibles pasa a `desconocido` con confianza 0; se ignoran mayusculas y espacios | El modelo puede inventar tipos | `proveedores/base.py` | unitario |
| Confianza del modelo | **No se usa en las reglas.** ADR-007 **aceptado** (2026-09-30): `nivel_confianza_por_campo` y `confianza_clasificacion` las calcula el codigo y la del modelo va solo a la auditoria | Siempre 0,9 o 1, tambien en datos mal leidos o inventados | `motor_ia` y `validacion/reglas.py` (etapa 2) | unitario |
| Formato de salida | `format: "json"` + `limpiar_json` (quita las marcas de bloque de codigo y el texto de alrededor) + parseo estricto con Pydantic (claves obligatorias y tipos). Si no es valido: 1 reintento con `prompts/correccion_json_v1.md`, sin reenviar las imagenes; si vuelve a fallar, `ErrorRespuestaInvalida` -> `SYS-002` (existe en `codigos_alertas.md`: "JSON del modelo invalido tras el reintento de correccion", critica) | JSON valido en todas las pruebas, pero no esta garantizado | `proveedores/base.py`, `proveedores/ollama.py` | unitario con Ollama simulado |
| Errores del proveedor | `ErrorProveedor`: timeout, conexion, HTTP 404 (modelo no descargado), 429, 5xx o respuesta sin contenido; el servicio decide si usa el respaldo. `ErrorRespuestaInvalida` es un subtipo | - | `proveedores/base.py`, `proveedores/ollama.py` | unitario |
| Registro de la llamada | `OllamaProvider.ultima_llamada` (`InfoLlamada`): modelo real usado, segundos, tokens de entrada y salida, peticiones, reintentos y lotes. `modelo_para(doc)` da el modelo segun la modalidad | El atributo `modelo` del Protocol no distingue texto y vision; la auditoria necesita tiempos y tokens | `proveedores/ollama.py` | unitario |
| Razonamiento | `think: false` solo si el modelo tiene la capacidad `thinking` segun `/api/show` (se consulta una vez por modelo; `gemma4` si, `qwen2.5vl` no) | `gemma4` razona por defecto: mas lento y mezcla texto con el JSON | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Temperatura | `temperature: 0` | Respuestas lo mas estables posible (no garantiza determinismo) | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Tope de salida | `num_predict: 800` | Sin tope, una transcripcion se quedo mas de 10 minutos repitiendo `<<<<` | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Tests | Solo con respuestas guardadas en `backend/tests/respuestas_modelo/`; nunca contra el modelo real | El modelo no es determinista y tarda de 35 a 125 s | `backend/tests/` | - |

## 5. Prompts

| Version | Estado | Contenido | Donde |
|---|---|---|---|
| `clasificacion_v1`, `extraccion_v1` | en el repo (historial) | Version inicial. Falta una variable para el texto del documento | `prompts/` |
| `clasificacion_v2`, `extraccion_v2` | **vigentes** (implementado) | Anaden `{{ contenido }}` (texto por pagina). `extraccion_v2`: fechas tal como aparecen, formato de evidencia, bajar la confianza si hay dudas y no inventar valores (cuerpo identico al borrador v2b validado). `clasificacion_v2`: `desconocido` si no encaja claramente | `prompts/` |
| `correccion_json_v1` | vigente (implementado) | Instruccion del reintento cuando la respuesta no es valida; variable `{{ error }}` | `prompts/` |
| `extraccion_v3` | pendiente (etapa 3, extra 2) | Pide `observaciones_visuales` (legibilidad, recortes, alteraciones) para las alertas `VIS-xxx`. El plan lo llamaba `extraccion_v2`; se renumera porque la v2 ya se usa | - |

Reglas de `motor_ia/prompts.py`:

| Regla | Detalle |
|---|---|
| `version_prompt` (`FechaYModelo`) | Sigue el ejemplo de `resultado.py`. Extraccion: `<id>_<tipo>@<version>` (p. ej. `extraccion_pasaporte@v2`). Clasificacion, sin tipo: `clasificacion@v2` |
| Variables | Jinja con `StrictUndefined`: si falta una variable, `ErrorPrompt`. `tipo_documental` se pasa aparte y tambien es variable del prompt |
| Contenido del documento | Se inserta como valor; nunca se interpreta como plantilla (un `{{ ... }}` del documento queda literal) |
| Formato comun | `formatear_contenido` (`--- pagina_<n> ---`; `(sin texto extraido)` si no hay texto), `formatear_tipos`, `formatear_esquema`, `formatear_contexto_rag` (`(sin contexto)` si esta vacio) |
| Errores | `ErrorPrompt`: fichero inexistente, frontmatter ausente o mal formado, `id`/`version` distintos del nombre del fichero, plantilla invalida, prompt sin version vigente |

Nota: el borrador `extraccion_v2.md` (fechas convertidas por el modelo) queda como referencia de lo
que no funciono. La evidencia del borrador v2b pide seccion; en la v2 definitiva, el parseo de vision
se queda solo con `pagina_<n>` (seccion 4).

## 6. Otras decisiones

| Decision | Detalle | Origen | Estado |
|---|---|---|---|
| API publica por modulo | Los demas modulos solo importan `configuracion/servicio.py` (`cargar`, `obtener`, `listar`) | ADR-005 | implementado |
| Validacion estricta de YAML | Claves desconocidas prohibidas; todos los errores de todos los ficheros en un unico `ErrorConfiguracion` | plan del cargador | implementado |
| `CONFIG_DIR` y `PROMPTS_DIR` | Variables de entorno opcionales; por defecto, rutas relativas a la raiz del repo | plan del cargador | implementado |
| Modalidad: umbral | `UMBRAL_CARACTERES_POR_PAGINA = 30` caracteres de texto extraible por pagina, sin contar espacios; el umbral exacto cuenta como texto | plan de `modalidad.py` | implementado (`orquestador/modalidad.py`) |
| Modalidad: PDF mixto | Si alguna pagina no llega al umbral, el PDF es `pdf_escaneado` (confirmado por PERSONA_2) | plan de `modalidad.py` | implementado |
| Modalidad: deteccion | Por los primeros bytes (`%PDF-`, PNG, JPEG); si no coinciden con la extension, manda el contenido y se registra un aviso en el log, sin el nombre del archivo (util en el CLI, que no pasa por la ingesta). **No emite alerta**: en la API la ingesta ya rechaza esos archivos con 415 `FORMATO_NO_PERMITIDO` (revision de PERSONA_1, PR #4); formato desconocido, vacio, PDF corrupto, cifrado o sin paginas -> `FormatoNoSoportado` | plan de `modalidad.py` | implementado |
| Preparador: DPI | `pdf_digital` a 150 dpi y `pdf_escaneado` a 200 dpi (PNG RGB); la reduccion a 1000 px la hace el proveedor | prompt de PERSONA_2 | implementado |
| Preparador: PDF mixto | Capa de texto en las paginas que superan el umbral y OCR solo en las demas | plan de la tarea 4 | implementado |
| Preparador: sin Tesseract | Las paginas que necesitaban OCR quedan con `texto=None`; aviso unico en el log, sin el nombre del archivo; la vision sigue | plan de la tarea 4 | implementado |
| Preparador: limite de paginas | Ninguno en el MVP (el proveedor trabaja por lotes de 4) | plan de la tarea 4 | decidido |
| CLI sin BD ni S3 | `folio_solicitud = "CLI-2026-000000"`; `referencia_archivo_original.ruta = "local://<nombre_archivo>"` (sin rutas personales); `hash` = SHA-256 real del archivo | objetivo de la etapa 1 | decidido (tarea 10) |
| Codigos de alerta del motor | `CLS-001` (critica): tipo declarado distinto del detectado. `SYS-001` (critica): fallo del proveedor sin respaldo. `SYS-002` (critica): JSON invalido tras el reintento. `SYS-003` (preventiva): texto recortado. Informativas: `SYS-005` (motor_ia: se uso el proveedor de respaldo) y `VAL-003` (orquestador/ocr: campo tomado de la MRZ). `SYS-004` se retiro en la revision del PR #4 (la ingesta rechaza con 415) y no se reutiliza; `SYS-005` conserva su numero. Catalogo: `docs/contratos/codigos_alertas.md`; `SYS-003`, `SYS-005` y `VAL-003`, en el PR unico `docs/adr-007-y-alertas` (PR #4, `4263190`), pendiente de fusionar en `main`. El motor no rellena `Alerta.id` | prompt de PERSONA_2, ADR-006 | `CLS-001`, `SYS-001`, `SYS-002`, `SYS-003`, `SYS-005` y `VAL-003` implementados en `motor_ia/servicio.py` (seccion 10); `CLS-002` y `VAL-002`, en la etapa 2 (deuda ADR-007) |
| `Tarea.validacion` (Contrato 3) | Se acepta en `modelos.yaml`, pero no se usa: la validacion son reglas deterministas en `validacion/reglas.py`, sin modelo. No se cambia el contrato | analisis de la etapa 0; tarea 8 | implementado (el enrutador la acepta) |
| Perfiles de modelos de `procesos.yaml` | `modelos: default` significa usar `modelos.yaml` tal cual; los perfiles por proceso **no se implementan** (reservados, fuera del MVP) | tarea 8 | decidido |
| Ficha para extraer | Se extrae con la ficha del tipo declarado; si no hay, con la del detectado. `tipo_confirmado` en `procesar_documento` manda sobre ambos (etapa 2) | ADR-006, 2.5 | decidido |
| `/tipos-documentales` | `configuracion/servicio.py` serializa `TipoDocumental` para el router de PERSONA_1 | ADR-006, 1.5 | pendiente (ver seccion 7) |
| RAG | PERSONA_2 hace `rag/conocimiento.py` (`buscar(consulta, k)` para `contexto_rag`) y usa `rag/embeddings.py` de PERSONA_3 | ADR-006, coordinacion | pendiente (etapa 3) |

## 7. Pendientes y riesgos

- [ ] **Maquina con GPU para Ollama** (riesgo 1 del plan). La VM actual (2 nucleos, 16 GB, sin GPU)
      tarda ~110 s por pagina con vision. Minimo orientativo: GPU NVIDIA con 8 GB de VRAM o mas, o
      32 GB de RAM y mas nucleos.
- [ ] **Instalar Tesseract** (`spa+eng`) en Windows; puede necesitar a TI. Plan B: OCR dentro del
      contenedor del backend.
- [ ] **OCR + texto frente a vision** para `pdf_escaneado` e `imagen`: comparar aciertos y tiempo
      (Tesseract + `gemma4:e2b` frente a `qwen2.5vl:3b`) cuando haya Tesseract.
- [ ] **Probar credencial de elector y comprobante de domicilio**: solo se ha probado el pasaporte.
- [x] **Fixtures de PERSONA_3** generados en local el 2026-09-30 (30 ficheros + `INDICE.md`), sin anadir sus
      scripts a `feat/motor-ia`. `ejemplos_referencia` de las fichas apuntan al caso sano.
- [ ] **OpenRouter**: crear la cuenta gratuita y probar los prompts con fixtures ficticios (propuesto al equipo).
- [ ] **PR pequeno de `.env.example`**: `OLLAMA_MODELO_TEXTO=gemma4:e2b`, `OLLAMA_MODELO_VISION=qwen2.5vl:3b`,
      `CONFIG_DIR`, `PROMPTS_DIR`, `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` y un comentario con los tres valores de
      `OLLAMA_BASE_URL` (seccion 2). **Avisar al equipo** de la barrera de privacidad: con `false`, OpenRouter
      no se usa nunca, ni como respaldo.
- [ ] **Aplicar ADR-006**: 1.5 serializar `TipoDocumental` en `configuracion/servicio.py` (para
      `/tipos-documentales`) y 2.5 `tipo_confirmado` en `procesar_documento` (etapa 2).
- [ ] **Avisar al equipo del cambio en `CLAUDE.md`** (linea de la spec de PERSONA_2) al abrir el PR de
      etapa: es un fichero compartido.
- [ ] Aviso a PERSONA_1: `configuracion.cargar()` en el arranque de `main.py` (mensaje preparado).
- [ ] **Fusionar el PR unico `docs/adr-007-y-alertas` (PR #4, `4263190`), pendiente de fusionar en `main`**: ADR-007 aceptado, `SYS-003`,
      `SYS-005`, `VAL-003` y el comentario de `resultado.py` (sin `SYS-004`, retirado en la revision). Sustituye a las ramas `docs/adr-007-confianza`
      y `docs/alerta-sys-003` (borradas del remoto y en local). Abrir el PR y avisar al equipo.
- [ ] **DEUDA ADR-007 (aceptado) - fecha limite: etapa 2, antes de `validacion/reglas.py` y de la
      recomendacion.** Hoy `nivel_confianza_por_campo` y `confianza_clasificacion` guardan la confianza del
      modelo como valor **provisional** y no se emiten `CLS-002` ni `VAL-002` (seccion 10). Hay que: calcular
      la confianza en el codigo (la del modelo, a la auditoria con `Analisis.llamadas`); `marcadores_clasificacion` en el cargador y, en un PR pequeno
      aparte con aviso (ficheros compartidos), en `config/tipos/*.yaml`; numero de marcadores y calibracion con
      los fixtures de PERSONA_3, sin cambiar los umbrales; confianza baja si fallan los digitos de la MRZ.
- [ ] **PyMuPDF no carga en el Windows de PERSONA_2**: falta el Microsoft Visual C++ Redistributable x64
      (`msvcp140.dll`). Mientras tanto, los tests se pasan en el contenedor del backend (seccion 8).
- [x] `.env` local de PERSONA_2: `OLLAMA_BASE_URL=http://localhost:11434`. Hecho el 2026-09-30.
- [ ] Si en la etapa 2 hace falta, pedir a PERSONA_3 un `CLS-003` para "tipo desconocido sin declarado ni
      confirmado" (hoy no se extrae y no se emite alerta; seccion 10).
- [ ] Reglas de fecha (etapa 2): una fecha no normalizable llega como texto con confianza 0; tratarla
      como fecha invalida y generar una alerta, sin fallar.
- [ ] `VAL-004` (etapa 2): `validacion` la emitira, informativa y con `campo`, cuando un campo `obligatorio: false`
      venga vacio. Aun no esta en el catalogo: PERSONA_3 la anade a `codigos_alertas.md` en un PR aparte y
      PERSONA_2 lo revisa.
- [ ] `NUM_CTX` con documentos reales: el margen medido es del 13 %; revisarlo si hay paginas mas altas que
      A4 (p. ej. oficio) o texto que tokenice peor que el de relleno usado en la medida.
- [ ] Riesgo: la confianza que da el modelo no es fiable (0,9-1 incluso en datos inventados).
- [ ] Riesgo: el modelo no es determinista ni con `temperature: 0`.
- [x] Borrar `qwen2.5:7b` de Ollama local (4,7 GB, descartado). Hecho el 2026-09-30.

## 8. Como pasar los tests

| Entorno | Comando (desde la raiz del repo) | Notas |
|---|---|---|
| Contenedor del backend (recomendado) | `docker compose build backend` y despues `docker compose run --rm --no-deps backend python -m pytest -q` | Incluye PyMuPDF y Tesseract. `--no-deps` no levanta `db` ni `ollama` (los tests no los necesitan); `--rm` borra el contenedor al terminar. Requiere `.env` y Docker Desktop en marcha |
| venv local | `cd backend && .venv/Scripts/python -m pytest -q` | En Windows necesita el Visual C++ Redistributable x64 para PyMuPDF |
| Contenedor + fixtures (integracion OCR) | `MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures:ro" backend python -m pytest -q` | `test_fixtures_ocr.py` busca `FIXTURES_DIR`, `/fixtures/generados` o `fixtures/generados` del repo; sin fixtures o sin Tesseract se salta |

Generar los fixtures de PERSONA_3 sin anadir sus scripts a esta rama (desde la raiz del repo, en Git Bash):

```
mkdir -p <scratchpad>/fixtures_p3 fixtures/generados
git show origin/feat/interfaz:scripts/generar_fixtures.py > <scratchpad>/fixtures_p3/generar_fixtures.py
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures" \
  -v "<scratchpad>/fixtures_p3:/scripts:ro" backend python /scripts/generar_fixtures.py --hoy AAAA-MM-DD
```

El script calcula sus rutas desde su ubicacion: montado en `/scripts`, lee `/config` y escribe en
`/fixtures/generados`. Con el mismo `--hoy`, los ficheros salen identicos byte a byte.

## 9. OCR (`orquestador/ocr.py`, tarea 3)

Implementado: `ocr.py` (`OCRProvider`, `TesseractOCR`), `mrz.py` y `preparador.py`. Resultado con los fixtures
(`test_fixtures_ocr.py`, 2026-09-30): **151/153 campos**, por encima de la linea base (en `pdf_digital` se usa
la capa de texto). Los 2 que faltan son `sexo` de `pasaporte_vencido_escaneado` y `_foto`; la MRZ da el sexo en
los 3 pasaportes vencidos. La lectura erronea de la MRZ de `pasaporte_vencido_escaneado` se detecta: fallan los
digitos de `numero_documento` y `compuesto`. OCR: ~0,8 s por documento en el contenedor.

| Requisito | Detalle | Origen |
|---|---|---|
| Linea base | 150/153 campos con Tesseract `spa+eng`, render a 200 dpi, escala de grises + autocontraste. `ocr.py` no debe quedar por debajo con los mismos fixtures | `scripts/verificar_ocr_fixtures.py` de PERSONA_3 (2026-09-30) |
| Sexo del pasaporte | Si no se lee en la zona visual, se toma de la MRZ: posicion 21 de la linea 2 (TD3). `Mrz.sexo` implementado; se aplica en `motor_ia/servicio.py` (tarea 9) | Fallo conocido: `sexo` "M" suelto no lo lee Tesseract |
| Digitos de control de la MRZ | Validar los digitos de control (numero, nacimiento, vencimiento, datos personales y compuesto, pesos 7-3-1). Un fallo indica una lectura erronea (p. ej. Z/2). **Sin codigo de alerta propio**: si fallan, se baja la confianza de esos campos al aplicar ADR-007 (tarea 9 / etapa 2). `validar_digitos` implementado | Fallo conocido de la MRZ de `pasaporte_vencido` |
| Enderezado (deskew) | No se hace: la linea base se alcanza sin el (rotaciones de 0,4 a 1,2 grados en los fixtures) | Decision de la tarea 3 |
| Casos de prueba | `pasaporte_vencido_escaneado.pdf` y `pasaporte_vencido_foto.jpg` (sexo "M" y confusion Z/2 en la MRZ); el resto de fixtures como regresion de la linea base | `INDICE.md` y `resultado_ocr.md` de PERSONA_3 |

## 10. Servicio de analisis (`motor_ia/servicio.py`, tarea 9)

Firma: `analizar(doc, *, folio, referencia, tipo_confirmado=None, enrutador=None, ahora=None) -> Analisis`
(`Analisis.resultado`: `ResultadoDocumento`; `Analisis.llamadas`: `InfoLlamada` de cada llamada, para la
auditoria). **Se aparta de la firma original `analizar(doc, ficha)`** del prompt de PERSONA_2 por dos motivos:
la ficha se elige dentro (ADR-006, 2.5) y `ResultadoDocumento` exige `folio_solicitud` y
`referencia_archivo_original`. Sin `enrutador`, se crea uno con `crear_enrutador()` la primera vez.

| Paso o regla | Detalle |
|---|---|
| Texto | `recortar_texto` (`MAX_CARACTERES_TEXTO`); si recorta, `SYS-003` (preventiva) |
| Clasificacion | Prompt `clasificacion_v2` con todas las fichas como tipos posibles. Con `tipo_confirmado` no se clasifica: `tipo_documental_detectado` y `confianza_clasificacion` quedan `None` (la plataforma conserva el detectado de la version anterior) |
| `CLS-001` (critica) | Hay tipo declarado y el detectado es distinto, incluido `desconocido` |
| Ficha para extraer | `tipo_confirmado` > declarado > detectado (ADR-006, 2.5). Un tipo declarado o confirmado que no existe lanza `TipoNoEncontrado` (la ingesta lo valida antes) |
| Tipo desconocido sin declarado ni confirmado | **No se extrae y no se emite alerta**: `completado` con datos vacios. Si en la etapa 2 hace falta, se pedira un `CLS-003` |
| Extraccion | Prompt `extraccion_v2` con el esquema de la ficha; `version_prompt` `extraccion_<tipo>@v2` |
| Sexo desde la MRZ | Solo `pasaporte` y solo si `sexo` llega `null`: posicion 21 de la linea 2, evidencia `pagina_<n>` de la pagina con la MRZ y `VAL-003` (informativa, `campo=sexo`). Confianza **1,0** si todos los digitos de control son correctos y **0,5** si alguno falla (provisional hasta ADR-007) |
| Respaldo | Si el principal lanza `ErrorProveedor` (incluido JSON invalido tras el reintento), se prueba el respaldo; si funciona, `SYS-005` (informativa), una sola vez por documento |
| Sin respaldo o falla tambien | `estado_analisis=error` + `SYS-002` si el ultimo fallo fue JSON invalido, `SYS-001` si no (criticas). Si la clasificacion salio bien, se conserva |
| `fecha_y_modelo_utilizado` | Proveedor, **modelo real** (`ultima_llamada.modelo`) y `version_prompt` de la extraccion; si no hubo extraccion, los de la clasificacion; `None` si no hubo ninguna llamada correcta |
| `Alerta.confianza` | **1,0** en las alertas deterministas (`CLS-001`, `SYS-00x`, `VAL-003`) |
| Alertas repetidas | Nunca dos con el mismo (`codigo`, `campo`) en un documento (ADR-006, 1.3) |
| Confianzas (**provisional**) | `confianza_clasificacion` y `nivel_confianza_por_campo` guardan la del modelo; **no se emiten `CLS-002` ni `VAL-002`**. Deuda ADR-007 con fecha limite: etapa 2, antes de `validacion/reglas.py` y de la recomendacion |
| Fuera de esta tarea (etapa 2) | `reglas_cumplidas_e_incumplidas`, `VAL-001`, `VAL-002`, `VAL-004`, `REG-*`, `recomendacion` y `procesar_documento` |

## Registro de cambios

El mas reciente arriba.

| Fecha | Cambio | Commit |
|---|---|---|
| 2026-09-30 | `motor_ia/servicio.py`: `analizar(doc, *, folio, referencia, ...)` -> `Analisis` (se aparta de `analizar(doc, ficha)` por ADR-006 y el Contrato 1). Ficha tipo_confirmado > declarado > detectado; `CLS-001`, `SYS-001/002/003/005`, `VAL-003` con confianza 1,0; respaldo tambien ante JSON invalido; sexo desde la MRZ (1,0 / 0,5); desconocido sin declarado no se extrae ni alerta. Confianzas del modelo provisionales, sin `CLS-002` ni `VAL-002` (deuda ADR-007). `orquestador.servicio` expone `buscar_mrz` y `validar_digitos` (17 tests) | este commit |
| 2026-09-30 | `motor_ia/enrutador.py`: `modelos.yaml` validado de forma estricta, proveedores desde las variables de entorno, `por_tipo`, barrera de privacidad `PERMITIR_PROVEEDORES_NO_PRIVADOS` (por defecto `false`), principal no disponible -> error al arrancar, respaldo no disponible -> `None`. `Tarea.validacion` aceptada sin uso; perfiles de `procesos.yaml` no implementados. `configuracion.servicio.directorio_config()` expuesto (24 tests) | `bbfdc9d` |
| 2026-09-30 | Pendiente de la etapa 2: `VAL-004` (informativa, campo `obligatorio: false` vacio, con `campo`), que emitira `validacion`; PERSONA_3 la anade al catalogo en un PR aparte y PERSONA_2 lo revisa | `7d2c361` |
| 2026-09-30 | Revision de PERSONA_1 en el PR #4: se retira `SYS-004` (la ingesta ya rechaza con 415 `FORMATO_NO_PERMITIDO` los archivos cuya extension no coincide con el contenido). `SYS-005` no se renumera. `modalidad.py` mantiene el aviso en el log (util en el CLI) y no emite alerta | `c696a99` |
| 2026-09-30 | ADR-007 **aceptado** por PERSONA_1, PERSONA_2 y PERSONA_3. PR unico de documentacion `docs/adr-007-y-alertas` (PR #4, `4263190`): ADR-007 aceptado, `SYS-003`, informativas `SYS-004`, `SYS-005` y `VAL-003`, y comentario del origen de la confianza en `resultado.py`. Borradas las ramas `docs/adr-007-confianza` y `docs/alerta-sys-003` | `e879271` |
| 2026-09-30 | `orquestador/ocr.py` (Tesseract, gris + autocontraste, sin deskew), `mrz.py` (TD3: busqueda, sexo, digitos de control) y `preparador.py` (150/200 dpi, PDF mixto con capa de texto + OCR, EXIF, sin Tesseract -> texto None) + `servicio.py`. Con los fixtures: 151/153 campos. MRZ sin alerta propia: confianza baja con ADR-007 | `ce6befa` |
| 2026-09-30 | `ejemplos_referencia` de las tres fichas apuntan a los fixtures del caso sano en `fixtures/generados/` (test de nombres). Fixtures de PERSONA_3 generados en local. Requisitos para `ocr.py` (seccion 9). `SYS-003` para el texto recortado, propuesta en la rama `docs/alerta-sys-003` | `799e60f` |
| 2026-09-30 | `proveedores/base.py` y `proveedores/ollama.py`: constantes de llamada en `base.py`, `NUM_CTX=16384` medido, timeouts de vision por imagen, lotes de 4 paginas con combinacion, evidencia y campos normalizados, fecha no normalizable como texto con confianza 0, `think` segun `/api/show`, reintento con `correccion_json_v1`. 7 respuestas reales en `backend/tests/respuestas_modelo/` | `6397817` |
| 2026-09-30 | `motor_ia/prompts.py`: carga y renderizado con frontmatter, `StrictUndefined`, `PROMPTS_DIR`, `VERSIONES_VIGENTES` (v2) y `version_prompt` `<id>_<tipo>@<version>` / `clasificacion@v2`. Prompts `clasificacion_v2` y `extraccion_v2` (19 tests) | `c41eaed` |
| 2026-09-30 | ADR-007 propuesto: confianza de campo y de clasificacion calculada por el codigo (clasificacion con `marcadores_clasificacion` del tipo detectado); la del modelo, solo en la auditoria | `7ece6b4` (PR: rama `docs/adr-007-confianza`, `a05bf3c`) |
| 2026-09-30 | `OLLAMA_BASE_URL` segun el entorno: `localhost` en local, `host.docker.internal` desde un contenedor con Ollama en Windows, `ollama` solo con el servicio de docker-compose. `.env` local con `localhost` | `86e5905` |
| 2026-09-30 | `orquestador/modalidad.py`: umbral 30, PDF mixto = escaneado, deteccion por bytes (21 tests). Tests en el contenedor del backend (seccion 8) por el bloqueo de PyMuPDF en Windows. Anotado el conflicto `VAL-002`/`CLS-002` con la regla de confianza. `.env` local con `gemma4:e2b` y `qwen2.5vl:3b`; `qwen2.5:7b` borrado | `86e5905` |
| 2026-09-30 | Merge de `origin/main`: ADR-004, ADR-006 y contratos 1 y 2 ampliados (PR #1 y #2). Contrato 3 sin cambios | `1149519` |
| 2026-09-30 | Spec creada con las decisiones de configuracion y pruebas del motor IA; informe y material de pruebas en `docs/motor_ia/` | `cc69521` |
| 2026-09-30 | Vision cerrada: `qwen2.5vl:3b`, fechas tal como aparecen + `normalizar_fecha`, imagenes a 1000 px, evidencia solo `pagina_<n>`, confianza del modelo fuera de las reglas | pruebas (sin codigo) |
| 2026-09-30 | Modelo de texto `gemma4:e2b`; enrutador: texto si `pdf_digital`, vision en el resto | pruebas (sin codigo) |
| 2026-09-30 | Descartados `gemma4` para vision (issue #16532), `gemma4:e4b`, `llama3.2-vision:11b` y `qwen2.5:7b` | pruebas (sin codigo) |
| 2026-09-30 | Cargador de fichas YAML: validacion estricta, `servicio.py`, `CONFIG_DIR` | `014e570` |
