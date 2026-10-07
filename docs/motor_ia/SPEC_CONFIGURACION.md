# Spec de configuracion del motor IA (PERSONA_2)

Documento vivo: cada decision de configuracion del motor IA se anota aqui, en el mismo commit que el
codigo que la aplica, con su entrada en el [registro de cambios](#registro-de-cambios).
Ambito: `configuracion`, `orquestador`, `motor_ia` y `validacion/reglas.py`.
Pruebas que justifican las decisiones: [pruebas_ollama.md](pruebas_ollama.md).
Explicacion en lenguaje sencillo para el equipo y la presentacion, con el historial de mejoras:
[EXPLICACION_MOTOR.md](EXPLICACION_MOTOR.md) (se actualiza en el mismo commit que esta spec).

Estados: **implementado** (en el codigo de `feat/motor-ia`), **decidido** (acordado, sin codigo aun),
**pendiente** (por decidir o por hacer).

## 1. Donde vive cada configuracion

| Configuracion | Donde | Destino en el codigo | Estado |
|---|---|---|---|
| Fichas de tipos documentales | `config/tipos/*.yaml` (repo) | `configuracion/cargador.py`, expuesto por `configuracion/servicio.py` | implementado |
| `ejemplos_referencia` de las fichas | `config/tipos/*.yaml`: fixtures del caso sano en `fixtures/generados/`, con las mismas modalidades que ya tenia cada ficha (acordado con PERSONA_3) | referencia; test de nombres en `test_configuracion.py` | implementado |
| Fixtures de prueba | `fixtures/generados/` (en `.gitignore`): **42 fixtures** (27 de los casos sano, vencido y domicilio_distinto + 3 duplicados + 12 de dificultad) + `INDICE.md`, generados en local con `scripts/generar_fixtures.py` (en `main` desde el PR #10; seccion 8). Especimenes (fotos de movil): `fixtures/especimenes/` (PR #10) | tests de `ocr.py` y del preparador; evaluacion (`evaluar_fixtures.py`); valores esperados en `INDICE.md` | generados en local |
| Asignacion de modelos por tarea | `config/modelos.yaml` (repo) | `motor_ia/enrutador.py` (`crear_enrutador`), validacion estricta | implementado |
| Barrera de privacidad | `.env`: `PERMITIR_PROVEEDORES_NO_PRIVADOS` (por defecto `false`) | `motor_ia/enrutador.py` | implementado; en `.env.example` (PR #5) |
| Nombres de los modelos de Ollama | `.env`: `OLLAMA_MODELO_TEXTO`, `OLLAMA_MODELO_VISION` | leidos por el enrutador via `modelos.yaml` (`modelo_texto_env`, `modelo_vision_env`) | implementado; en `.env.example` (PR #5) |
| URL de Ollama | `.env`: `OLLAMA_BASE_URL` | la lee el enrutador y la pasa a `OllamaProvider(base_url, ...)` | implementado |
| Proveedor comercial (respaldo) | `.env`: `PROVEEDOR_COMERCIAL_*` (ADR-003) | `motor_ia/proveedores/openrouter.py` | pendiente (cuenta sin crear) |
| Carpeta de configuracion | `.env` opcional: `CONFIG_DIR`; por defecto `config/` de la raiz del repo | `configuracion/cargador.py` | implementado; en `.env.example` |
| Carpeta de prompts | `.env` opcional: `PROMPTS_DIR` (en Docker, `/prompts`); por defecto `prompts/` de la raiz del repo | `motor_ia/prompts.py` | implementado; en `.env.example` (PR #5) |
| Prompts versionados | `prompts/<id>_<version>.md` (repo), con frontmatter `id`, `version`, `salida` | `motor_ia/prompts.py` (`renderizar`) | implementado: v1, v2 y v3 |
| Version vigente de cada prompt | constante `VERSIONES_VIGENTES` en `motor_ia/prompts.py` (`clasificacion: v2`, `extraccion: v3`, `correccion_json: v1`) | `motor_ia/prompts.py` | implementado |
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
| Embeddings (base de conocimiento) | `nomic-embed-text` (plan) | `OLLAMA_MODELO_EMBEDDINGS` (propuesta) | sin probar | fuera del MVP (R10, seccion 16) |

Valor de `OLLAMA_BASE_URL` segun donde corre el backend (o el CLI) y donde corre Ollama:

| Backend / CLI | Ollama | `OLLAMA_BASE_URL` | Uso |
|---|---|---|---|
| En local (venv, fuera de Docker) | Instalado en la misma maquina | `http://localhost:11434` | Desarrollo y CLI de la etapa 1. Valor del `.env` local de PERSONA_2 |
| Dentro de un contenedor | Instalado en el Windows anfitrion (Docker Desktop) | `http://host.docker.internal:11434` | Backend en docker compose sin levantar el servicio `ollama`. **Valor por defecto de `.env.example`** (revision de PERSONA_1: desde el PR #3 `ollama` es un perfil opcional y `docker compose up` normal no lo arranca) |
| Dentro de un contenedor | Servicio `ollama` de docker-compose | `http://ollama:11434` | Solo con `docker compose --profile ollama up`; con `docker compose up` normal no resuelve |

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

Regla (decidida el 2026-10-01, sustituye a "texto si `pdf_digital`"): **modelo de texto, sin imagenes, si
TODAS las paginas tienen al menos 30 caracteres de texto (capa del PDF u OCR), sin contar espacios; modelo de
vision si alguna no llega.** Se aplica a clasificacion y a extraccion, sea cual sea la modalidad.
`MIN_CARACTERES_TEXTO_POR_PAGINA = 30` en `proveedores/base.py`, igual que
`UMBRAL_CARACTERES_POR_PAGINA` de `modalidad.py` (un test lo comprueba).

**Reintento con vision** (mitigacion del riesgo 2 de `PLAN_PROYECTO.md`: fotos con OCR malo -> vision): si la
extraccion con texto deja a `null` **la mitad o mas de los campos obligatorios** de la ficha
(`FRACCION_OBLIGATORIOS_VACIOS_REINTENTO = 0.5`) y el documento tiene imagenes, se repite la extraccion con
vision. Manda el resultado de vision; el de texto solo rellena los campos que la vision deja a `null`. Si el
reintento falla, se conserva el resultado con texto. La clasificacion no se reintenta.

**OCR pobre y paso a vision** (decidido el 2026-10-01 con los bloques 3 y 4 de la evaluacion; lo decide el
servicio, `motor_ia/servicio.py`, que conoce la clasificacion). Un OCR es pobre si se da cualquiera de estas
senales:

| Senal | Cuando | Que se hace |
|---|---|---|
| 1. Texto insuficiente | Antes del modelo: alguna pagina con menos de 30 caracteres | Vision directamente (regla de arriba) |
| 2. Clasificacion `desconocido` | Tras clasificar con texto, si el documento tiene imagenes | **Se reclasifica con vision** (`clasificar_con_vision`) y `CLS-001` se decide con esa clasificacion. Si la vision confirma el declarado: sin `CLS-001` y extraccion **directa con vision**. Si da otro tipo concreto: `CLS-001` y extraccion con texto, sin reintento. Si tambien da `desconocido`: `CLS-001` (si hay declarado) y extraccion directa con vision con la ficha del declarado. Sin declarado, se extrae con la ficha que da la vision |
| 3. Obligatorios vacios | Tras extraer con texto: la mitad o mas de los obligatorios a `null` | **Reintento de extraccion con vision** |
| 4. Formato invalido | Tras extraer con texto: algun campo con valor que no cumple el `patron` de la ficha, no es una fecha valida o no es un anio de 4 cifras (`campos_con_formato_invalido`) | **Reintento de extraccion con vision** |

- En el reintento manda la vision y el texto solo rellena los campos que la vision deja a `null`. Si el
  reintento o la reclasificacion fallan, se conserva el resultado con texto.
- **No se reintenta si salta `CLS-001` con un tipo concreto distinto del declarado** (hallazgo del bloque 1): se
  extrajo con la ficha del declarado y los vacios o formatos invalidos se explican por el tipo. Con `tipo_confirmado`
  no hay clasificacion ni `CLS-001`, asi que si se reintenta.
- El proveedor solo expone `clasificar_con_vision(...)` y `extraer_con_vision(...)`; `clasificar()` y `extraer()`
  no reintentan. El servicio solo actua si la llamada fue con texto (`entrada == "texto"`), el proveedor tiene el
  metodo y el documento tiene imagenes.
- Medido (bloque 3 repetido el 2026-10-01, con `extraccion_v3`): dificil 31/34 correctos y 2 incorrectos (antes
  19/34 y 7); extremo 28/34 y 6 incorrectos (antes 9/34 y 10); tipo correcto 6/6 y 6/6 (antes 6/6 y 2/6); vacios 1
  (antes 23); ~150 s por caso (antes ~63-82 s). Nivel normal (bloque 1 repetido): 153/153, 59,4 s de media, ningun
  caso usa vision. Sin cubrir: errores sin senal (p. ej. `GALLE FICTICIA 123`, comprobante escaneado extremo 1/4);
  para eso, la confianza de Tesseract (pendiente).

Registro: cada llamada (`InfoLlamada`) lleva `entrada` (`texto` o `vision`) y `motivo`, y el servicio registra
todas en `Analisis.llamadas`. Motivos:
`reclasificacion con vision: la clasificacion con texto dio desconocido`;
`extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido)`;
`reintento con vision: 3/4 campos obligatorios vacios con texto`,
`reintento con vision: formato invalido en curp con texto` o las dos senales separadas por `;`;
si no se reintenta por `CLS-001`, la llamada de texto lleva `sin reintento con vision (<senales>): el tipo
declarado no coincide con el detectado (CLS-001)`; si la vision falla, `...; fallo (...): se conserva el
resultado con texto` (o la clasificacion con texto). `fecha_y_modelo_utilizado.modelo` es el modelo del resultado que se usa (el de vision si el
reintento funciona; el de texto si no se reintenta o el reintento falla).

Se decide sin ADR: `Enrutador.obtener(tarea, tipo)` (Contrato 3) devuelve el proveedor configurado y el
proveedor elige su modelo (`OllamaProvider.modelo_para`, `usa_texto`). Datos: `pruebas_ollama.md`,
"Alternativas para documentos sin capa de texto". Documentado en `backend/app/modulos/motor_ia/README.md`.

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
| Modalidad | Que prepara el orquestador | Modelo habitual | Cuando va a vision |
|---|---|---|---|
| `pdf_digital` | Texto por pagina (PyMuPDF) + PNG a 150 dpi | texto `gemma4:e2b` (todas las paginas superan el umbral por definicion) | Solo como reintento si la extraccion sale muy incompleta |
| `pdf_escaneado` | PNG a 200 dpi; por pagina, capa de texto si supera el umbral (PDF mixto) y OCR si no | texto `gemma4:e2b` con el texto OCR, si todas las paginas lo superan | Alguna pagina sin texto suficiente (p. ej. sin Tesseract) o reintento: `qwen2.5vl:3b` con las imagenes a 1000 px + el texto en `{{ contenido }}` |
| `imagen` | La propia imagen, orientada segun EXIF y en PNG, + OCR | igual que `pdf_escaneado` | igual que `pdf_escaneado` |

Respaldo: si el proveedor principal falla, se usa el `respaldo` de `modelos.yaml` (OpenRouter
gratuito, ADR-003, solo con fixtures ficticios). Sin respaldo disponible: `estado_analisis=error` +
`SYS-001`.

## 4. Reglas de vision y parseo

| Regla | Valor | Motivo | Donde | Test |
|---|---|---|---|---|
| Fechas | El prompt pide las fechas **tal como aparecen**; el codigo las normaliza con `normalizar_fecha` (dia/mes/anio -> `AAAA-MM-DD`, separadores `/ . -` y espacio; ISO valido se deja igual; fecha imposible -> `None`) | Al convertirlas, `qwen2.5vl:3b` intercambia dia y mes (`10/05/2024` -> `2024-10-05`). Sin convertir: 3/3 correctas en 4 de 4 | `motor_ia/proveedores/base.py` (tarea 7). Referencia: `pruebas_ollama/prueba_fechas.py` | unitario con los 11 casos del autotest |
| Tamano de imagen | `ANCHO_MAX_IMAGEN = 1000`: `reducir_imagen` antes de enviar; solo reduce y mantiene la proporcion | Sube los aciertos de 5/7 a 6/7 y ahorra ~20 % de tiempo; 800 px no mejora | `proveedores/base.py` | unitario |
| Lotes de vision | `MAX_PAGINAS_POR_LLAMADA_VISION = 4`. Con mas paginas no se ignora ninguna: se procesan por lotes de 4 y se combinan (`combinar_lotes`). Por campo, el valor no nulo con evidencia valida; ante empate, el de la pagina mas baja; si ningun lote tiene evidencia valida, el primer valor no nulo. La clasificacion solo usa el primer lote. En un lote, `pagina_1..k` relativa a las imagenes enviadas se traduce a la pagina real | Cada pagina A4 a 1000 px suma ~1 850 tokens y ~130 s en CPU | `proveedores/base.py`, `proveedores/ollama.py` | unitario con Ollama simulado |
| Contexto | `NUM_CTX = 16384`. Medido (`pruebas_ollama/prueba_num_ctx.py`): 1 pagina A4 + prompt = 2 457 tokens; 4 paginas + prompt + 20 000 caracteres = 13 476; con `NUM_PREDICT` quedan ~2 100 de margen (13 %) | Si no se fija, Ollama usa un contexto menor y recorta la entrada sin avisar. **Se mantiene fijo** (2026-10-01): bajarlo a 8192 solo ahorra ~0,3 GB del modelo y ~0,1 GB de consumo real, y la vision pasa a ser el caso poco frecuente | `proveedores/base.py` | unitario del cuerpo de la peticion |
| Timeouts | Texto: 120 s. Vision: 60 s + 150 s por imagen (4 imagenes -> 660 s). El reintento de correccion, sin imagenes, usa el de texto | Medido: 4 paginas = 499 s solo de lectura del prompt; un timeout fijo de 300 s fallaria siempre | `proveedores/base.py` (`timeout_vision`) | unitario |
| Texto largo | `MAX_CARACTERES_TEXTO = 20000`: `recortar_texto` respeta el orden de las paginas y marca `[texto recortado]`. Si se recorta, alerta **`SYS-003`** (preventiva): "El texto del documento supera `MAX_CARACTERES_TEXTO` y se ha recortado; los campos de las paginas finales pueden no haberse extraido". En el catalogo desde el PR #4 (`docs/adr-007-y-alertas`, fusionado en `main`) | Mantener el prompt dentro de `NUM_CTX` | `proveedores/base.py`; la alerta, en `motor_ia/servicio.py` (tarea 9) | unitario |
| Evidencia | Valida: `pagina_<n>[:detalle]` de una pagina del documento. En vision solo `pagina_<n>`; en texto se conserva el detalle (p. ej. `pagina_1:Fecha de caducidad`). Si es invalida, se quita: el Contrato 1 no admite valores nulos | `qwen2.5vl:3b` copia la seccion del ejemplo o devuelve `seccion_superior` sin pagina | `proveedores/base.py` | unitario con respuestas guardadas |
| Campos y tipos | Solo se conservan los campos de la ficha (`qwen` anadio `tipo` y `pais_emisor`); un campo ausente queda `null` con confianza 0. **`""` y los textos solo con espacios (incluidos tabuladores, saltos de linea y espacio duro) pasan a `null`** con confianza 0 y sin evidencia, en cualquier tipo de campo, para que `VAL-001` y `VAL-004` los vean como ausentes (acordado con PERSONA_3). `anio` de 4 cifras -> entero; si no, texto original con confianza 0. Los valores que no son texto se convierten a texto | La regla `anio_mayor_o_igual_actual` compara numeros | `proveedores/base.py` | unitario |
| Fecha no normalizable | Se conserva el texto original con confianza 0 (p. ej. `"mayo 2034"`). **Las reglas de fecha de la etapa 2 deben tratarlo como fecha invalida y generar una alerta, sin fallar** | Que el revisor vea el dato y no salte un falso `VAL-001` (obligatorio ausente) | `proveedores/base.py`; reglas en `validacion/reglas.py` (etapa 2) | unitario |
| Clasificacion fuera de la lista | Un tipo que no esta entre los posibles pasa a `desconocido` con confianza 0; se ignoran mayusculas y espacios | El modelo puede inventar tipos | `proveedores/base.py` | unitario |
| Confianza del modelo | **No se usa en las reglas.** ADR-007 **aceptado** (2026-09-30) e **implementado** (etapa 2): `nivel_confianza_por_campo` y `confianza_clasificacion` las calcula el codigo (seccion 14) y la del modelo va solo a la auditoria (`Analisis.confianzas_modelo`) | Siempre 0,9 o 1, tambien en datos mal leidos o inventados | `motor_ia/confianza.py`, `motor_ia/servicio.py` | `test_confianza.py`, `test_servicio_motor.py` |
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
| `clasificacion_v2`, `extraccion_v2` | `clasificacion_v2` **vigente**; `extraccion_v2` en el repo (historial) | Anaden `{{ contenido }}` (texto por pagina). `extraccion_v2`: fechas tal como aparecen, formato de evidencia, bajar la confianza si hay dudas y no inventar valores (cuerpo identico al borrador v2b validado). `clasificacion_v2`: `desconocido` si no encaja claramente | `prompts/` |
| `correccion_json_v1` | vigente (implementado) | Instruccion del reintento cuando la respuesta no es valida; variable `{{ error }}` | `prompts/` |
| `extraccion_v3` | **vigente** (2026-10-01) | La v2 mas una regla: asignar cada valor por su etiqueta (en espanol o en ingles: "Date of issue" = fecha de expedicion, etc.), no por su posicion, y no dejar vacio un campo cuya etiqueta aparece. La lista de campos va **sin obligatoriedad** (variable `campos_a_extraer`, `formatear_campos`): con "opcional" qwen2.5vl dejaba vacia `fecha_expedicion` aunque se lee (sonda: A v3 con "opcional" vacia en 2/2; B sin "opcional" `30/09/2021` en 2/2; C sin texto OCR 1/2; D a 1400 px 1/2). 4 pasaportes dificiles con vision forzada: 21/28 -> 25/28 y 4 -> 0 vacios. La v2 sigue con `esquema_campos` (con obligatoriedad) | `prompts/` |
| `extraccion_v4` | pendiente (etapa 3, extra 2) | Pide `observaciones_visuales` (legibilidad, recortes, alteraciones) para las alertas `VIS-xxx`. El plan lo llamaba `extraccion_v2`; se renumera porque la v2 y la v3 ya se usan (tambien en `docs/equipo/PERSONA_2_motor_ia.md`) | - |

Reglas de `motor_ia/prompts.py`:

| Regla | Detalle |
|---|---|
| `version_prompt` (`FechaYModelo`) | Sigue el ejemplo de `resultado.py`. Extraccion: `<id>_<tipo>@<version>` (p. ej. `extraccion_pasaporte@v3`). Clasificacion, sin tipo: `clasificacion@v2` |
| Variables | Jinja con `StrictUndefined`: si falta una variable, `ErrorPrompt`. `tipo_documental` se pasa aparte y tambien es variable del prompt |
| Contenido del documento | Se inserta como valor; nunca se interpreta como plantilla (un `{{ ... }}` del documento queda literal) |
| Formato comun | `formatear_contenido` (`--- pagina_<n> ---`; `(sin texto extraido)` si no hay texto), `formatear_tipos`, `formatear_esquema` (con obligatoriedad; v1 y v2), `formatear_campos` (sin obligatoriedad; `extraccion_v3`), `formatear_contexto_rag` (`(sin contexto)` si esta vacio) |
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
| Codigos de alerta del motor | `CLS-001` (critica): tipo declarado distinto del detectado. `SYS-001` (critica): fallo del proveedor sin respaldo. `SYS-002` (critica): JSON invalido tras el reintento. `SYS-003` (preventiva): texto recortado. Informativas: `SYS-005` (motor_ia: se uso el proveedor de respaldo) y `VAL-003` (orquestador/ocr: campo tomado de la MRZ). `SYS-004` se retiro en la revision del PR #4 (la ingesta rechaza con 415) y no se reutiliza; `SYS-005` conserva su numero. Catalogo: `docs/contratos/codigos_alertas.md`; `SYS-003`, `SYS-005` y `VAL-003`, en el catalogo desde el PR #4 (`docs/adr-007-y-alertas`, fusionado en `main`). El motor no rellena `Alerta.id` | prompt de PERSONA_2, ADR-006 | `CLS-001`, `SYS-001`, `SYS-002`, `SYS-003`, `SYS-005` y `VAL-003` implementados en `motor_ia/servicio.py` (seccion 10); `CLS-002` y `VAL-002`, en la etapa 2 (deuda ADR-007) |
| `Tarea.validacion` (Contrato 3) | Se acepta en `modelos.yaml`, pero no se usa: la validacion son reglas deterministas en `validacion/reglas.py`, sin modelo. No se cambia el contrato | analisis de la etapa 0; tarea 8 | implementado (el enrutador la acepta) |
| Perfiles de modelos de `procesos.yaml` | `modelos: default` significa usar `modelos.yaml` tal cual; los perfiles por proceso **no se implementan** (reservados, fuera del MVP) | tarea 8 | decidido |
| Ficha para extraer | Se extrae con la ficha del tipo declarado; si no hay, con la del detectado. `tipo_confirmado` en `procesar_documento` manda sobre ambos (etapa 2) | ADR-006, 2.5 | decidido |
| `/tipos-documentales` | `configuracion/servicio.py` serializa `TipoDocumental` para el router de PERSONA_1 | ADR-006, 1.5 | pendiente (ver seccion 7) |
| RAG | Toda la carpeta `modulos/rag` es de PERSONA_2 desde el traspaso de PERSONA_3 (PR #13): `rag/conocimiento.py` (`buscar(consulta, k)` para `contexto_rag`), `rag/embeddings.py` (Ollama `nomic-embed-text`) y, por ADR-010 (PR #21), **solo** `rag.servicio.fragmento_resumen(folio) -> str | None`, ya enmascarado; los folios relacionados los elige PERSONA_1 con SQL (ya no hay `buscar_antecedentes` en `rag`) (H14) | ADR-006, coordinacion, PR #13, ADR-010 | memoria de folios hecha (H14, seccion 16); `rag/conocimiento.py` y `rag/embeddings.py` fuera del MVP (R10) |

## 7. Pendientes y riesgos

- [ ] **Maquina con GPU para Ollama** (riesgo 1 del plan). La VM actual (2 nucleos, 16 GB, sin GPU)
      tarda ~110 s por pagina con vision. Minimo orientativo: GPU NVIDIA con 8 GB de VRAM o mas, o
      32 GB de RAM y mas nucleos.
- [ ] **Instalar Tesseract** (`spa+eng`) en Windows; puede necesitar a TI. Plan B: OCR dentro del
      contenedor del backend.
- [x] **OCR + texto frente a vision** medido el 2026-10-01 en el contenedor: OCR + `gemma4:e2b` 7/7 en ~68 s;
      `qwen2.5vl:3b` 6/7 en ~130 s. Regla nueva del enrutador (seccion 3).
- [x] **Probar credencial de elector y comprobante de domicilio**: evaluados con los tres tipos en los bloques 1 y 3
      (`pruebas_ollama/resultados/evaluacion/informe.md`).
- [x] **Fixtures de PERSONA_3** generados en local: 42 fixtures (27 + 3 duplicados + 12 de dificultad) + `INDICE.md`;
      el generador esta en `main` desde el PR #10. `ejemplos_referencia` de las fichas apuntan al caso sano.
- [ ] **OpenRouter**: crear la cuenta gratuita y probar los prompts con fixtures ficticios (propuesto al equipo).
- [ ] **Aplicar ADR-006**: 1.5 serializar `TipoDocumental` en `configuracion/servicio.py` (para
      `/tipos-documentales`) y 2.5 `tipo_confirmado` en `procesar_documento` (etapa 2).
- [x] **Avisar al equipo del cambio en `CLAUDE.md`** (linea de la spec de PERSONA_2): avisado en la descripcion
      del PR #11 (etapa 1), con el resto de ficheros compartidos.
- [x] Aviso a PERSONA_1: `configuracion.cargar()` en el arranque de `main.py`, `ingesta/tipos.py` y las fichas como
      dict en `validacion.comparar`: en la descripcion del PR #11.
- [x] **PR unico `docs/adr-007-y-alertas` (PR #4) fusionado en `main`**: ADR-007 aceptado, `SYS-003`, `SYS-005`,
      `VAL-003` y el comentario de `resultado.py` (sin `SYS-004`, retirado en la revision).
- [x] **ADR-007 en el motor** (etapa 2, paso 1): confianza de campo y de clasificacion calculadas por el codigo,
      `CLS-002`, marcadores en el cargador y en las fichas, MRZ y calibracion (seccion 14). Falta: `VAL-002` (paso 2,
      `validacion/reglas.py`), la confianza del modelo en `datos_auditoria` (paso 4) y fusionar el PR pequeno de
      `config/tipos/*.yaml` (con el cargador nuevo: el de `main` rechaza la clave `marcadores_clasificacion`).
- [ ] **PyMuPDF no carga en el Windows de PERSONA_2**: falta el Microsoft Visual C++ Redistributable x64
      (`msvcp140.dll`). Mientras tanto, los tests se pasan en el contenedor del backend (seccion 8).
- [x] `.env` local de PERSONA_2: `OLLAMA_BASE_URL=http://localhost:11434`. Hecho el 2026-09-30.
- [ ] **Regla para `validacion/servicio.py` (etapa 2), compartido con PERSONA_1**: solo reexporta funciones; la
      logica va en `validacion/comparaciones.py` (PERSONA_1) y `validacion/reglas.py` (PERSONA_2). Antes de crear o
      tocar `validacion/servicio.py` o `reglas.py`: `git fetch` y `git merge origin/main`. Si PERSONA_1 ya lo creo,
      anadir solo la linea de import de PERSONA_2 en su bloque, sin reescribir el fichero. Si hay conflicto, parar
      y ensenarlo antes de resolver.
- [x] **Etapa 2, paso 4: `orquestador.servicio.procesar_documento`** (seccion 11), con la MRZ en el orquestador
      (`completar_mrz.py`) y `motor_ia` sin importar `orquestador` (test). Ya con ADR-007 aplicado (H10): PERSONA_1
      puede sustituir el stub de la ingesta (paso 5).
- [x] **Valor reservado `desconocido`: ADR-009 ACEPTADO** (2026-10-02, PERSONA_1 en la revision del PR #14 y
      PERSONA_2); ver seccion 10. El PR #14 se fusiono con el ADR aun en PROPUESTO y sin `EXP-002`; la version
      aceptada, con `EXP-002` y `EXP-001` tambien sin tipo declarado, esta en `main` desde el PR #17.
- [ ] **Aplicar ADR-009** (PERSONA_2): PR de contratos con el comentario de `resultado.py` y la linea de
      `endpoints.md` (antes de la etapa 2), y en la etapa 2 el cargador rechaza una ficha llamada `desconocido`
      (con test). PERSONA_1: mensaje de `EXP-002` y UI.
- [ ] **Notas para la etapa 2** (revision de PERSONA_3 en el PR #11):
      - (a) `procesar_documento` **no sustituye al stub** de la ingesta (`ingesta/motor_stub.py`) hasta que la
        confianza la calcule el codigo (ADR-007): la UI la muestra como "Confianza verificada", y hoy es la del
        modelo (provisional, siempre 0,9-1).
      - (b) Anadir la **version del prompt de clasificacion** a `datos_auditoria` (hoy `version_prompt` solo es
        el de la extraccion; si no hubo extraccion, el de la clasificacion).
      - (c) Cuando llegue `openrouter.py`, formalizar con un ADR en `interfaces.py` (Contrato 3, congelado)
        `extraer_con_vision`, `clasificar_con_vision` y `ultima_llamada`/`ultimas_llamadas`. Hoy son metodos de
        `OllamaProvider` que el servicio usa solo si existen (`hasattr`/`getattr`), sin cambiar el contrato.
- [x] ~~`CLS-003` para "tipo desconocido sin declarado ni confirmado"~~: no hace falta. El ADR-009 reutiliza
      `EXP-002` (informativa, del expediente), que ya sale en ese caso (seccion 10).
- [x] **`validacion/reglas.py`** (etapa 2, paso 2): `evaluar_reglas` con `VAL-001`, `VAL-002`, `VAL-004`, los tipos de
      regla de los YAML y las fechas no normalizables (incumplen sus reglas, sin fallar). Seccion 15.
- [ ] **Reglas de coherencia en las fichas** (PR pequeno de `config/tipos/*.yaml`, con aviso): los tipos
      `curp_coincide_con_fecha` y `fecha_anterior_a_campo` ya estan en el cargador, en `reglas.py` y en el evaluador de
      `generar_fixtures.py` (H13), pero **ninguna ficha los usa todavia**. Anadirlos a los YAML obliga a regenerar los
      mocks del frontend (`frontend/src/mocks/datos/folios.json` y `tipos_documentales.json`, con
      `scripts/generar_datos_mock.py`): el frontend es de PERSONA_1 desde el traspaso. **Decidido** (2026-10-02): PR
      pequeno aparte desde `origin/main` cuando esten fusionados los PR #18 (marcadores) y #19 (de PERSONA_1); se abre
      junto con PERSONA_1. `campo_relacionado` **cambia el Contrato 2**: el PR lleva tambien la linea de
      `docs/contratos/endpoints.md`, el tipo en `frontend/src/tipos/contrato.ts` y la clave en `_regla` de
      `ingesta/tipos.py`, y debe pasar `test_openapi_contrato.py`. Borrador local: `chore/reglas-coherencia` (`ecea1b0`).
      Reglas propuestas (severidad `critica`): credencial `curp_coincide_nacimiento` (`curp` con `fecha_nacimiento`);
      pasaporte `nacimiento_antes_de_expedicion`, `expedicion_antes_de_vencimiento` y `nacimiento_antes_de_vencimiento`
      (la tercera cubre la expedicion vacia). Medido con los resultados de la evaluacion (sin modelo): no suben los
      incorrectos marcados (4/12 con y sin ellas). Las dos CURP mal leidas ya llevaban `VAL-002`, y el error
      "nacimiento = expedicion" del bloque 3 desaparecio con `extraccion_v3`. Siguen detectando ese tipo de error (tests).
- [ ] `NUM_CTX` con documentos reales: el margen medido es del 13 %; revisarlo si hay paginas mas altas que
      A4 (p. ej. oficio) o texto que tokenice peor que el de relleno usado en la medida.
- [x] **Vision con los fixtures escaneado y foto**: ejecutada el 2026-10-01 con `analizar()` (alternativa B,
      `qwen2.5vl:3b`): 6/7 en ambos; para 1 pagina bastan ~5,8 GB libres. Con la regla nueva, esos fixtures van
      a texto con OCR (7/7).
- [ ] **Mejorar la evidencia del prompt de extraccion** (etapa 2): en la ejecucion real, `gemma4:e2b` devolvio
      `pagina_1:seccion_central` en los 7 campos; es valida, pero no dice donde esta cada dato.
- [x] **Documentos de uno en uno y `OLLAMA_MAX_LOADED_MODELS=1`: resuelto por PERSONA_1 en el PR #9** (en `main`,
      `eee95be`): la ingesta llama al motor dentro de un semaforo de `MAX_PROCESAMIENTOS_SIMULTANEOS` (1 por
      defecto; `.env.example`) y su README pide arrancar Ollama con `OLLAMA_MAX_LOADED_MODELS=1`. PERSONA_2: anadir
      `MAX_PROCESAMIENTOS_SIMULTANEOS=1` a su `.env`. Contexto original (configuracion del servidor, sin codigo):
      con el reintento con vision, Ollama tendria cargados a la vez `gemma4:e2b` (~3 GB) y `qwen2.5vl:3b`
      (~4,3 GB), y una maquina de 16 GB se queda sin RAM. Con la variable, descarga un modelo al cargar otro.
      En la evaluacion (`pruebas_ollama/evaluar_fixtures.py`) se descarga el de texto antes del reintento
      (`keep_alive: 0`) y queda anotado en el informe. Revisarlo en la maquina con GPU.
- [x] **Hallazgo del bloque 3**: `CLS-001` bloqueaba el reintento cuando el texto daba `desconocido`. Resuelto con
      la regla de OCR pobre (seccion 3): reclasificacion con vision y `CLS-001` decidido con ella.
- [ ] **Senal 5 de OCR pobre: confianza por palabra de Tesseract** (`image_to_data` en `orquestador/ocr.py`), para
      los errores sin senal (p. ej. `GALLE FICTICIA 123`). Despues de probar con los especimenes; calibrar con los
      fixtures normales, dificiles y los especimenes.
- [ ] **Traspaso de PERSONA_3** (dejo el equipo el 2026-10-01; PR #13, `docs/equipo/PERSONA_3_estado.md`,
      `docs/PLAN_PROYECTO.md` seccion 8). Tareas heredadas por PERSONA_2:
      - [x] H9: ADR-009 (`desconocido`), aceptado (PR #14 y #17).
      - [x] H10: el stub no se sustituye hasta ADR-007 (decidido; ver "Notas para la etapa 2").
      - [x] H11: formato estable de `INDICE.md` documentado en `fixtures/README.md` (elementos que leen
        `test_fixtures_ocr.py`, `evaluar_fixtures.py` y `verificar_ocr_fixtures.py`, y comprobacion tras cambiarlo).
      - [x] H12: tiempo maximo por documento (seccion 13).
      - [ ] H13: mantener `generar_fixtures.py` (tipos de regla nuevos en su evaluador), `verificar_ocr_fixtures.py`
        (mismo preprocesado que `orquestador/ocr.py`) y `procesar_especimenes.py`. Versiones de PyMuPDF (1.28.2) y Pillow
        (12.3.0) fijadas con `==` en `backend/requirements.txt` (rama `chore/fijar-pymupdf-pillow`, PR #35, fusionado): son las del
        contenedor y las de `sha256_fixtures_existentes.txt`.
      - [x] H14 (redefinido por ADR-010, PR #21): **ya no es `buscar_antecedentes`**. `rag.servicio.indexar_resumen(folio,
        resumen_md)` y `fragmento_resumen(folio)`, **sin embeddings** (seccion 16; PR #37). Conectado por PERSONA_1 en el
        #39: migracion `0005`, `avisar_reindexar` llama a `indexar_resumen` y `scripts/reindexar_resumenes.py`.
      - [x] H15 (ADR-010, A1 y A6; rama `feat/sensible`, despues del PR de reglas de coherencia): `Campo.sensible`
        en el cargador (booleano, por defecto `false`) y `sensible: true` solo en `curp`, `clave_elector` y
        `numero_pasaporte` (R8). **Cambia el Contrato 2**: `sensible` siempre presente en `CampoFicha` de
        `GET /tipos-documentales` (`endpoints.md`, `contrato.ts`, `_campo` de `ingesta/tipos.py` y `CampoTipo` del
        router). Test `test_sin_valores_en_logs.py`: los logs del motor y `datos_auditoria` no llevan valores de los
        campos (normal, proveedor caido, JSON invalido y sexo desde la MRZ). Mocks regenerados con
        `scripts/generar_datos_mock.py` (solo `tipos_documentales.json`). Con la rama `chore/mocks-sensible`
        (`e24e757`, PR pendiente) el script pone `sensible` en todos los campos, igual que la API.
      Recortes aceptados que afectan al motor: R4 (`VIS-xxx` solo si el dia 11 el hito y la memoria estan en
      verde), R5 (no se repiten las fotos de especimenes descartadas), R6 (`openrouter.py` al final de la etapa 3,
      opcional en la demo) y R8 (enmascaramiento solo de CURP, numero de pasaporte y clave de elector; ADR-010).
- [x] **Especimenes** (`fixtures/especimenes/`, 5 fotos de movil de los documentos sanos impresos): bloque 5 de
      `evaluar_fixtures.py` con el flujo completo (`procesar_documento`), 2026-10-05: **27/27 campos**, tipo 5/5, 0
      incorrectos (informe en `pruebas_ollama/resultados/especimenes/`). Los 4 con texto: `aprobar`, 59-72 s. El
      comprobante "dificil" (13 caracteres de OCR) va por vision: 4/4 correctos en 225 s, pero `revision_manual` con
      `CLS-002` y `VAL-002` en sus 4 campos: sin texto no se puede verificar nada (ADR-007). RAM libre minima 1,41 GB.
      **Aviso: sus fechas impresas no cambian; desde el 2026-12-15 el comprobante dara `REG-antiguedad_maxima`**
      (critica).
- [x] **RAM con dos modelos cargados, confirmado en el bloque 3**: un documento con 15 caracteres de OCR fue directo
      a vision con `gemma4:e2b` aun cargado y la RAM bajo a 0,99 GB. En la evaluacion se descarga el otro modelo en
      cada cambio; en produccion, semaforo y `OLLAMA_MAX_LOADED_MODELS=1` del PR #9 de PERSONA_1.
- [ ] **Opcional: bloque 2 de la evaluacion** (`pruebas_ollama/evaluar_fixtures.py lanzar --bloque 2`): vision
      forzada en los 18 escaneados y fotos, como referencia del respaldo (~40-45 min; criterio >= 40/51 por
      modalidad, no bloquea). El bloque 1 (ruta auto) aprobo todo el 2026-10-01.
- [ ] Riesgo: la confianza que da el modelo no es fiable (0,9-1 incluso en datos inventados).
- [ ] Riesgo: el modelo no es determinista ni con `temperature: 0`.
- [x] Borrar `qwen2.5:7b` de Ollama local (4,7 GB, descartado). Hecho el 2026-09-30.

## 8. Como pasar los tests

| Entorno | Comando (desde la raiz del repo) | Notas |
|---|---|---|
| Contenedor del backend (recomendado) | `docker compose build backend` y despues `MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" -v "<repo>/fixtures:/fixtures:ro" -v "<repo>/frontend:/frontend:ro" -v "<repo>/docs:/docs:ro" backend python -m pytest -q` | Incluye PyMuPDF y Tesseract. `--no-deps` no levanta `db` ni `ollama`; `--rm` borra el contenedor al terminar. Los tests buscan la raiz del repo en `/`: `scripts/` (p. ej. `crear_usuario.py` de PERSONA_1), `fixtures/` (integracion OCR y especimenes), `frontend/` (contrato del frontend y mocks) y `docs/` (`codigos_alertas.md`). Sin alguno, sus tests se saltan o fallan. Resultado el 2026-10-01: 670 pasan y 2 se saltan (requieren `TEST_POSTGRES_URL`). Reconstruir la imagen si cambia `requirements.txt`. Requiere `.env` y Docker Desktop en marcha |
| venv local | `cd backend && .venv/Scripts/python -m pytest -q` | En Windows necesita el Visual C++ Redistributable x64 para PyMuPDF |
| Solo la integracion OCR | `MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures:ro" backend python -m pytest -q tests/test_fixtures_ocr.py` | `test_fixtures_ocr.py` busca `FIXTURES_DIR`, `/fixtures/generados` o `fixtures/generados` del repo; sin fixtures o sin Tesseract se salta. Solo usa los casos y el nivel conocidos (sano, vencido y domicilio_distinto en digital, escaneado y foto): no se rompe si se anaden fixtures |

Generar los fixtures de PERSONA_3 (el script esta en `main` desde el PR #10; desde la raiz del repo, en Git Bash):

```
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures" \
  -v "<repo>/scripts:/scripts:ro" backend python /scripts/generar_fixtures.py --hoy AAAA-MM-DD
```

El script calcula sus rutas desde su ubicacion: montado en `/scripts`, lee `/config` y escribe en
`/fixtures/generados`. Con el mismo `--hoy`, los ficheros salen identicos byte a byte.

## 9. OCR (`orquestador/ocr.py`, tarea 3)

Implementado: `ocr.py` (`OCRProvider`, `TesseractOCR`), `mrz.py` y `preparador.py`. Resultado con los 27 fixtures
de los casos conocidos en nivel normal (`test_fixtures_ocr.py`, 2026-09-30): **151/153 campos**, por encima de la linea base (en `pdf_digital` se usa
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
| `CLS-001` (critica) | Hay tipo declarado y el detectado es distinto, incluido `desconocido`. Si el texto da `desconocido` y hay imagenes, se decide con la reclasificacion con vision (seccion 3) |
| Valor reservado `desconocido` | `tipo_documental_detectado = "desconocido"` significa "clasificado, pero no encaja en ninguna ficha" (`DESCONOCIDO` en `proveedores/base.py`). **El contrato no lo recoge**: `resultado.py` solo dice `str \| None` y `endpoints.md` no lo menciona; `null` es otra cosa (no se clasifico: `tipo_confirmado` o error antes de clasificar). **ADR-009 ACEPTADO** (2026-10-02): valor reservado, distinto de `null`; ninguna ficha puede llamarse asi (el cargador lo rechazara); los consumidores no lo tratan como nombre de ficha; en el expediente no cubre ningun tipo requerido (`_tipo_efectivo`) hasta que el revisor confirme el tipo, y emite `EXP-002` (no esta en `tipos_requeridos` ni en `tipos_opcionales`). Alertas de un documento `desconocido`: con declarado, `CLS-001` + `EXP-001` (si al folio le falta algun tipo requerido) + `EXP-002`; sin declarado ni confirmado, `EXP-001` (si al folio le falta algun requerido) + `EXP-002`; con tipo confirmado, ninguna (no se clasifica). Sin codigos nuevos (PR #14 y #17) |
| Ficha para extraer | `tipo_confirmado` > declarado > detectado (ADR-006, 2.5). Un tipo declarado o confirmado que no existe lanza `TipoNoEncontrado` (la ingesta lo valida antes) |
| Tipo desconocido sin declarado ni confirmado | Se reclasifica con vision si hay imagenes; si da un tipo concreto, se extrae con esa ficha. Si sigue `desconocido` (o no hay imagenes): **no se extrae y el motor no emite alerta**, `completado` con datos vacios. La senal para el revisor es `EXP-002` (informativa), que emite el expediente (ADR-009) |
| Extraccion | Prompt `extraccion_v3` con la lista de campos de la ficha (`campos_a_extraer`); `version_prompt` `extraccion_<tipo>@v3` |
| Sexo desde la MRZ | **Lo hace el orquestador** (`orquestador/completar_mrz.py`, dentro de `procesar_documento`), no `analizar`; `analizar` recibe la MRZ (`mrz=`) solo para la confianza. Solo `pasaporte` y solo si `sexo` llega `null`: posicion 21 de la linea 2, evidencia `pagina_<n>` de la pagina con la MRZ y `VAL-003` (informativa, `campo=sexo`). Confianza calculada (seccion 14): 1,0 si los digitos de control cuadran; como mucho 0,5 si alguno falla |
| OCR pobre y vision | Ver seccion 3: reclasificacion con vision (`_reclasificar_con_vision`) y reintento (`_reintento_vision`); no se reintenta si salta `CLS-001` con un tipo concreto |
| Respaldo | Si el principal lanza `ErrorProveedor` (incluido JSON invalido tras el reintento), se prueba el respaldo; si funciona, `SYS-005` (informativa), una sola vez por documento |
| Sin respaldo o falla tambien | `estado_analisis=error` + `SYS-002` si el ultimo fallo fue JSON invalido, `SYS-001` si no (criticas). Si la clasificacion salio bien, se conserva |
| `fecha_y_modelo_utilizado` | Proveedor, **modelo real** (`ultima_llamada.modelo`) y `version_prompt` de la extraccion; si no hubo extraccion, los de la clasificacion; `None` si no hubo ninguna llamada correcta |
| `Alerta.confianza` | **1,0** en las alertas deterministas (`CLS-001`, `SYS-00x`, `VAL-003`) |
| Alertas repetidas | Nunca dos con el mismo (`codigo`, `campo`) en un documento (ADR-006, 1.3) |
| Confianzas (ADR-007) | Calculadas por el codigo (seccion 14); la del modelo, en `Analisis.confianzas_modelo`. `CLS-002` lo emite el motor; `VAL-002`, `validacion/reglas.py` (paso 2). Con `tipo_confirmado`, `confianza_clasificacion = None` (ADR-009; el 1,0 lo pone la plataforma, D2) |
| Fuera de esta tarea (etapa 2) | `reglas_cumplidas_e_incumplidas`, `VAL-001`, `VAL-002`, `VAL-004` y `REG-*` (en `validacion/reglas.py`, seccion 15), `recomendacion` y `procesar_documento` |

## 11. Integracion con la plataforma (etapa 2)

Acuerdo cerrado con PERSONA_1 el 2026-09-30. **Implementado** en la etapa 2, paso 4 (`orquestador/procesamiento.py`).

| Punto | Acuerdo |
|---|---|
| Firma | `app.modulos.orquestador.servicio.procesar_documento(contenido, *, identificador, nombre_archivo, tipo_declarado, folio, referencia, tipo_confirmado=None) -> (ResultadoDocumento, datos_auditoria)` |
| Alcance | No toca la BD ni S3: recibe los bytes del original y devuelve el resultado. PERSONA_1 descarga el original, gestiona los estados (`pendiente -> procesando -> completado/error`), guarda el resultado, inserta cada alerta en la tabla `alertas` y audita |
| `datos_auditoria` | `{modelo, proveedor, version_prompt, version_prompt_clasificacion, respaldo_usado, confianzas_modelo, tiempos: {segundos_modelo}, tokens: {entrada, salida}, llamadas: [{proveedor, modelo, entrada, motivo, segundos, tokens_entrada, tokens_salida, peticiones, reintentos, lotes}], modalidad, paginas}`. Todo serializable a JSON y sin datos del documento. `modelo` y `version_prompt` van a sus columnas; el resto, a `detalle`. Sale de `Analisis` (llamadas, confianzas del modelo, version del prompt de clasificacion) |
| Pasos | `preparar` -> verificacion de la MRZ -> `motor_ia.analizar(..., mrz=)` -> completar el sexo (`VAL-003`) -> `validacion.evaluar_reglas` (con `hoy` de `orquestador/reloj.py`) -> `validacion.recomendar_documento`. Las alertas del motor y las de las reglas se unen sin repetir (`codigo`, `campo`). Con `estado_analisis=error` o sin ficha (desconocido sin tipo) no se evaluan reglas y la recomendacion es `revision_manual` |
| Parametros extra | `enrutador=` y `ahora=` (opcionales, por nombre) para los tests y el CLI; la firma de la plataforma no cambia (test contra `ingesta/motor_stub.py`) |
| Errores | Proveedor caido o sin respaldo -> `estado_analisis=error` + `SYS-001`. JSON invalido -> `error` + `SYS-002`. Cualquier otra cosa inesperada lanza excepcion (PERSONA_1 la registra y pone el documento en `error`) |
| Reparto de alertas y recomendaciones | PERSONA_2: `VAL-*`, `REG-*`, `CLS-*` y la recomendacion **por documento**. PERSONA_1: `CMP-001`, `EXP-001` y la recomendacion **global** del expediente |
| `evaluar_reglas` (validacion) | **Firma aceptada por PERSONA_1** (2026-10-02): `validacion.servicio.evaluar_reglas(datos_extraidos, confianzas, ficha, *, hoy) -> (list[Alerta], Reglas)`. Pura (sin BD, S3 ni modelo); solo emite `VAL-001`, `VAL-002`, `VAL-004` y `REG-*`, nunca `VAL-003`, `CLS`, `SYS`, `DUP`, `EXP` ni `CMP`; alertas con `campo`, confianza 1,0, sin `id`, como mucho una por (`codigo`, `campo`); una regla sobre un campo vacio no se evalua ni se lista (D8); cada regla tal cual esta escrita (D9). PERSONA_1 la llama tras cada correccion (D3) con la ficha como `TipoDocumental` (`configuracion.servicio.obtener` del tipo de extraccion) y las confianzas con 1,0 en los corregidos; sustituye en la version vigente las VAL/REG sin revisar o confirmadas por las nuevas (conserva los falsos positivos, `aplica=false`), actualiza `reglas_cumplidas_e_incumplidas` con el `Reglas` devuelto y, al corregir un campo con `VAL-003`, borra su `VAL-003` sin revisar |
| "Hoy" de las reglas de fecha | `procesar_documento` calcula `hoy` con la zona horaria de la plataforma: variable de entorno `ZONA_HORARIA` (por defecto `America/Mexico_City`), `datetime.now(ZoneInfo(zona)).date()`, en `orquestador/reloj.py` (`hoy()`). **No importa `core.config`** (ADR-005). Zona desconocida -> `ValueError`. Test: cerca de medianoche (05:30 UTC = 23:30 en Ciudad de Mexico) da la fecha de la zona, no la UTC (`test_reloj.py`). Requisito de PERSONA_1 (2026-10-02) |
| Confianza de clasificacion con tipo confirmado | El motor no clasifica: `tipo_documental_detectado = None` y `confianza_clasificacion = None` (ADR-009; igual que el stub del PR #19). **El 1,0 lo pone la plataforma** (D2), que ademas trata como 1,0 cualquier documento con tipo confirmado en la recomendacion global. `recomendar_documento` tambien cuenta como 1,0 esa confianza `None` si hay tipo confirmado |
| Recomendacion del documento | Solo `aprobar` o `revision_manual`; **nunca `rechazar`** (D1, aceptado en el PR #13; `codigos_alertas.md` no cambia) |

**Importacion circular resuelta** (paso 4): la dependencia va en un solo sentido, `orquestador -> motor_ia`.
Lo que se decidio:
- Mover la completacion del sexo desde la MRZ (hoy `_sexo_desde_mrz` en `motor_ia/servicio.py`) a
  `orquestador`, que la aplica despues de `analizar()` dentro de `procesar_documento`. Encaja con el
  catalogo, que ya da `VAL-003` como emitida por `orquestador (ocr)`.
- `motor_ia/servicio.py` deja de importar `orquestador`: solo hace IA (clasificar, extraer, respaldo).
- `procesar_documento` orquesta: `preparar` -> `motor_ia.analizar` -> MRZ -> `validacion` (reglas y
  recomendacion del documento) -> `(ResultadoDocumento, datos_auditoria)`.
- Descartado: importar dentro de la funcion (funciona, pero esconde el ciclo) e importar `orquestador/mrz.py`
  directamente (incumple la regla 2 de ADR-005).
- Un test (`test_procesar_documento.py`) comprueba que `motor_ia` no importa `orquestador`, salvo `motor_ia/cli.py`:
  es un punto de entrada que ningun modulo importa, asi que no crea ciclo. El CLI llama a `procesar_documento`.

## 12. CLI (`motor_ia/cli.py`, tarea 10, entregable de la etapa 1)

| Regla | Detalle |
|---|---|
| Uso | `python -m app.modulos.motor_ia.cli <archivo> [--tipo T] [--tipo-confirmado T] [--folio F] [--salida fichero.json]` desde `backend/`. Desde la etapa 2 usa `orquestador.procesar_documento` (MRZ, reglas y recomendacion incluidas) |
| Salida | stdout: solo el `ResultadoDocumento` (JSON). stderr: resumen (modalidad, modelo, segundos y tokens por llamada, alertas), sin datos del documento |
| Codigos de salida | 0 completado; 1 `estado_analisis=error` (el JSON se imprime igual); 2 error de entrada o de configuracion (archivo inexistente, `FormatoNoSoportado`, tipo inexistente, `ErrorEnrutador`, fichas o prompts invalidos) |
| Folio y referencia | `CLI-2026-000000` por defecto; `referencia_archivo_original`: `nombre_archivo`, `ruta = local://<nombre>` (sin rutas personales) y el SHA-256 real |
| `.env` | Se lee el de la raiz del repo con `python-dotenv` (declarado en `requirements.txt`); el entorno real tiene prioridad. En Docker, `env_file` ya inyecta las variables |
| Ruta del archivo | Desde la carpeta actual y, si no existe, desde la raiz del repo: el comando del entregable funciona desde `backend/` y en el contenedor (con `/fixtures` montado) |
| Validacion al arrancar | Fichas, tipos de `--tipo` y `--tipo-confirmado` y enrutador antes de preparar el documento |

Ejecucion real en el contenedor contra el Ollama del equipo (Windows sin Visual C++ Redistributable):

```
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -v "<repo>/fixtures:/fixtures:ro" \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 backend \
  python -m app.modulos.motor_ia.cli fixtures/generados/pasaporte_sano_digital.pdf --tipo pasaporte
```

## 13. Tiempo por documento

Medido en la VM de pruebas (2 nucleos, sin GPU), evaluacion del 2026-10-01 (`pruebas_ollama/resultados/evaluacion/`),
un documento de 1 pagina cada vez y un modelo cargado cada vez:

| Documento | Media | Maximo medido | Por que |
|---|---|---|---|
| Normal (digital, escaneado o foto; ruta auto) | ~60 s (59,4 s) | 73 s | Texto (capa del PDF u OCR) + `gemma4:e2b`: clasificacion + extraccion |
| Primer documento, con el modelo sin cargar (pasaporte digital, 2026-10-02) | 76-87 s | 87 s | Carga de `gemma4:e2b` (~21 s, en la primera llamada) + clasificacion + extraccion. El mismo documento repetido con el modelo cargado: **47 s** (clasificacion 7 s, extraccion 37 s, resto ~3 s). En la demo, calentar el modelo antes (o asumir ~30 s mas en el primero) |
| Tipo declarado equivocado (`CLS-001`) | ~55 s | 56 s | Sin reintento con vision |
| Dificil (ruta auto) | ~150 s | 244 s | Texto + reintento o extraccion con vision (`qwen2.5vl:3b`) |
| Extremo (ruta auto) | ~156 s | 193 s | Reclasificacion y extraccion con vision |
| Vision forzada (dificil y extremo) | ~155 s | 195 s | Clasificacion + extraccion con vision |

Limites (timeouts de cada peticion, `proveedores/base.py`): texto **120 s**; vision **60 s + 150 s por imagen**
(1 pagina: 210 s; lote de 4: 660 s). El reintento de correccion del JSON usa el de texto. Peor caso de un documento
de 1 pagina con OCR pobre, sin reintentos de correccion: clasificacion con texto (120 s) + reclasificacion con vision
(210 s) + extraccion con vision (210 s) = **540 s**; cada reintento de correccion suma hasta 120 s y el respaldo, si
lo hay, repite la llamada. Con varios documentos, la ingesta los procesa de uno en uno (PR #9): el tiempo de espera
se suma. En la maquina con GPU hay que volver a medir.

**Calentar los modelos antes de la demo** (`motor_ia/calentar.py`): carga el modelo de texto en Ollama con una
peticion vacia (`/api/generate` sin prompt, `keep_alive` y **`num_ctx` = `NUM_CTX`** de `proveedores/base.py`), sin
analizar ningun documento. Sin el mismo `num_ctx` (fallo corregido el 2026-10-05), Ollama lo cargaba con 4096 y lo
recargaba en la primera peticion del motor: el calentamiento no servia.
Asi el primer documento tarda como los demas (~47 s) y no ~80 s. Medido el 2026-10-05: `gemma4:e2b` cargado en
28,3 s. `--vision` carga tambien `qwen2.5vl:3b`; con `OLLAMA_MAX_LOADED_MODELS=1` descarga el de texto, asi que solo
conviene si la demo empieza con fotos. Lanzarlo justo antes de la demo: el modelo se descarga tras `KEEP_ALIVE` (10
min) sin uso. Salida 0 si carga; 1 si falla (p. ej. modelo no descargado). Tests: `test_calentar.py` (HTTP falso).

```
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps backend python -m app.modulos.motor_ia.calentar
```

## 14. Confianza calculada por el codigo (ADR-007, etapa 2)

Implementado en `motor_ia/confianza.py` (funciones puras) y aplicado en `motor_ia/servicio.py`. La confianza que
devuelve el modelo ya no llega a `ResultadoDocumento`: va a `Analisis.confianzas_modelo` (por campo y
`"clasificacion"`) para la auditoria (`datos_auditoria`, paso 4).

| Regla | Detalle |
|---|---|
| Campo | `0,6 x aparece + 0,4 x formato_valido`; campo `null` -> 0. `aparece`: 1 si el valor esta en el texto del documento (capa del PDF u OCR, sin recortar) tras normalizar (mayusculas, sin acentos, espacios colapsados); las fechas se comparan con las fechas del texto normalizadas (o con sus cifras sin separador, p. ej. `3009/2021`); un texto que no esta exacto vale su parecido con el mejor tramo del texto si es >= 0,85 (`SIMILITUD_MINIMA`). `formato_valido`: `patron` de la ficha, fecha ISO valida o anio de 4 cifras; texto sin patron, valido |
| MRZ (pasaporte) | Cubre `numero_pasaporte`, `fecha_nacimiento`, `fecha_vencimiento` y `sexo`. Digitos de control correctos: el valor queda verificado (`aparece = 1`) si coincide con la MRZ y sin verificar (`aparece = 0`) si no. Digitos fallidos: tope de **0,5** (`TOPE_MRZ_FALLIDA`) **salvo que el valor este tal cual en la zona visual** (ajuste de la calibracion: el OCR leia mal la MRZ de `pasaporte_vencido_escaneado` y castigaba 3 campos bien leidos) |
| Clasificacion | Proporcion de `marcadores_clasificacion` del tipo detectado que aparecen en el texto normalizado (`re.MULTILINE`). `desconocido` o ficha sin marcadores -> 0. Con `tipo_confirmado` no se clasifica: `None` (ADR-009); el 1,0 lo pone la plataforma (D2) |
| `CLS-002` (preventiva) | Confianza de clasificacion < `confianza_minima_clasificacion` del tipo detectado. **No se emite con `desconocido`** (ya avisa `CLS-001`; D4) |
| Marcadores | En `config/tipos/*.yaml` (PR pequeno aparte, con aviso). Cuantos: el umbral tolera uno sin encontrar (pasaporte y credencial 7 -> 6/7 = 0,857 >= 0,85; comprobante 5 -> 4/5 = 0,80). Validados en el cargador (compilan, sin repetidos) |
| Umbrales | Sin cambios (`confianza_minima_campo` y `confianza_minima_clasificacion` de las fichas) |
| Campo corregido | 1,0 (ADR-006 2.4): lo aplica la plataforma, no el motor |

Calibracion (2026-10-02, `pruebas_ollama/calibrar_confianza.py`, sin modelo; informe en
`pruebas_ollama/resultados/calibracion/informe.md`):

| Medida | Normal | Dificil | Extremo | Especimenes |
|---|---|---|---|---|
| A. Valores correctos (de `INDICE.md`) con confianza >= minimo | **152/153** | 30/34 | 13/34 | 23/27 |
| A. Clasificacion del tipo correcto >= minimo | **27/27** | 2/6 | 0/6 | 4/5 |
| B. Campos extraidos correctos >= minimo (ruta auto) | 152/153 | 28/31 | 11/28 | - |
| B. Campos extraidos incorrectos < minimo (ruta auto y vision) | - | 0/3 | 4/9 | - |

- Normal: el unico campo por debajo es `sexo` de `pasaporte_vencido_escaneado`, que sale de una MRZ mal leida y
  no esta en la zona visual: queda sin verificar, como debe.
- Dificil y extremo: con OCR malo casi nada se puede verificar en el texto -> `VAL-002` y `CLS-002` y
  `revision_manual`. Es lo que pide el ADR-007 ("el dato no se ha podido verificar"). **Aceptado** (2026-10-02),
  incluido el ruido de `CLS-002` (preventiva) en los dificiles.
- Especimenes: los 4 con texto OCR suficiente, 23/23 campos y 4/4 tipos sobre el minimo (tambien el comprobante
  "buena", 4/4 campos a 1,0). El comprobante "dificil" solo da 14 caracteres de OCR: va por vision, no hay texto
  con el que verificar y sus 4 campos quedan sin verificar (`VAL-002`). Para la demo, usar los "buena".
- **No detecta** los errores que el modelo copia del propio OCR (8 de 12 incorrectos, p. ej. `2X0000001`,
  `AMA EJEMPLO PRUEBA`, `GALLE FICTICIA 123`): estan en el texto. Para eso: reglas de coherencia (paso 2) y la
  confianza por palabra de Tesseract (pendiente). El modelo daba 0,9-1,0 a los 12 incorrectos.
- **Objetivo pendiente**: marcar como dudosos al menos el 50 % de los campos incorrectos de los fixtures dificiles
  y extremos (hoy 4/12). Queda para las reglas de coherencia (paso 2) y la confianza de Tesseract (senal 5); se
  vuelve a medir con `calibrar_confianza.py` y `evaluar_fixtures.py` cuando esten.

## 15. Reglas del documento (`validacion/reglas.py`, etapa 2)

API publica: `validacion.servicio.evaluar_reglas(datos_extraidos, confianzas, ficha, *, hoy) -> (list[Alerta], Reglas)`
(firma aceptada por PERSONA_1, seccion 11). `validacion/servicio.py` es compartido: solo se anadio el bloque de
PERSONA_2 al final (import y `__all__ +=`), sin tocar lo de PERSONA_1.

| Regla | Detalle |
|---|---|
| `VAL-001` (critica) | Campo `obligatorio: true` ausente, `null`, `""` o solo espacios |
| `VAL-004` (informativa) | Campo `obligatorio: false` vacio |
| `VAL-002` (preventiva) | Campo **con valor** y confianza < `confianza_minima_campo` (D4); sin confianza cuenta como 0 |
| `REG-{id}` (severidad de la ficha) | Regla incumplida; `campo` = el de la regla; `mensaje` = el de la ficha |
| Campo vacio | Sus reglas no se evaluan ni se listan (D8), salvo las de tipo `obligatorio` |
| `patron` | `fullmatch` del patron del campo |
| `fecha_posterior_a_hoy` / `_mas_dias` / `fecha_no_anterior_a_hoy_menos_dias` | fecha > hoy / > hoy + dias / >= hoy - dias. Una fecha que no es ISO valida incumple (y lleva `VAL-002` por su confianza 0) |
| `anio_mayor_o_igual_actual` | anio (entero o texto de 4 cifras) >= `hoy.year`; otro valor incumple |
| `obligatorio`, `confianza_minima` | Como `VAL-001` y `VAL-002`, pero con su `REG-{id}` |
| `curp_coincide_con_fecha` (nuevo) | Posiciones 5-10 de la CURP = `campo_relacionado` en `AAMMDD` y posicion 17 digito si nacio antes de 2000, letra si despues. No se evalua si la CURP no tiene el formato o la fecha no es valida |
| `fecha_anterior_a_campo` (nuevo) | `campo` < `campo_relacionado`. No se evalua si alguna no es una fecha valida |
| Cada regla tal cual | Un pasaporte vencido incumple `vigencia_documento` y `vigencia_proxima` (D9) |
| Alertas | Confianza 1,0, sin `id`, una por (`codigo`, `campo`). Orden: VAL por el orden de los campos y REG por el de las reglas. Nunca `VAL-003`, `CLS`, `SYS`, `DUP`, `EXP` ni `CMP` |
| Ficha | `TipoDocumental` o dict; un dict invalido -> `ErrorConfiguracion` |
| Cargador | `Regla.campo_relacionado` (obligatorio en las de coherencia y prohibido en las demas; campo existente y de tipo `texto`+`fecha` o `fecha`+`fecha`) |
| Tests | `test_reglas.py` (fronteras de cada tipo, D8, D9, coherencia con los dos fallos reales del bloque 3), `test_configuracion.py`, `test_generar_fixtures.py` |

### Recomendacion del documento (`validacion/recomendacion.py`, etapa 2, paso 3)

`validacion.servicio.recomendar_documento(resultado, ficha) -> Recomendacion`. Pura. **Nunca `rechazar`** (D1,
aceptado en el PR #13; `codigos_alertas.md` no cambia). Mismas reglas que la recomendacion global de PERSONA_1
(`expediente/recomendacion.py`), aplicadas a un documento:

| Recomendacion | Cuando |
|---|---|
| `revision_manual` | `estado_analisis` distinto de `completado`; sin ficha (p. ej. `desconocido` sin tipo declarado ni confirmado); alguna alerta `critica` o `bloqueante` con `aplica` distinto de `false` (sin revisar o confirmada); `confianza_clasificacion` ausente o < `confianza_minima_clasificacion`; algun campo **con valor** con confianza < `confianza_minima_campo` |
| `aprobar` | Todo lo demas. Las alertas preventivas e informativas no frenan; los campos vacios no cuentan en las confianzas (ya llevan `VAL-001`, critica, o `VAL-004`, informativa) |

- `ficha`: la del tipo de extraccion (`TipoDocumental` o dict). Con tipo confirmado, el motor deja
  `confianza_clasificacion = None` (ADR-009) y la recomendacion la cuenta como 1,0 (D2): no lleva a `revision_manual`.
- La plataforma puede recalcularla tras una correccion o al resolver alertas con el `ResultadoDocumento` vigente.
- Tests: `test_recomendacion_documento.py`.

## 16. Memoria de folios (`rag`, H14, ADR-010 C4)

API publica (`rag/servicio.py`):
- `indexar_resumen(folio, resumen_md, *, sesion=None, ahora=None) -> None`: guarda o sustituye el `resumen.md` del
  folio (ya enmascarado, ADR-010 A5) y su fragmento. **Nunca lanza**: si falla, registra solo el folio y el tipo
  de error, nunca el contenido; el siguiente cambio lo reindexa. **Con `sesion`, hace `commit` sobre ella** (y
  `rollback` si falla, que descartaria tambien lo pendiente del llamador): llamarla despues del commit del llamador.
- `fragmento_resumen(folio, *, sesion=None) -> str | None`: el fragmento, o `None` si el folio no esta indexado.
  Sin `sesion`, cada funcion abre y cierra la suya.

| Decision | Detalle |
|---|---|
| **Sin embeddings** (2026-10-05, decidido por PERSONA_2) | C4 solo pide un trozo del resumen de cada folio, y los folios relacionados los elige la plataforma con SQL (C2): no hace falta busqueda semantica. Calcular embeddings en cada regeneracion del resumen (en cada correccion, alerta resuelta o decision) cargaria otro modelo en Ollama y, con `OLLAMA_MAX_LOADED_MODELS=1`, descargaria `gemma4:e2b`: el siguiente documento volveria a pagar ~21-28 s de carga. Sin vectores, la tabla funciona tambien en SQLite (tests) y no necesita pgvector. Si se hace la base de conocimiento (`contexto_rag`), sus embeddings se calcularan fuera del analisis y en una tabla aparte |
| Tabla | `memoria_folios` (`folio` PK y FK a `folios`, `resumen_md`, `fragmento`, `actualizado_en`). El modelo vive en `rag/modelos.py`, no en `core/modelos.py`. Migracion `0005` e import de `app.modulos.rag.modelos` en `alembic/env.py`: PERSONA_1 (#39) |
| Cuando se indexa | Al regenerar el resumen, despues del commit de la accion: `expediente.servicio.avisar_reindexar(sesion, folio, resumen_md)` llama a `rag.servicio.indexar_resumen(folio, resumen_md, sesion=sesion)` con el mismo texto enmascarado que va a S3 (asi `rag` no lee S3) (PERSONA_1, #39). Folios anteriores: `scripts/reindexar_resumenes.py` |
| Fragmento | Determinista, sin modelo: cabecera (`# Expediente`, referencia opaca, proceso, fecha, estado, recomendacion global), la decision **sin el comentario libre**, de cada documento su titulo, estado y alertas, y las alertas del expediente. **Nunca** los `Datos:`, las comparaciones ni "Generado el": aunque el resumen llegue enmascarado, el fragmento no copia valores. Se corta en un final de linea antes de `LIMITE_FRAGMENTO` (800) caracteres, con `...` |
| Formato que lee | El de `expediente/plantillas/resumen.md.j2` (listas, desde el #27): titulos `#`, `##`, `###`, lineas `- Clave: valor`, `Datos:` y los titulos de grupo de alertas acabados en `:`. Si la plantilla cambia, revisar `extraer_fragmento` y sus tests |
| **Base de conocimiento** (R10, 2026-10-07, ACEPTADO por PERSONA_1 y PERSONA_2) | Fuera del MVP: con `OLLAMA_MAX_LOADED_MODELS=1`, el modelo de embeddings expulsa a `gemma4:e2b` y cada documento tardaria ~25 s mas en volver a cargarlo. El requisito RAG del MVP lo cubre la memoria de folios (esta seccion) con los antecedentes (H16). **Evolucion futura**, activable con GPU o mas RAM (dos modelos cargados a la vez) **sin cambiar la arquitectura**: el motor ya recibe `DocumentoPreparado.contexto_rag` y los prompts ya tienen su hueco (`formatear_contexto_rag`, hoy `(sin contexto)`); bastaria `rag/conocimiento.py` (`buscar(consulta, k)`) y `rag/embeddings.py`, con los embeddings calculados fuera del analisis y en una tabla aparte. **Opcion barata posterior**: `contexto_rag` sin embeddings, con un `.md` de conocimiento por tipo documental (`docs/conocimiento/<tipo>.md`) que se pasa entero segun el tipo; no carga ningun modelo |
| Tests | `test_memoria_folios.py`: SQLite temporal y un `resumen.md` de ejemplo enmascarado; fragmento con y sin decision, sin valores, corte, folio sin indexar, reindexado, fallo sin lanzar y sin contenido en el log |

## Registro de cambios

El mas reciente arriba.

| Fecha | Cambio | Commit |
|---|---|---|
| 2026-10-07 | R10 (ACEPTADO por PERSONA_1 y PERSONA_2): base de conocimiento con embeddings fuera del MVP (con `OLLAMA_MAX_LOADED_MODELS=1` expulsaria a `gemma4:e2b`: ~25 s mas por documento). El RAG del MVP es la memoria de folios (H14). Seccion 16: evolucion futura con GPU o mas RAM sin cambiar la arquitectura (`contexto_rag` ya existe) y opcion barata sin embeddings (un `.md` por tipo). Modelos (seccion 2) y RAG (seccion 6) al dia | este commit |
| 2026-10-06 | Merge de `origin/main` en `feat/motor-ia` con el #42 (arranque de demo) y el #43 (filtro de logs). `CHECKLIST_E2E_HITO.md`: la plataforma se arranca con `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build` (backend sin `--reload`, frontend incluido) y el arranque de desarrollo queda como alternativa. `ESTADO_SESION.md` al dia (#42 y #43 fusionados; el aviso del log, resuelto por el #43) | este commit |
| 2026-10-06 | Merge de `origin/main` en `feat/motor-ia` con el #38 (boton Mostrar), el #39 (H14 conectado), el #40 (CI en ubuntu-24.04) y el #41 (antecedentes); conflicto del registro resuelto conservando todas las entradas. `ESTADO_SESION.md` al dia (H14 completo; H16 y H17 en `main`; siguiente, el e2e por la web). Docstring de `indexar_resumen`: hace commit (o rollback) sobre la sesion recibida y se llama despues del commit del llamador | `6325c9d` |
| 2026-10-06 | `ESTADO_SESION.md` al dia: H13 (#35), documentacion (#36) y enmascaramiento (#32) fusionados; H14 (#37) esperando aprobacion; siguiente paso, el e2e por la web con la mascara (plataforma preparada sin el override local y sin `revisor_hito`) | `6501bff` |
| 2026-10-06 | Merge de `origin/main` en `feat/motor-ia` con el #32 (enmascaramiento), el #34 (arquitectura) y el #35 (H13); conflicto del registro y de la checklist resuelto conservando todas las entradas | `9444744` |
| 2026-10-06 | Merge de `origin/main` con el #33 (reanudar analisis) y el #36 (documentacion del motor) en `feat/rag-memoria`; conflicto del registro y del historial resuelto conservando todas las entradas | `959922b` |
| 2026-10-06 | Merge de `origin/main` en `feat/rag-memoria` con el #32 (enmascaramiento), el #34 (arquitectura) y el #35 (H13); conflicto del registro y de la checklist resuelto conservando todas las entradas | `3c9aea3` |
| 2026-10-05 | H14 (seccion 16): memoria de folios en `rag` sin embeddings (decision y motivo), tabla `memoria_folios` con el modelo en `rag/modelos.py`, `indexar_resumen` y `fragmento_resumen`; migracion y `avisar_reindexar` pendientes de PERSONA_1 | `c170791` |
| 2026-10-05 | `docs/motor_ia/ESTADO_SESION.md`: estado de las ramas, PR abiertos, pendientes en orden y reglas de trabajo, para retomar la proxima sesion | `c6350c7` |
| 2026-10-05 | e2e del hito sobre `main` (H10 y D3) con Ollama real y S3: folio sano con los 3 `completado`, sin alertas, global `aprobar` en 210 s; el primer documento no recargo el modelo (`calentar` con `num_ctx`); D3 recalcula reglas y recomendacion al corregir; folios vencido (`REG-vigencia_documento`) y domicilio_distinto (`CMP-001`) como en `INDICE.md`. Resultado anadido a `CHECKLIST_E2E_HITO.md` | `b7cacb2` |
| 2026-10-05 | `docs/motor_ia/CHECKLIST_E2E_HITO.md`: checklist del e2e del hito (preparacion, calentar, prueba con los 3 sanos, resultado esperado de la prueba local de H10 y que mirar si falla) | `00e9546` |
| 2026-10-05 | Especimen "dificil" del comprobante (vision): 4/4 correctos, `revision_manual` con `CLS-002` y `VAL-002` (sin texto que verificar). Especimenes completos: 27/27, tipo 5/5 | `c8cf280` |
| 2026-10-05 | H13: PyMuPDF 1.28.2 y Pillow 12.3.0 fijadas con `==` en `backend/requirements.txt` (las del contenedor y de `sha256_fixtures_existentes.txt`) | `8080f6f` |
| 2026-10-05 | Prueba local de H10 (`feat/plataforma-motor`, `a1fc046`) con Ollama real y S3: folio `onboarding` con los 3 documentos sanos (pasaporte digital, credencial foto, comprobante escaneado), los tres `completado`, tipo y campos 17/17 con confianza 1,0, sin alertas, comparaciones coinciden, recomendacion global `aprobar`, 194 s en serie (72, 71 y 51 s). `calentar` pasa `num_ctx` = `NUM_CTX` (antes cargaba con 4096 y Ollama recargaba el modelo en la primera peticion) | `807c2d6` |
| 2026-10-05 | Merge de `origin/main` con H15 (#26). Rama `chore/mocks-sensible` (`e24e757`, con permiso de PERSONA_1): `generar_datos_mock.py` pone `sensible` en todos los campos de `tipos_documentales.json`, igual que la API, y `test_contrato_frontend.py` lo comprueba | `bb5477a` |
| 2026-10-05 | Aviso de los especimenes corregido: el comprobante da `REG-antiguedad_maxima` desde el **2026-12-15** (la regla compara emision >= hoy - 90 dias; el 14 aun cumple) | `7865d5b` |
| 2026-10-05 | Especimenes (bloque 5, flujo completo): los 4 que van por texto, 23/23 campos, tipo 4/4, recomendacion `aprobar`; el comprobante dificil, pendiente de RAM. `evaluar_fixtures.py --margen-gb` (margen de RAM para `--solo` con casos de texto) y los fallos de especimenes en la tabla de campos que fallan. Merge de `origin/main` con el #23 | `1745d4a` |
| 2026-10-05 | H15 (ADR-010, A1 y A6): `sensible` en el cargador y en `curp`, `clave_elector` y `numero_pasaporte`; Contrato 2 con `sensible` en `CampoFicha`; test de que los logs del motor y `datos_auditoria` no llevan valores | `a627aa8` |
| 2026-10-05 | `motor_ia/calentar.py` (calentar los modelos antes de la demo; `gemma4:e2b` cargado en 28,3 s) en la seccion 13. `evaluar_fixtures.py`: todos los bloques pasan por `orquestador.procesar_documento` (reglas y recomendacion en el resultado), bloque 5 de especimenes (`--salida resultados/especimenes`) y `--salida` absoluta para Docker. H11: formato de `INDICE.md` documentado en `fixtures/README.md` | `f4b41fb` |
| 2026-10-05 | ADR-010 (PR #21, aprobado por PERSONA_2): H14 pasa a ser solo `rag.servicio.fragmento_resumen(folio) -> str \| None` ya enmascarado (PERSONA_1 elige los folios con SQL); H15 (`sensible: true`) despues del PR de reglas de coherencia, con test de que logs y `datos_auditoria` no llevan valores | `6195d28` |
| 2026-10-02 | Seccion 13: tiempo del primer documento con el modelo sin cargar (76-87 s; carga ~21 s) frente a 47 s con el modelo cargado (CLI con `procesar_documento`, pasaporte digital). No supera los 73 s con el modelo cargado: el maximo no cambia. Rama `chore/reglas-coherencia` (`2986d2b`) desde `main`, subida sin PR. Test de ids de reglas del pasaporte como subconjunto | `e679f60` |
| 2026-10-02 | Etapa 2, paso 4: `orquestador.procesar_documento` (`orquestador/procesamiento.py`) con la firma de la seccion 11: preparar, MRZ, `motor_ia.analizar(mrz=)`, sexo y `VAL-003` en el orquestador (`completar_mrz.py`), reglas con `hoy` de `reloj.py`, recomendacion y `datos_auditoria` (con `version_prompt_clasificacion`). `motor_ia` ya no importa `orquestador` (test). CLI y `evaluar_fixtures.py` pasan por el orquestador | `90e9a36` |
| 2026-10-02 | Revision de PERSONA_1 en el PR #18: con `tipo_confirmado` el motor deja `confianza_clasificacion = None` (ADR-009, como el stub del PR #19) y el 1,0 lo pone la plataforma (D2); `recomendar_documento` cuenta esa `None` como 1,0 si hay tipo confirmado. Merge de `origin/main` con el PR #19. La rama de reglas de coherencia se prepara desde `main` cuando se fusione el PR #18 y llevara tambien `endpoints.md`, `contrato.ts`, `_regla` de `ingesta/tipos.py` y pasara `test_openapi_contrato.py` (`campo_relacionado` cambia el Contrato 2) | `d7a07f5` |
| 2026-10-02 | Etapa 2, paso 3: `validacion/recomendacion.py` (`recomendar_documento`): solo `aprobar` o `revision_manual` (D1), con las mismas reglas que la global de PERSONA_1; expuesta en el bloque de PERSONA_2 de `validacion/servicio.py`. Rama local `chore/reglas-coherencia` (`ecea1b0`): las 4 reglas de coherencia en las fichas y los mocks regenerados con el script, para abrir cuando se fusione el PR de marcadores | `a1d85d3` |
| 2026-10-02 | Etapa 2, paso 2: `validacion/reglas.py` (`evaluar_reglas`: `VAL-001`, `VAL-002`, `VAL-004`, `REG-*`, fechas no normalizables), expuesta en `validacion/servicio.py` (solo el bloque de PERSONA_2). Tipos de regla de coherencia `curp_coincide_con_fecha` y `fecha_anterior_a_campo` en el cargador (`campo_relacionado`), en `reglas.py` y en `generar_fixtures.py` (H13); las fichas aun no los usan (los mocks del frontend se regeneran). Medido: 4/12 incorrectos marcados, con y sin coherencia (seccion 7) | `1fbf9c7` |
| 2026-10-02 | `marcadores_clasificacion` fuera de `model_dump()` (`Field(exclude=True)`): son internos del motor y `GET /tipos-documentales` (Contrato 2) no cambia, tampoco cuando la API use `configuracion.servicio.listar()`. Mismo cambio en `chore/marcadores-clasificacion` (`3ce49c4`) | `52aaa39` |
| 2026-10-02 | Seccion 11: firma de `evaluar_reglas` aceptada por PERSONA_1 (ficha como `TipoDocumental`, `Reglas` devuelto, `VAL-003` borrada al corregir), D1 (nunca `rechazar`) y D2. "Hoy" de las reglas con `ZONA_HORARIA` (por defecto `America/Mexico_City`) en `orquestador/reloj.py`, sin `core.config`; test cerca de medianoche. Rama `chore/marcadores-clasificacion` (`8d8bfca`) con el cargador y los marcadores para `main` | `72b3d85` |
| 2026-10-02 | Calibracion de ADR-007 aceptada (ajuste de la MRZ y ruido de `CLS-002` en los dificiles). Objetivo pendiente: marcar >= 50 % de los incorrectos (hoy 4/12), con las reglas de coherencia y la confianza de Tesseract. Especimenes: el comprobante "buena" verifica 4/4; los 4 sin verificar son del "dificil" (14 caracteres de OCR) | `a3787b2` |
| 2026-10-02 | Etapa 2, paso 1 (ADR-007): `motor_ia/confianza.py` (confianza de campo y de clasificacion por el codigo, MRZ con tope 0,5 salvo zona visual), `CLS-002`, `confianza_clasificacion = 1,0` con `tipo_confirmado` (D2), sin `CLS-002` con `desconocido` (D4), confianza del modelo en `Analisis.confianzas_modelo`. Cargador: `marcadores_clasificacion` y nombre reservado `desconocido` (ADR-009). Marcadores en las tres fichas. Calibracion sin modelo: normal 152/153 campos y 27/27 clasificaciones sobre el minimo (seccion 14) | `afd6c5f` |
| 2026-10-02 | Merge de `origin/main` con los PR #16 y #17: ADR-009 final (`EXP-001` tambien sin tipo declarado). Traspaso de PERSONA_3 (PR #13): `rag` completo y fixtures para PERSONA_2, tareas H9-H15 y recortes R4, R5, R6 y R8 en los pendientes | `afd6c5f` |
| 2026-10-02 | ADR-009 ACEPTADO (PERSONA_1 en la revision del PR #14 y PERSONA_2): `desconocido` reservado, no cubre ningun requerido y emite `EXP-002`; sin `CLS-003`. La version aceptada con `EXP-002` va en un PR nuevo desde `docs/adr-009-desconocido` (el PR #14 se fusiono antes) | `3e2bf3b` |
| 2026-10-01 | Revision de PERSONA_3 en el PR #11: 42 fixtures (27 + 3 duplicados + 12 de dificultad); variables ya en `.env.example` (PR #5); prompts vigentes con `extraccion_v3`; PR #4 fusionado; pendientes cumplidos marcados (credencial y comprobante evaluados, avisos del PR #11, especimenes en `main`). Valor reservado `desconocido` (seccion 10) y ADR-009 PROPUESTO en `docs/adr-009-desconocido` (`4dc4906`). Notas para la etapa 2: stub hasta ADR-007, version del prompt de clasificacion en `datos_auditoria`, ADR para `extraer_con_vision`/`clasificar_con_vision`/`ultima_llamada` con `openrouter.py`. Seccion 13: tiempo por documento. `test_fixtures_ocr.py` filtra los casos y el nivel conocidos (no depende de 153). Comando de tests con `fixtures/`, `frontend/` y `docs/` montados | `7c84720` |
| 2026-10-01 | Pendiente "documentos de uno en uno" y `OLLAMA_MAX_LOADED_MODELS=1` resuelto por PERSONA_1 (PR #9: semaforo `MAX_PROCESAMIENTOS_SIMULTANEOS=1`) | `a3e69a9` |
| 2026-10-01 | `docs/motor_ia/EXPLICACION_MOTOR.md`: explicacion del motor para el equipo (flujo, modelos probados, historial de mejoras, reglas, resultados, pendientes). Regla: cada cambio de regla, de modelo o resultado de prueba anade una entrada a su historial en el mismo commit | `a3e69a9` |
| 2026-10-01 | `extraccion_v3` sin la obligatoriedad en la lista de campos (`formatear_campos`, variable `campos_a_extraer`): la palabra "opcional" hacia que la vision dejara vacia `fecha_expedicion`; 4 pasaportes dificiles con vision forzada 21/28 -> 25/28. Bloque 3 repetido con la regla de OCR pobre: APRUEBA (dificil 31/34 y 2 incorrectos; extremo 28/34 y 6; tipo 6/6 y 6/6). Bloque 1 repetido: 153/153, 59,4 s. El bloque 4 no se repite: queda como referencia y el informe avisa de que mezcla v2 (8 casos) y v3 (4 pasaportes) | `459ef8f` |
| 2026-10-01 | Regla de OCR pobre (seccion 3): cuatro senales (texto insuficiente, clasificacion `desconocido`, obligatorios vacios, formato invalido); reclasificacion con vision cuando el texto da `desconocido`, con `CLS-001` decidido segun la vision; extraccion directa con vision si la clasificacion ya detecto OCR pobre; motivos en `InfoLlamada.motivo`. Prompt `extraccion_v3` (asignar por etiqueta; corrige `fecha_expedicion` vacia en vision); observaciones visuales pasan a v4. Pendientes: confianza de Tesseract y especimenes | `903f09b` |
| 2026-10-01 | Evaluacion, bloque 4 (vision forzada en los 12 fixtures dificiles): 60/68 correctos, 4 vacios y 4 incorrectos, frente a 28/68, 23 y 17 de la ruta auto; tipo correcto 12/12; ~130-195 s por caso; RAM libre minima 1,42 GB, un modelo cada vez. La vision deja vacia `fecha_expedicion` en los 4 pasaportes | `8058e7e` |
| 2026-10-01 | Pendientes de la etapa 2: reglas de coherencia CURP <-> `fecha_nacimiento` y `fecha_nacimiento` < `fecha_expedicion` < `fecha_vencimiento`, con tipos de regla nuevos en las fichas (PR aparte, fichero compartido) y en el cargador | `8058e7e` |
| 2026-10-01 | Evaluacion, bloque 3 (fixtures dificiles de PERSONA_3, ruta auto, 12 casos): NO aprueba (dificil 19/34 correctos y 7/34 incorrectos; extremo 10/34 incorrectos; 0 reintentos con vision porque `CLS-001` los bloquea). 8 de los 17 incorrectos los detectarian las reglas de la etapa 2. `evaluar_fixtures.py`: niveles de dificultad, bloques 3 y 4, campos correcto/vacio/incorrecto, `docker stop` del contenedor si la RAM baja de 1 GB y descarga del otro modelo en cada cambio | `56cca57` |
| 2026-10-01 | Evaluacion completa, bloque 1 (ruta auto, 30 casos): 153/153 campos, 27/27 tipos, `CLS-001` 3/3, sin errores ni abortos, 59 s de media (`pruebas_ollama/resultados/evaluacion/informe.md`). El reintento con vision pasa del proveedor al servicio y no se hace si salta `CLS-001` (el caso que tardaba 255 s baja a 80 s); el proveedor expone `extraer_con_vision`. Pendientes: `OLLAMA_MAX_LOADED_MODELS=1` en produccion y bloque 2 opcional. Script `evaluar_fixtures.py` | `a0c7675` |
| 2026-10-01 | Merge de `origin/main` con los PR #5 (`.env.example`: modelos, `PROMPTS_DIR`, `PERMITIR_PROVEEDORES_NO_PRIVADOS`, `OLLAMA_BASE_URL` por defecto a `host.docker.internal`), #6 (`VAL-004` en el catalogo) y #7/#8 (ADR-008: `referencia_externa` en `ResumenFolio` y `/auditoria` paginada; no afecta al motor). Se quitan de pendientes el PR de `.env.example` y el alta de `VAL-004`. Regla de `validacion/servicio.py` compartido con PERSONA_1 en pendientes | `d3e18b4` |
| 2026-10-01 | Regla del enrutador: texto si todas las paginas tienen >= 30 caracteres (capa del PDF u OCR), vision si alguna no llega. Reintento con vision si la extraccion con texto deja a `null` la mitad o mas de los obligatorios (riesgo 2 del plan), registrado en las llamadas (`entrada`, `motivo`). `NUM_CTX` fijo a 16384. `""` y textos solo con espacios a `null` (acordado con PERSONA_3). Medidas A/B en `pruebas_ollama.md` | `1a6b9f4` |
| 2026-09-30 | `OLLAMA_BASE_URL` por defecto de `.env.example`: `http://host.docker.internal:11434` (revision de PERSONA_1; `ollama` es un perfil opcional desde el PR #3). El `.env` local de PERSONA_2 sigue con `localhost` | `5f6292d` |
| 2026-09-30 | Ejecucion real del CLI (entregable de la etapa 1): `pasaporte_sano_digital.pdf` 7/7 en 68 s con `gemma4:e2b`; vision pendiente por RAM (faltaron 0,25 GB). Pendientes: CLI con vision y mejorar la evidencia del prompt | `3dfb54a` |
| 2026-09-30 | `motor_ia/cli.py` (seccion 12): JSON por stdout y resumen por stderr, salidas 0/1/2, `local://` + SHA-256, `.env` con `python-dotenv` (anadido a `requirements.txt`), ruta desde la raiz del repo, `--tipo-confirmado` (11 tests). PR de `.env.example` subido en `chore/env-example` | `e5e8c5a` |
| 2026-09-30 | Seccion 11: acuerdo con PERSONA_1 para la etapa 2 (`procesar_documento`, `datos_auditoria`, errores, reparto de alertas y recomendaciones) y propuesta para evitar la importacion circular: dependencia `orquestador -> motor_ia`, con la MRZ en `orquestador` | `39bf63f` |
| 2026-09-30 | Merge del PR #3 de PERSONA_1 (core, API, ingesta, expediente), sin conflictos. Los tests en el contenedor necesitan montar `scripts/` (seccion 8): 369 pasan y 1 se salta (requiere `TEST_POSTGRES_URL`) | `beb1b9f` |
| 2026-09-30 | `motor_ia/servicio.py`: `analizar(doc, *, folio, referencia, ...)` -> `Analisis` (se aparta de `analizar(doc, ficha)` por ADR-006 y el Contrato 1). Ficha tipo_confirmado > declarado > detectado; `CLS-001`, `SYS-001/002/003/005`, `VAL-003` con confianza 1,0; respaldo tambien ante JSON invalido; sexo desde la MRZ (1,0 / 0,5); desconocido sin declarado no se extrae ni alerta. Confianzas del modelo provisionales, sin `CLS-002` ni `VAL-002` (deuda ADR-007). `orquestador.servicio` expone `buscar_mrz` y `validar_digitos` (17 tests) | `2178f83` |
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
