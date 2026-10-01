# Evaluacion completa del motor IA con los fixtures

Generado por `docs/motor_ia/pruebas_ollama/evaluar_fixtures.py`. Datos ficticios (fixtures de PERSONA_3).
Verdad de referencia: `fixtures/generados/INDICE.md`. Campo incorrecto = con valor distinto del
esperado (error silencioso); vacio = null.

## Nivel normal: criterios de aprobado

| Ruta | Modalidad | Aciertos | Vacios | Incorrectos | Minimo | Resultado |
|---|---|---|---|---|---|---|
| auto | digital | 51/51 (100 %) | 0 | 0 | 49/51 | APROBADO |
| auto | escaneado | 51/51 (100 %) | 0 | 0 | 47/51 | APROBADO |
| auto | foto | 51/51 (100 %) | 0 | 0 | 47/51 | APROBADO |
| vision | escaneado | - | 0 | 0 | 40/51 | pendiente |
| vision | foto | - | 0 | 0 | 40/51 | pendiente |

| Criterio | Valor | Minimo | Resultado |
|---|---|---|---|
| Tipo detectado correcto (normal, ruta auto) | 27/27 | 26/27 | APROBADO |
| CLS-001 en los casos equivocados | 3/3 | 3/3 | APROBADO |
| CLS-001 en casos correctos (falsos positivos) | 0 | 0 | APROBADO |
| Resultados con SYS-001 o SYS-002 (todos los bloques) | 0 | 0 | APROBADO |
| Excepciones (resultado no valido) | 0 | 0 | APROBADO |
| Abortos por RAM | 0 | 0 | APROBADO |
| Tiempo medio por documento (normal, ruta auto, informativo) | 59 s | <= 90 s | si |

## Nivel normal: aciertos por tipo, modalidad y ruta

| Ruta | Tipo | Digital | Escaneado | Foto |
|---|---|---|---|---|
| auto | comprobante_domicilio | 12/12 (100 %) | 12/12 (100 %) | 12/12 (100 %) |
| auto | credencial_elector | 18/18 (100 %) | 18/18 (100 %) | 18/18 (100 %) |
| auto | pasaporte | 21/21 (100 %) | 21/21 (100 %) | 21/21 (100 %) |

## Fixtures de dificultad: criterios de aprobado

| Nivel | Ruta | Metrica | Valor | Criterio | Resultado |
|---|---|---|---|---|---|
| dificil | auto | correctos | 31/34 | >= 26 | APROBADO |
| dificil | auto | incorrectos | 2/34 | <= 3 | APROBADO |
| dificil | auto | tipo_correcto | 6/6 | >= 6 | APROBADO |
| extremo | auto | incorrectos | 6/34 | <= 7 | APROBADO |
| extremo | auto | tipo_correcto | 6/6 | >= 4 | APROBADO (referencia) |
| extremo | auto | reintento si >= la mitad de obligatorios vacios | 0/0 | todos | APROBADO |

## Fixtures de dificultad: correctos, vacios e incorrectos

| Nivel | Ruta | Modalidad | Correctos | Vacios | Incorrectos | Reintentos con vision | Usan vision |
|---|---|---|---|---|---|---|---|
| dificil | auto | escaneado | 16/17 (94 %) | 0 | 1 | 2/3 | 2/3 |
| dificil | auto | foto | 15/17 (88 %) | 1 | 1 | 1/3 | 1/3 |
| dificil | vision | escaneado | 17/17 (100 %) | 0 | 0 | 0/3 | 1/3 |
| dificil | vision | foto | 16/17 (94 %) | 0 | 1 | 0/3 | 1/3 |
| extremo | auto | escaneado | 14/17 (82 %) | 0 | 3 | 0/3 | 2/3 |
| extremo | auto | foto | 14/17 (82 %) | 0 | 3 | 0/3 | 3/3 |
| extremo | vision | escaneado | 17/17 (100 %) | 0 | 0 | 0/3 | 1/3 |
| extremo | vision | foto | 14/17 (82 %) | 0 | 3 | 0/3 | 1/3 |

**Nota: la ruta `vision` mezcla versiones del prompt de extraccion** (resultados de ejecuciones distintas; se deja como referencia):
- `extraccion_v2`: 8 casos
- `extraccion_v3`: 4 casos (`vision__pasaporte_sano_escaneado_dificil`, `vision__pasaporte_sano_escaneado_extremo`, `vision__pasaporte_sano_foto_dificil`, `vision__pasaporte_sano_foto_extremo`)

