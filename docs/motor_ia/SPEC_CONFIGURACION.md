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
| Asignacion de modelos por tarea | `config/modelos.yaml` (repo) | `motor_ia/enrutador.py` (tarea 8) | decidido |
| Nombres de los modelos de Ollama | `.env`: `OLLAMA_MODELO_TEXTO`, `OLLAMA_MODELO_VISION` | leidos via `modelos.yaml` (`modelo_texto_env`, `modelo_vision_env`) | decidido; `.env.example` pendiente de PR |
| URL de Ollama | `.env`: `OLLAMA_BASE_URL` | `motor_ia/proveedores/ollama.py` | decidido |
| Proveedor comercial (respaldo) | `.env`: `PROVEEDOR_COMERCIAL_*` (ADR-003) | `motor_ia/proveedores/openrouter.py` | pendiente (cuenta sin crear) |
| Carpeta de configuracion | `.env` opcional: `CONFIG_DIR`; por defecto `config/` de la raiz del repo | `configuracion/cargador.py` | implementado; falta en `.env.example` |
| Carpeta de prompts | `.env` opcional: `PROMPTS_DIR`; por defecto `prompts/` de la raiz del repo | `motor_ia/prompts.py` (tarea 5) | decidido |
| Prompts versionados | `prompts/<id>_<version>.md` (repo) | `motor_ia/prompts.py` (tarea 5) | v1 en el repo; v2 decidido |
| Borradores de prompts | `docs/motor_ia/pruebas_ollama/prompts_borrador/` (repo) | pasan a `prompts/` en la tarea 5 | referencia |
| Parametros de llamada (`temperature`, `num_predict`, `think`) | se decide en la tarea 6: constantes en `proveedores/base.py` o bloque `parametros` en `modelos.yaml` | `motor_ia/proveedores/*.py` | valores decididos (seccion 4); ubicacion en la tarea 6 |
| Procesos (`procesos.yaml`) | `config/procesos.yaml` (repo) | modulo de PERSONA_1 | fuera de este ambito |
| Scripts, imagenes y resumenes de las pruebas | `docs/motor_ia/pruebas_ollama/` (repo) | referencia; no los importa el backend | implementado |
| Respuestas crudas del modelo | carpeta local de pruebas, fuera del repo | `backend/tests/respuestas_modelo/` (tarea 7) | pendiente |

## 2. Modelos de Ollama

| Uso | Modelo | Variable del `.env` | Resultado en las pruebas | Estado |
|---|---|---|---|---|
| Texto (clasificacion y extraccion de `pdf_digital`) | `gemma4:e2b` | `OLLAMA_MODELO_TEXTO=gemma4:e2b` | 7/7 campos en 2 de 2 ejecuciones; ~37 s por documento | decidido |
| Vision (`pdf_escaneado`, `imagen`) | `qwen2.5vl:3b` | `OLLAMA_MODELO_VISION=qwen2.5vl:3b` | 7/7 tras normalizar fechas en 4 de 4; ~110 s por pagina nueva | decidido |
| URL local (CLI fuera de Docker) | - | `OLLAMA_BASE_URL=http://localhost:11434` | - | decidido |
| URL dentro de docker compose | - | `OLLAMA_BASE_URL=http://ollama:11434` | - | valor actual de `.env.example` |
| Embeddings (RAG, etapa 3) | `nomic-embed-text` (plan) | `OLLAMA_MODELO_EMBEDDINGS` (propuesta) | sin probar | pendiente |

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
segun `DocumentoPreparado.modalidad`. Se documenta en `backend/app/modulos/motor_ia/README.md` al
implementar el enrutador (tarea 8).

| Modalidad | Que prepara el orquestador | Modelo | Que se envia al modelo |
|---|---|---|---|
| `pdf_digital` | Texto por pagina (PyMuPDF) + PNG a 150 dpi | texto: `gemma4:e2b` | Solo el texto, en `{{ contenido }}`. Los PNG no se envian |
| `pdf_escaneado` | PNG a 200 dpi + OCR | vision: `qwen2.5vl:3b` | Imagenes reducidas a 1000 px de ancho + texto OCR en `{{ contenido }}` (ver pendiente OCR frente a vision) |
| `imagen` | La propia imagen + OCR | vision: `qwen2.5vl:3b` | Igual que `pdf_escaneado` |

