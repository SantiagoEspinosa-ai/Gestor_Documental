# Pruebas de Ollama del motor IA (2026-09-30)

Objetivo: elegir los modelos locales de texto y de vision antes de escribir `proveedores/ollama.py`.
Decisiones resultantes: [SPEC_CONFIGURACION.md](SPEC_CONFIGURACION.md). Material para reproducirlas:
[pruebas_ollama/](pruebas_ollama/).

Todos los datos son inventados. Las pruebas solo llamaron a Ollama local; nada salio de la maquina.

## Maquina

| Recurso | Valor |
|---|---|
| Tipo | Maquina virtual (Hyper-V), Windows 11 |
| CPU | Xeon, 2 nucleos / 4 hilos |
| RAM | 16 GB, ~8 GB libres |
| GPU | No |
| Ollama | 0.34.4, local en `http://localhost:11434` |

La RAM libre nunca bajo de 3,5 GB. Cada script lleva un vigilante que detiene el modelo si baja de 1 GB.

## Documento de prueba

Pasaporte inventado, sin escudos, logotipos ni organismos reales, con la marca "DOCUMENTO DE MUESTRA -
SIN VALIDEZ". Variantes: A (imagen limpia, 1200x850) y B (foto de movil simulada: rotacion, desenfoque,
ruido y JPEG de baja calidad). En el modo texto se envia el texto de A como lo sacaria PyMuPDF de un
`pdf_digital`.

| Campo | Valor inventado |
|---|---|
| `nombre_completo` | `ANA EJEMPLO PRUEBA` |
| `numero_pasaporte` | `X1234567P` |
| `fecha_nacimiento` | `01/01/1990` |
| `fecha_expedicion` | `10/05/2024` |
| `fecha_vencimiento` | `09/05/2034` (juego 1) / `25/07/2031` (juego 2) |
| `nacionalidad` | `PAIS FICTICIO` |
| `sexo` | `F` |

Fechas de prueba:
- Juego 1 (`imagenes/`): las tres fechas admiten las dos lecturas dia/mes o mes/dia.
- Juego 2 (`imagenes_fechas/`): `10/05/2024` es ambigua y `25/07/2031` tiene el dia mayor que 12,
  asi que solo admite una lectura. La MRZ se genera con las mismas fechas.

## Resultados

Tiempo de un documento nuevo: primera ejecucion con una imagen nueva, con el modelo ya en memoria.
Las repeticiones con la misma imagen son mas rapidas porque Ollama reutiliza lo ya procesado, y un
documento real nunca se beneficia de eso.

| # | Modelo | Entrada | Prompt | Clasificacion | Aciertos de extraccion | Tiempo de un documento nuevo | Veredicto |
|---|---|---|---|---|---|---|---|
| 1 | `gemma4:e2b` | imagen | v1 | ❌ `desconocido` | 0/7 (A, datos inventados con confianza 0,95), 0/7 (B) | ~50 s | descartado: no ve las imagenes |
| 2 | `qwen2.5vl:3b` | imagen | v1 | ✅ | 4/7 (lee los 7 valores, pero no convierte fechas ni respeta la evidencia) | ~125 s (B) | base de la vision |
| 3 | `qwen2.5vl:3b` | texto | v1 | ✅ | 4/7 | ~39 s | no aporta frente al 4 |
| 4 | **`gemma4:e2b`** | **texto** | v1 | ✅ | **7/7 y 7/7** | **~37 s** | **modelo de texto** |
| 5 | `qwen2.5:7b` | texto | v1 | ✅ | 6/7 y 7/7 | ~75 s | descartado: el doble de lento |
| 6 | `qwen2.5vl:3b` | imagen | v2 (fechas convertidas por el modelo) | - | 5/7 (A y B); 6/7 (B a 1000 y 800 px) | 101-137 s | intercambia dia y mes |
| 7 | **`qwen2.5vl:3b`** | **imagen a 1000 px** | **v2b (fechas tal como aparecen) + `normalizar_fecha`** | - | **7/7 en 4 de 4 (A y B); fechas 3/3** | **~110 s** | **modelo de vision** |

Diagnosticos:

| Prueba | `gemma4:e2b` | `qwen2.5vl:3b` |
|---|---|---|
| Imagen con "HOLA" grande sobre blanco | `'Que'` (repite la primera palabra de la pregunta) ❌ | `'HOLA'` ✅ |
| Transcribir el texto de la imagen A | "una tabla con muchas filas" y una lista de numeros del 1 al 100 ❌ | - |