Reintentos con vision (resultado con texto antes del reintento -> resultado final):

| Caso | Antes: correctos / vacios / incorrectos | Despues: correctos / vacios / incorrectos |
|---|---|---|
| `auto__credencial_elector_sano_escaneado_dificil` | 5 / 0 / 1 | 6 / 0 / 0 |
| `auto__pasaporte_sano_escaneado_dificil` | 4 / 1 / 2 | 7 / 0 / 0 |
| `auto__pasaporte_sano_foto_dificil` | 4 / 0 / 3 | 6 / 0 / 1 |

## Campos que fallan (todos los bloques)

| Ruta | Nivel | Archivo | Campo | Estado | Esperado | Extraido |
|---|---|---|---|---|---|---|
| auto | dificil | `comprobante_domicilio_sano_escaneado_dificil.pdf` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | GALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO |
| auto | dificil | `credencial_elector_sano_foto_dificil.jpg` | `vigencia` | vacio | 2029 | None |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 2X0000001 |
| vision | dificil | `pasaporte_sano_foto_dificil.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 2X0000001 |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | Cormero de pense |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `nombre_titular` | incorrecto | ANA EJEMPLO PRUEBA | orta11 Of PAODO moon YA TIO |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `proveedor` | incorrecto | SERVICIOS DE EJEMPLO S.A. | SERVICIOS DE EJEMPLO S A. |
| auto | extremo | `credencial_elector_sano_foto_extremo.jpg` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA000101MDFXXX01 |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `nombre_completo` | incorrecto | ANA EJEMPLO PRUEBA | AMA EJEMPLO PRUEBA |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 000000! |
| vision | extremo | `credencial_elector_sano_foto_extremo.jpg` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA000101MDFXXX01 |
| vision | extremo | `pasaporte_sano_foto_extremo.jpg` | `nombre_completo` | incorrecto | ANA EJEMPLO PRUEBA | AMA EJEMPLO PRUEBA |
| vision | extremo | `pasaporte_sano_foto_extremo.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 000000! |

## Clasificacion con tipo declarado equivocado (CLS-001)

| Archivo | Declarado | Detectado | Alertas |
|---|---|---|---|
| `comprobante_domicilio_sano_escaneado.pdf` | pasaporte | comprobante_domicilio | CLS-001 |
| `credencial_elector_sano_digital.pdf` | pasaporte | credencial_elector | CLS-001 |
| `pasaporte_sano_foto.jpg` | credencial_elector | pasaporte | CLS-001 |

## Casos: tiempos, modelos, RAM y reintentos