Respaldo: si el proveedor principal falla, se usa el `respaldo` de `modelos.yaml` (OpenRouter
gratuito, ADR-003, solo con fixtures ficticios). Sin respaldo disponible: `estado_analisis=error` +
`SYS-001`.

## 4. Reglas de vision y parseo

| Regla | Valor | Motivo | Donde | Test |
|---|---|---|---|---|
| Fechas | El prompt pide las fechas **tal como aparecen**; el codigo las normaliza con `normalizar_fecha` (dia/mes/anio -> `AAAA-MM-DD`, separadores `/ . -` y espacio; ISO valido se deja igual; fecha imposible -> `None`) | Al convertirlas, `qwen2.5vl:3b` intercambia dia y mes (`10/05/2024` -> `2024-10-05`). Sin convertir: 3/3 correctas en 4 de 4 | `motor_ia/proveedores/base.py` (tarea 7). Referencia: `pruebas_ollama/prueba_fechas.py` | unitario con los 11 casos del autotest |
| Tamano de imagen | Ancho maximo 1000 px antes de enviar | Sube los aciertos de 5/7 a 6/7 y ahorra ~20 % de tiempo; 800 px no mejora | `orquestador/preparador.py` o `proveedores/base.py` (tarea 4 o 7) | unitario de redimensionado |
| Evidencia | Para vision solo `pagina_<n>`; se descarta la seccion | `qwen2.5vl:3b` copia la seccion del ejemplo en todos los campos | `proveedores/ollama.py` (tarea 6) | unitario con respuestas guardadas |
| Confianza del modelo | Se guarda en `nivel_confianza_por_campo`, pero **no se usa en las reglas** | Siempre 0,9 o 1, tambien en datos mal leidos o inventados | `validacion/reglas.py` (etapa 2) | unitario |
| Formato de salida | `format: "json"` + parseo estricto con Pydantic; si el JSON es invalido, 1 reintento con instruccion de correccion; despues `SYS-002` | JSON valido en todas las pruebas, pero no esta garantizado | `proveedores/ollama.py` | unitario con respuestas guardadas |
| Razonamiento | `think: false` solo en modelos que lo admiten (`gemma4`) | `gemma4` razona por defecto: mas lento y mezcla texto con el JSON | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Temperatura | `temperature: 0` | Respuestas lo mas estables posible (no garantiza determinismo) | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Tope de salida | `num_predict: 800` | Sin tope, una transcripcion se quedo mas de 10 minutos repitiendo `<<<<` | `proveedores/ollama.py` | unitario del cuerpo de la peticion |
| Tests | Solo con respuestas guardadas en `backend/tests/respuestas_modelo/`; nunca contra el modelo real | El modelo no es determinista y tarda de 35 a 125 s | `backend/tests/` | - |

## 5. Prompts

| Version | Estado | Contenido | Donde |
|---|---|---|---|
| `clasificacion_v1`, `extraccion_v1` | en el repo | Version inicial. Falta una variable para el texto del documento | `prompts/` |
| `clasificacion_v2`, `extraccion_v2` | decidido (tarea 5) | Anade `{{ contenido }}` (texto por pagina), fechas tal como aparecen, formato de evidencia, instruccion de bajar la confianza si hay dudas y de no inventar valores | borrador: `pruebas_ollama/prompts_borrador/extraccion_v2b.md` |
| `extraccion_v3` | pendiente (etapa 3, extra 2) | Pide `observaciones_visuales` (legibilidad, recortes, alteraciones) para las alertas `VIS-xxx`. El plan lo llamaba `extraccion_v2`; se renumera porque la v2 ya se usa | - |

Nota: el borrador `extraccion_v2.md` (fechas convertidas por el modelo) queda como referencia de lo
que no funciono. La evidencia del borrador v2b pide seccion; en la v2 definitiva, el parseo de vision
se queda solo con `pagina_<n>` (seccion 4).

## 6. Otras decisiones