Detalle por escenario en `pruebas_ollama/resultados/<escenario>/resumen.json`.

## Medida del contexto (`num_ctx`)

`prueba_num_ctx.py`, con `qwen2.5vl:3b`, `num_ctx=16384`, el prompt real `extraccion_v2` y paginas A4
inventadas a 1000 px (1000x1414). `num_predict=1`: solo se mide la lectura del prompt.

| Escenario | Tokens de entrada | Tiempo |
|---|---|---|
| 1 pagina, sin texto | 2 457 (~1 850 de la imagen) | 133 s |
| 4 paginas + 20 000 caracteres de texto de relleno | 13 476 | 499 s |

Con los 800 tokens de salida (`num_predict`) quedan ~2 100 de margen: `NUM_CTX = 16384` es suficiente.
El tiempo obliga a que el timeout de vision dependa del numero de imagenes (60 s + 150 s por imagen).
RAM libre minima: 3,1 GB.

## Ejecucion del CLI (entregable de la etapa 1)

2026-09-30. `python -m app.modulos.motor_ia.cli fixtures/generados/pasaporte_sano_digital.pdf --tipo pasaporte`
en el contenedor del backend, contra el Ollama del equipo (`OLLAMA_BASE_URL=http://host.docker.internal:11434`).
Fixture de PERSONA_3 del caso `sano`, datos ficticios. Una modalidad cada vez, descargando los modelos entre
una y otra y con el vigilante de RAM (aborta por debajo de 1 GB).

| Modalidad | RAM libre al empezar | Ejecutado | Tiempo total | Llamadas | Campos correctos (`INDICE.md`) | Estado y alertas |
|---|---|---|---|---|---|---|
| `pasaporte_sano_digital.pdf` | 6,30 GB | si | 68 s | clasificacion 27 s + extraccion 38 s (`gemma4:e2b`, sin reintentos) | **7/7** | `completado`, sin alertas |
| `pasaporte_sano_escaneado.pdf` | 6,25 GB | no: faltaban 0,25 GB para el margen de 6,5 GB | - | - | - | - |
| `pasaporte_sano_foto.jpg` | 6,26 GB | no: faltaban 0,24 GB para el margen de 6,5 GB | - | - | - | - |

- Resultado del digital: `pruebas_ollama/resultados/cli/pasaporte_sano_digital.json` (`ResultadoDocumento`
  valido). Detectado `pasaporte` (igual al declarado), `version_prompt` `extraccion_pasaporte@v2`, modelo real
  `gemma4:e2b`, referencia `local://pasaporte_sano_digital.pdf` con el SHA-256 de `INDICE.md`.
- RAM libre minima durante el digital: 3,1 GB. El respaldo comercial quedo desactivado por la barrera de privacidad.
- Confianza del modelo: 1,0 en los 7 campos (otra vez sin informacion; ADR-007).
- Evidencia: `pagina_1:seccion_central` en los 7 campos; valida, pero no dice donde esta cada dato.
- Vision: pendiente de ejecutar cuando haya RAM suficiente (`qwen2.5vl:3b` consume ~5 GB) o la maquina con GPU.
  No se lanzo con el margen reducido.

## Alternativas para documentos sin capa de texto (2026-10-01)

`pasaporte_sano_escaneado.pdf` y `pasaporte_sano_foto.jpg` (fixtures de PERSONA_3, datos ficticios), con
`preparar()` + `analizar()` en el contenedor del backend contra el Ollama del equipo. Un modelo cada vez,
descargando los modelos entre casos y con el vigilante de RAM (aborta por debajo de 1 GB).

- **A**: OCR (Tesseract en el contenedor) + modelo de texto `gemma4:e2b`, sin imagenes.
- **B**: `qwen2.5vl:3b` (vision) con `num_ctx = 8192`.

| Alternativa | Fichero | Campos correctos (`INDICE.md`) | Tiempo total | RAM libre minima | Detalle |
|---|---|---|---|---|---|
| **A** | escaneado | **7/7** | **70 s** | **3,17 GB** | OCR 1,9 s + clasificacion 28 s + extraccion 40 s |
| **A** | foto | **7/7** | **66 s** | **3,55 GB** | OCR 0,8 s + 27 s + 38 s |
| B | escaneado | 6/7 | 135 s | 2,24 GB | clasificacion 91 s + extraccion 42 s; falta `fecha_expedicion` |
| B | foto | 6/7 | 123 s | 2,17 GB | 81 s + 41 s; falta `fecha_expedicion` |