| Caso | Nivel | Modalidad | Correctos | Vacios | Incorrectos | Tiempo | Llamadas | Vision (motivo) | RAM libre minima |
|---|---|---|---|---|---|---|---|---|---|
| `auto__comprobante_domicilio_sano_escaneado_dificil` | dificil | escaneado | 3/4 | 0 | 1 | 67.6 s | gemma4:e2b (texto) 28.41 s; gemma4:e2b (texto) 37.46 s | no | 5.44 GB |
| `auto__comprobante_domicilio_sano_foto_dificil` | dificil | foto | 4/4 | 0 | 0 | 49.2 s | gemma4:e2b (texto) 10.13 s; gemma4:e2b (texto) 37.99 s | no | 5.33 GB |
| `auto__credencial_elector_sano_escaneado_dificil` | dificil | escaneado | 6/6 | 0 | 0 | 224.5 s | gemma4:e2b (texto) 29.47 s; gemma4:e2b (texto) 51.94 s; qwen2.5vl:3b (vision) 142.05 s | reintento con vision: formato invalido en curp con texto | 3.71 GB |
| `auto__credencial_elector_sano_foto_dificil` | dificil | foto | 5/6 | 1 | 0 | 82.9 s | gemma4:e2b (texto) 29.5 s; gemma4:e2b (texto) 52.7 s | no | 3.96 GB |
| `auto__pasaporte_sano_escaneado_dificil` | dificil | escaneado | 7/7 | 0 | 0 | 244.0 s | gemma4:e2b (texto) 28.71 s; gemma4:e2b (texto) 56.01 s; qwen2.5vl:3b (vision) 157.41 s | reintento con vision: formato invalido en numero_pasaporte con texto | 3.26 GB |
| `auto__pasaporte_sano_foto_dificil` | dificil | foto | 6/7 | 0 | 1 | 228.6 s | gemma4:e2b (texto) 29.1 s; gemma4:e2b (texto) 55.3 s; qwen2.5vl:3b (vision) 143.25 s | reintento con vision: formato invalido en fecha_expedicion, fecha_vencimiento con texto | 4.21 GB |
| `vision__comprobante_domicilio_sano_escaneado_dificil` | dificil | escaneado | 4/4 | 0 | 0 | 195.1 s | qwen2.5vl:3b (vision) 140.85 s; qwen2.5vl:3b (vision) 52.09 s | no | 2.46 GB |
| `vision__comprobante_domicilio_sano_foto_dificil` | dificil | foto | 4/4 | 0 | 0 | 172.2 s | qwen2.5vl:3b (vision) 120.99 s; qwen2.5vl:3b (vision) 49.86 s | no | 1.42 GB |
| `vision__credencial_elector_sano_escaneado_dificil` | dificil | escaneado | 6/6 | 0 | 0 | 142.0 s | qwen2.5vl:3b (vision) 77.28 s; qwen2.5vl:3b (vision) 63.29 s | no | 3.4 GB |
| `vision__credencial_elector_sano_foto_dificil` | dificil | foto | 6/6 | 0 | 0 | 138.3 s | qwen2.5vl:3b (vision) 76.28 s; qwen2.5vl:3b (vision) 61.35 s | no | 3.22 GB |
| `vision__pasaporte_sano_escaneado_dificil` | dificil | escaneado | 7/7 | 0 | 0 | 149.7 s | qwen2.5vl:3b (vision) 82.95 s; qwen2.5vl:3b (vision) 65.5 s | si (sin texto suficiente) | 3.44 GB |
| `vision__pasaporte_sano_foto_dificil` | dificil | foto | 6/7 | 0 | 1 | 144.0 s | qwen2.5vl:3b (vision) 74.36 s; qwen2.5vl:3b (vision) 68.81 s | si (sin texto suficiente) | 3.45 GB |
| `auto__comprobante_domicilio_sano_escaneado_extremo` | extremo | escaneado | 1/4 | 0 | 3 | 47.5 s | gemma4:e2b (texto) 11.1 s; gemma4:e2b (texto) 34.61 s | no | 5.33 GB |
| `auto__comprobante_domicilio_sano_foto_extremo` | extremo | foto | 4/4 | 0 | 0 | 193.4 s | gemma4:e2b (texto) 9.67 s; qwen2.5vl:3b (vision) 125.68 s; qwen2.5vl:3b (vision) 57.28 s | reclasificacion con vision: la clasificacion con texto dio desconocido; extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido) | 3.78 GB |
| `auto__credencial_elector_sano_escaneado_extremo` | extremo | escaneado | 6/6 | 0 | 0 | 176.0 s | gemma4:e2b (texto) 28.38 s; qwen2.5vl:3b (vision) 82.87 s; qwen2.5vl:3b (vision) 63.9 s | reclasificacion con vision: la clasificacion con texto dio desconocido; extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido) | 3.92 GB |
| `auto__credencial_elector_sano_foto_extremo` | extremo | foto | 5/6 | 0 | 1 | 149.1 s | qwen2.5vl:3b (vision) 79.85 s; qwen2.5vl:3b (vision) 68.53 s | si (sin texto suficiente) | 3.93 GB |
| `auto__pasaporte_sano_escaneado_extremo` | extremo | escaneado | 7/7 | 0 | 0 | 187.0 s | gemma4:e2b (texto) 28.35 s; qwen2.5vl:3b (vision) 84.82 s; qwen2.5vl:3b (vision) 71.44 s | reclasificacion con vision: la clasificacion con texto dio desconocido; extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido) | 3.66 GB |
| `auto__pasaporte_sano_foto_extremo` | extremo | foto | 5/7 | 0 | 2 | 183.1 s | gemma4:e2b (texto) 27.56 s; qwen2.5vl:3b (vision) 86.92 s; qwen2.5vl:3b (vision) 67.86 s | reclasificacion con vision: la clasificacion con texto dio desconocido; extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido) | 4.26 GB |
| `vision__comprobante_domicilio_sano_escaneado_extremo` | extremo | escaneado | 4/4 | 0 | 0 | 182.3 s | qwen2.5vl:3b (vision) 114.17 s; qwen2.5vl:3b (vision) 66.68 s | no | 1.74 GB |
| `vision__comprobante_domicilio_sano_foto_extremo` | extremo | foto | 4/4 | 0 | 0 | 173.0 s | qwen2.5vl:3b (vision) 118.86 s; qwen2.5vl:3b (vision) 53.28 s | no | 1.88 GB |
| `vision__credencial_elector_sano_escaneado_extremo` | extremo | escaneado | 6/6 | 0 | 0 | 140.7 s | qwen2.5vl:3b (vision) 71.39 s; qwen2.5vl:3b (vision) 68.26 s | no | 3.32 GB |
| `vision__credencial_elector_sano_foto_extremo` | extremo | foto | 5/6 | 0 | 1 | 137.4 s | qwen2.5vl:3b (vision) 74.01 s; qwen2.5vl:3b (vision) 62.65 s | no | 2.95 GB |
| `vision__pasaporte_sano_escaneado_extremo` | extremo | escaneado | 7/7 | 0 | 0 | 140.1 s | qwen2.5vl:3b (vision) 72.68 s; qwen2.5vl:3b (vision) 66.35 s | si (sin texto suficiente) | 3.48 GB |
| `vision__pasaporte_sano_foto_extremo` | extremo | foto | 5/7 | 0 | 2 | 145.6 s | qwen2.5vl:3b (vision) 75.64 s; qwen2.5vl:3b (vision) 69.09 s | si (sin texto suficiente) | 3.31 GB |
| `auto__comprobante_domicilio_domicilio_distinto_digital` | normal | digital | 4/4 | 0 | 0 | 67.8 s | gemma4:e2b (texto) 29.06 s; gemma4:e2b (texto) 38.53 s | no | 5.85 GB |
| `auto__comprobante_domicilio_domicilio_distinto_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 52.0 s | gemma4:e2b (texto) 10.27 s; gemma4:e2b (texto) 39.31 s | no | 5.7 GB |
| `auto__comprobante_domicilio_domicilio_distinto_foto` | normal | foto | 4/4 | 0 | 0 | 49.5 s | gemma4:e2b (texto) 10.38 s; gemma4:e2b (texto) 38.02 s | no | 5.73 GB |
| `auto__comprobante_domicilio_sano_digital` | normal | digital | 4/4 | 0 | 0 | 51.2 s | gemma4:e2b (texto) 10.94 s; gemma4:e2b (texto) 40.2 s | no | 5.67 GB |
| `auto__comprobante_domicilio_sano_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 50.7 s | gemma4:e2b (texto) 10.36 s; gemma4:e2b (texto) 38.09 s | no | 5.63 GB |
| `auto__comprobante_domicilio_sano_foto` | normal | foto | 4/4 | 0 | 0 | 49.9 s | gemma4:e2b (texto) 10.52 s; gemma4:e2b (texto) 38.35 s | no | 5.57 GB |
| `auto__comprobante_domicilio_vencido_digital` | normal | digital | 4/4 | 0 | 0 | 48.9 s | gemma4:e2b (texto) 10.89 s; gemma4:e2b (texto) 37.97 s | no | 5.54 GB |
| `auto__comprobante_domicilio_vencido_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 51.8 s | gemma4:e2b (texto) 11.36 s; gemma4:e2b (texto) 38.1 s | no | 5.54 GB |
| `auto__comprobante_domicilio_vencido_foto` | normal | foto | 4/4 | 0 | 0 | 48.3 s | gemma4:e2b (texto) 9.95 s; gemma4:e2b (texto) 37.37 s | no | 5.49 GB |
| `auto__credencial_elector_domicilio_distinto_digital` | normal | digital | 6/6 | 0 | 0 | 72.1 s | gemma4:e2b (texto) 15.67 s; gemma4:e2b (texto) 56.43 s | no | 5.26 GB |
| `auto__credencial_elector_domicilio_distinto_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 61.5 s | gemma4:e2b (texto) 11.24 s; gemma4:e2b (texto) 48.91 s | no | 5.46 GB |
| `auto__credencial_elector_domicilio_distinto_foto` | normal | foto | 6/6 | 0 | 0 | 61.4 s | gemma4:e2b (texto) 11.26 s; gemma4:e2b (texto) 49.54 s | no | 5.46 GB |
| `auto__credencial_elector_sano_digital` | normal | digital | 6/6 | 0 | 0 | 53.2 s | gemma4:e2b (texto) 9.74 s; gemma4:e2b (texto) 43.43 s | no | 5.46 GB |
| `auto__credencial_elector_sano_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 63.1 s | gemma4:e2b (texto) 11.45 s; gemma4:e2b (texto) 50.22 s | no | 5.38 GB |
| `auto__credencial_elector_sano_foto` | normal | foto | 6/6 | 0 | 0 | 63.8 s | gemma4:e2b (texto) 12.79 s; gemma4:e2b (texto) 50.39 s | no | 5.35 GB |
| `auto__credencial_elector_vencido_digital` | normal | digital | 6/6 | 0 | 0 | 62.7 s | gemma4:e2b (texto) 13.24 s; gemma4:e2b (texto) 49.38 s | no | 5.61 GB |
| `auto__credencial_elector_vencido_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 71.9 s | gemma4:e2b (texto) 10.9 s; gemma4:e2b (texto) 59.69 s | no | 5.21 GB |
| `auto__credencial_elector_vencido_foto` | normal | foto | 6/6 | 0 | 0 | 53.2 s | gemma4:e2b (texto) 8.35 s; gemma4:e2b (texto) 44.18 s | no | 5.53 GB |
| `auto__pasaporte_domicilio_distinto_digital` | normal | digital | 7/7 | 0 | 0 | 67.2 s | gemma4:e2b (texto) 11.44 s; gemma4:e2b (texto) 55.73 s | no | 5.31 GB |
| `auto__pasaporte_domicilio_distinto_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 73.2 s | gemma4:e2b (texto) 12.83 s; gemma4:e2b (texto) 58.68 s | no | 5.18 GB |
| `auto__pasaporte_domicilio_distinto_foto` | normal | foto | 7/7 | 0 | 0 | 56.1 s | gemma4:e2b (texto) 8.75 s; gemma4:e2b (texto) 46.52 s | no | 5.34 GB |
| `auto__pasaporte_sano_digital` | normal | digital | 7/7 | 0 | 0 | 55.2 s | gemma4:e2b (texto) 9.36 s; gemma4:e2b (texto) 45.81 s | no | 5.36 GB |
| `auto__pasaporte_sano_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 67.5 s | gemma4:e2b (texto) 13.36 s; gemma4:e2b (texto) 52.39 s | no | 5.34 GB |
| `auto__pasaporte_sano_foto` | normal | foto | 7/7 | 0 | 0 | 55.6 s | gemma4:e2b (texto) 8.63 s; gemma4:e2b (texto) 46.17 s | no | 5.29 GB |
| `auto__pasaporte_vencido_digital` | normal | digital | 7/7 | 0 | 0 | 65.2 s | gemma4:e2b (texto) 12.95 s; gemma4:e2b (texto) 52.2 s | no | 5.29 GB |
| `auto__pasaporte_vencido_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 66.2 s | gemma4:e2b (texto) 12.31 s; gemma4:e2b (texto) 52.27 s | no | 5.27 GB |
| `auto__pasaporte_vencido_foto` | normal | foto | 7/7 | 0 | 0 | 64.5 s | gemma4:e2b (texto) 11.19 s; gemma4:e2b (texto) 52.53 s | no | 5.26 GB |
| `cls__comprobante_domicilio_sano_escaneado__como_pasaporte` | normal | escaneado | - | - | - | 55.6 s | gemma4:e2b (texto) 10.23 s; gemma4:e2b (texto) 43.28 s | no | 5.33 GB |
| `cls__credencial_elector_sano_digital__como_pasaporte` | normal | digital | - | - | - | 53.8 s | gemma4:e2b (texto) 9.36 s; gemma4:e2b (texto) 44.33 s | no | 5.23 GB |
| `cls__pasaporte_sano_foto__como_credencial_elector` | normal | foto | - | - | - | 54.4 s | gemma4:e2b (texto) 8.59 s; gemma4:e2b (texto) 44.89 s | no | 5.07 GB |

## RAM por bloque

| Bloque | RAM libre minima | Abortado por RAM |
|---|---|---|
| 1 | 5.07 GB | no |
| 3 | 3.26 GB | no |
| 4 | 3.31 GB | no |
