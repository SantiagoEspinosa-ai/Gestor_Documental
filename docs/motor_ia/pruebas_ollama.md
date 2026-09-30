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

`--sin-think` es para modelos sin razonamiento, como `qwen2.5vl`. Las imagenes versionadas no se
regeneran; si se borran, los scripts las vuelven a crear. Las salidas crudas (`respuestas/`,
`log.txt`) no se versionan (ver `.gitignore`): pasaran a `backend/tests/respuestas_modelo/` en la tarea 7.