RAM de `qwen2.5vl:3b` segun `num_ctx` (1 pagina, `num_predict=1`):

| `num_ctx` | Tamano del modelo en Ollama | RAM consumida | RAM libre minima |
|---|---|---|---|
| 16384 | 3,50 GB | 4,39 GB | 1,92 GB |
| 8192 | 3,21 GB | 4,27 GB | 2,22 GB |

Conclusiones:
- Con texto OCR suficiente (~310 caracteres por pagina en estos fixtures), el modelo de texto acierta mas y
  tarda la mitad que la vision. Regla nueva del enrutador: texto si todas las paginas tienen >= 30 caracteres
  (capa del PDF u OCR); vision si no, o como reintento si la extraccion con texto sale muy incompleta
  (`SPEC_CONFIGURACION.md`, seccion 3).
- Bajar `num_ctx` a 8192 apenas ahorra RAM: se mantiene fijo a 16384.
- El margen de 6,5 GB que impidio la vision el 2026-09-30 era conservador: para 1 pagina bastan ~5,8 GB.
- La evidencia de A vuelve a ser `pagina_1:seccion_central` en todos los campos (pendiente de mejorar).

Resultados: `pruebas_ollama/resultados/alternativas_vision/` (`A_*.json` y `B_*.json` con la medida y el
`ResultadoDocumento`; `ram_num_ctx.json`).

## Fallo de gemma4 con imagenes en Windows

`gemma4` anuncia vision, pero en Ollama para Windows no procesa las imagenes: el codificador recibe
la imagen vacia y el modelo responde como si no la hubiera, o se inventa los datos.
- Issue [ollama#16532](https://github.com/ollama/ollama/issues/16532) "gemma4 does not process images
  on windows": abierto a 2026-09-30. Otra incidencia ya cerrada, #18560, describe lo mismo.
- Ni la 0.35.0 ni la 0.35.1-rc0 incluyen un arreglo. No se ha actualizado Ollama.
- Segun usuarios del issue, la variante `gemma4:e4b-it-qat` si ve imagenes. Sin probar.

## Conclusiones

1. Para `pdf_digital` basta con el texto, y da mejores resultados que la imagen: `gemma4:e2b`, 7/7 en ~37 s.
2. Para vision, `qwen2.5vl:3b` lee bien los valores, pero hay que corregir su salida en codigo:
   - las fechas se piden tal como aparecen y se normalizan con dia/mes/anio;
   - las imagenes se reducen a 1000 px;
   - la evidencia se reduce a `pagina_<n>`.
3. La confianza que devuelve el modelo no sirve para decidir: da 0,9-1 incluso en datos inventados.
4. Ni con `temperature: 0` hay determinismo: los tests usan respuestas guardadas.
5. Esta maquina no sirve para la demo: ~110 s por pagina con vision. Hace falta la maquina con GPU.

## Como reproducirlas

Con el venv del backend, desde `docs/motor_ia/pruebas_ollama/` (Ollama local en marcha):

| Script | Que hace |
|---|---|
| `prueba_ollama.py --modelo <m> [--sin-think] [--modo texto]` | Escenarios 1 a 5 (clasificacion y extraccion, prompts v1) |
| `prueba_vision_v2.py --modelo qwen2.5vl:3b --sin-think` | Escenario 6 (borrador v2; A, B, B a 1000 y 800 px) |
| `prueba_fechas.py --modelo qwen2.5vl:3b --sin-think` | Escenario 7 (borrador v2b + `normalizar_fecha`; juego 2 de fechas) |
| `diagnostico_hola.py --modelo <m> [--sin-think]` | Imagen con "HOLA" |
| `diagnostico_transcripcion.py --modelo <m>` | Transcripcion literal con tope de tokens |
| `prueba_num_ctx.py --modelo qwen2.5vl:3b --num-ctx 16384` | Tokens de 1 y de 4 paginas A4 con el prompt real |

`--sin-think` es para modelos sin razonamiento, como `qwen2.5vl`. Las imagenes versionadas no se
regeneran; si se borran, los scripts las vuelven a crear. Las salidas crudas (`respuestas/`,
`log.txt`) no se versionan (ver `.gitignore`): pasaran a `backend/tests/respuestas_modelo/` en la tarea 7.