| Decision | Detalle | Origen | Estado |
|---|---|---|---|
| API publica por modulo | Los demas modulos solo importan `configuracion/servicio.py` (`cargar`, `obtener`, `listar`) | ADR-005 | implementado |
| Validacion estricta de YAML | Claves desconocidas prohibidas; todos los errores de todos los ficheros en un unico `ErrorConfiguracion` | plan del cargador | implementado |
| `CONFIG_DIR` y `PROMPTS_DIR` | Variables de entorno opcionales; por defecto, rutas relativas a la raiz del repo | plan del cargador | `CONFIG_DIR` implementado; `PROMPTS_DIR` en la tarea 5 |
| Modalidad: umbral | `UMBRAL_CARACTERES_POR_PAGINA = 30` | plan de `modalidad.py` | decidido (tarea 2) |
| Modalidad: PDF mixto | Si alguna pagina no supera el umbral, el PDF es `pdf_escaneado` | plan de `modalidad.py` | decidido (tarea 2) |
| Modalidad: deteccion | Por los primeros bytes (`%PDF`, PNG, JPEG); si no coinciden con la extension, manda el contenido; formato desconocido o PDF corrupto -> `FormatoNoSoportado` | plan de `modalidad.py` | decidido (tarea 2) |
| CLI sin BD ni S3 | `folio_solicitud = "CLI-2026-000000"`; `referencia_archivo_original.ruta = "local://<nombre_archivo>"` (sin rutas personales); `hash` = SHA-256 real del archivo | objetivo de la etapa 1 | decidido (tarea 10) |
| Codigos de alerta del motor | `CLS-001` (critica): tipo declarado distinto del detectado. `SYS-001` (critica): fallo del proveedor sin respaldo. El catalogo `docs/contratos/codigos_alertas.md` se acepto en ADR-006; llega a `main` con el PR de contratos | prompt de PERSONA_2, ADR-006 | decidido |
| `Tarea.validacion` (Contrato 3) | Se ignora: la validacion son reglas deterministas en `validacion/reglas.py`, sin modelo. No se cambia el contrato | analisis de la etapa 0 | decidido |
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
- [ ] **Fixtures de PERSONA_3** (`fixtures/generados/`, en `.gitignore`: cada persona los genera en local).
- [ ] **OpenRouter**: crear la cuenta gratuita y probar los prompts con fixtures ficticios (propuesto al equipo).
- [ ] **PR pequeno de `.env.example`**: `OLLAMA_MODELO_TEXTO=gemma4:e2b`, `OLLAMA_MODELO_VISION=qwen2.5vl:3b`,
      `CONFIG_DIR`, `PROMPTS_DIR` y una nota sobre `OLLAMA_BASE_URL` en local.
- [ ] **Aplicar ADR-006**: 1.5 serializar `TipoDocumental` en `configuracion/servicio.py` (para
      `/tipos-documentales`) y 2.5 `tipo_confirmado` en `procesar_documento` (etapa 2).
- [ ] **Avisar al equipo del cambio en `CLAUDE.md`** (linea de la spec de PERSONA_2) al abrir el PR de
      etapa: es un fichero compartido.
- [ ] Aviso a PERSONA_1: `configuracion.cargar()` en el arranque de `main.py` (mensaje preparado).
- [ ] Riesgo: la confianza que da el modelo no es fiable (0,9-1 incluso en datos inventados).
- [ ] Riesgo: el modelo no es determinista ni con `temperature: 0`.
- [ ] Opcional: borrar `qwen2.5:7b` de Ollama local (4,7 GB, descartado).

## Registro de cambios

El mas reciente arriba.

| Fecha | Cambio | Commit |
|---|---|---|
| 2026-09-30 | Spec creada con las decisiones de configuracion y pruebas del motor IA; informe y material de pruebas en `docs/motor_ia/` | este commit |
| 2026-09-30 | Vision cerrada: `qwen2.5vl:3b`, fechas tal como aparecen + `normalizar_fecha`, imagenes a 1000 px, evidencia solo `pagina_<n>`, confianza del modelo fuera de las reglas | pruebas (sin codigo) |
| 2026-09-30 | Modelo de texto `gemma4:e2b`; enrutador: texto si `pdf_digital`, vision en el resto | pruebas (sin codigo) |
| 2026-09-30 | Descartados `gemma4` para vision (issue #16532), `gemma4:e4b`, `llama3.2-vision:11b` y `qwen2.5:7b` | pruebas (sin codigo) |
| 2026-09-30 | Cargador de fichas YAML: validacion estricta, `servicio.py`, `CONFIG_DIR` | `014e570` |
