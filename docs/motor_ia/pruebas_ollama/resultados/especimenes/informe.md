# Evaluacion completa del motor IA con los fixtures

Generado por `docs/motor_ia/pruebas_ollama/evaluar_fixtures.py`. Datos ficticios (fixtures de PERSONA_3).
Verdad de referencia: `fixtures/generados/INDICE.md`. Campo incorrecto = con valor distinto del
esperado (error silencioso); vacio = null.

## Nivel normal: criterios de aprobado

| Ruta | Modalidad | Aciertos | Vacios | Incorrectos | Minimo | Resultado |
|---|---|---|---|---|---|---|
| auto | digital | - | 0 | 0 | 49/51 | pendiente |
| auto | escaneado | - | 0 | 0 | 47/51 | pendiente |
| auto | foto | - | 0 | 0 | 47/51 | pendiente |
| vision | escaneado | - | 0 | 0 | 40/51 | pendiente |
| vision | foto | - | 0 | 0 | 40/51 | pendiente |

| Criterio | Valor | Minimo | Resultado |
|---|---|---|---|
| Tipo detectado correcto (normal, ruta auto) | 0/0 | 26/27 | pendiente |
| CLS-001 en los casos equivocados | 0/0 | 3/3 | pendiente |
| CLS-001 en casos correctos (falsos positivos) | 0 | 0 | APROBADO |
| Resultados con SYS-001 o SYS-002 (todos los bloques) | 0 | 0 | APROBADO |
| Excepciones (resultado no valido) | 0 | 0 | APROBADO |
| Abortos por RAM | 0 | 0 | APROBADO |

## Nivel normal: aciertos por tipo, modalidad y ruta

| Ruta | Tipo | Digital | Escaneado | Foto |
|---|---|---|---|---|

## Fixtures de dificultad: criterios de aprobado

| Nivel | Ruta | Metrica | Valor | Criterio | Resultado |
|---|---|---|---|---|---|
| dificil | auto | correctos | 0/0 | >= 26 | pendiente |
| dificil | auto | incorrectos | 0/0 | <= 3 | pendiente |
| dificil | auto | tipo_correcto | 0/0 | >= 6 | pendiente |
| extremo | auto | incorrectos | 0/0 | <= 7 | pendiente |
| extremo | auto | tipo_correcto | 0/0 | >= 4 | pendiente |
| extremo | auto | reintento si >= la mitad de obligatorios vacios | 0/0 | todos | pendiente |

## Fixtures de dificultad: correctos, vacios e incorrectos

| Nivel | Ruta | Modalidad | Correctos | Vacios | Incorrectos | Reintentos con vision | Usan vision |
|---|---|---|---|---|---|---|---|

Reintentos con vision (resultado con texto antes del reintento -> resultado final):

Ninguno.

## Campos que fallan (todos los bloques)

Ninguno.

## Especimenes (fotos de movil reales, bloque 5)

| Archivo | Caracteres OCR | Tipo | Correctos | Vacios | Incorrectos | Vision | Recomendacion | Alertas | Tiempo |
|---|---|---|---|---|---|---|---|---|---|
| `comprobante_domicilio_sano_especimen_buena.jpg` | 285 | ok | 4/4 | 0 | 0 | no | aprobar | - | 72.1 s |
| `comprobante_domicilio_sano_especimen_dificil.jpg` | 13 | ok | 4/4 | 0 | 0 | si | revision_manual | CLS-002, VAL-002[nombre_titular], VAL-002[domicilio], VAL-002[proveedor], VAL-002[fecha_emision] | 225.1 s |
| `credencial_elector_sano_especimen_buena.jpg` | 206 | ok | 6/6 | 0 | 0 | no | aprobar | - | 61.9 s |
| `credencial_elector_sano_especimen_dificil.jpg` | 207 | ok | 6/6 | 0 | 0 | no | aprobar | - | 58.9 s |
| `pasaporte_sano_especimen_buena.jpg` | 268 | ok | 7/7 | 0 | 0 | no | aprobar | - | 61.2 s |

Total: 27/27 (100 %) correctos, 0 vacios y 0 incorrectos; tipo correcto 5/5.

## Clasificacion con tipo declarado equivocado (CLS-001)

| Archivo | Declarado | Detectado | Alertas |
|---|---|---|---|
| - | - | - | - |

## Casos: tiempos, modelos, RAM y reintentos

| Caso | Nivel | Modalidad | Correctos | Vacios | Incorrectos | Tiempo | Llamadas | Vision (motivo) | RAM libre minima |
|---|---|---|---|---|---|---|---|---|---|
| `auto__comprobante_domicilio_sano_especimen_buena` | especimen | foto | 4/4 | 0 | 0 | 72.1 s | gemma4:e2b (texto) 30.42 s; gemma4:e2b (texto) 39.74 s | no | 2.7 GB |
| `auto__comprobante_domicilio_sano_especimen_dificil` | especimen | foto | 4/4 | 0 | 0 | 225.1 s | qwen2.5vl:3b (vision) 168.64 s; qwen2.5vl:3b (vision) 54.48 s | si (sin texto suficiente) | 1.41 GB |
| `auto__credencial_elector_sano_especimen_buena` | especimen | foto | 6/6 | 0 | 0 | 61.9 s | gemma4:e2b (texto) 12.58 s; gemma4:e2b (texto) 47.17 s | no | 2.61 GB |
| `auto__credencial_elector_sano_especimen_dificil` | especimen | foto | 6/6 | 0 | 0 | 58.9 s | gemma4:e2b (texto) 11.18 s; gemma4:e2b (texto) 45.25 s | no | 2.65 GB |
| `auto__pasaporte_sano_especimen_buena` | especimen | foto | 7/7 | 0 | 0 | 61.2 s | gemma4:e2b (texto) 11.04 s; gemma4:e2b (texto) 48.33 s | no | 2.62 GB |

## RAM por bloque

| Bloque | RAM libre minima | Abortado por RAM |
|---|---|---|
| 5 | 1.41 GB | no |
