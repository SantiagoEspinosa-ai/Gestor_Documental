# Evaluacion completa del motor IA con los fixtures

Generado por `docs/motor_ia/pruebas_ollama/evaluar_fixtures.py`. Datos ficticios (fixtures de PERSONA_3).
Verdad de referencia: `fixtures/generados/INDICE.md`.

## Criterios de aprobado

| Ruta | Modalidad | Aciertos | Minimo | Resultado |
|---|---|---|---|---|
| auto | digital | 51/51 (100 %) | 49/51 | APROBADO |
| auto | escaneado | 51/51 (100 %) | 47/51 | APROBADO |
| auto | foto | 51/51 (100 %) | 47/51 | APROBADO |
| vision | escaneado | - | 40/51 | pendiente |
| vision | foto | - | 40/51 | pendiente |

| Criterio | Valor | Minimo | Resultado |
|---|---|---|---|
| Tipo detectado correcto (ruta auto) | 27/27 | 26/27 | APROBADO |
| CLS-001 en los casos equivocados | 3/3 | 3/3 | APROBADO |
| CLS-001 en casos correctos (falsos positivos) | 0 | 0 | APROBADO |
| Resultados con SYS-001 o SYS-002 | 0 | 0 | APROBADO |
| Excepciones (resultado no valido) | 0 | 0 | APROBADO |
| Abortos por RAM | 0 | 0 | APROBADO |
| Tiempo medio por documento (ruta auto, informativo) | 59 s | <= 90 s | si |

## Aciertos por tipo, modalidad y ruta

| Ruta | Tipo | Digital | Escaneado | Foto |
|---|---|---|---|---|
| auto | comprobante_domicilio | 12/12 (100 %) | 12/12 (100 %) | 12/12 (100 %) |
| auto | credencial_elector | 18/18 (100 %) | 18/18 (100 %) | 18/18 (100 %) |
| auto | pasaporte | 21/21 (100 %) | 21/21 (100 %) | 21/21 (100 %) |

## Campos que fallan

Ninguno.

## Clasificacion con tipo declarado equivocado (CLS-001)

| Archivo | Declarado | Detectado | Alertas |
|---|---|---|---|
| `comprobante_domicilio_sano_escaneado.pdf` | pasaporte | comprobante_domicilio | CLS-001 |
| `credencial_elector_sano_digital.pdf` | pasaporte | credencial_elector | CLS-001 |
| `pasaporte_sano_foto.jpg` | credencial_elector | pasaporte | CLS-001 |

## Casos: tiempos, modelos, RAM y reintentos

| Caso | Modalidad | Aciertos | Tiempo | Llamadas | Reintento con vision | RAM libre minima |
|---|---|---|---|---|---|---|
| `auto__comprobante_domicilio_domicilio_distinto_digital` | digital | 4/4 | 78.0 s | gemma4:e2b (texto) 39.93 s; gemma4:e2b (texto) 38.01 s | no | 4.41 GB |
| `auto__comprobante_domicilio_domicilio_distinto_escaneado` | escaneado | 4/4 | 50.9 s | gemma4:e2b (texto) 10.2 s; gemma4:e2b (texto) 38.45 s | no | 4.32 GB |
| `auto__comprobante_domicilio_domicilio_distinto_foto` | foto | 4/4 | 48.1 s | gemma4:e2b (texto) 10.53 s; gemma4:e2b (texto) 36.61 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_digital` | digital | 4/4 | 47.1 s | gemma4:e2b (texto) 10.36 s; gemma4:e2b (texto) 36.6 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_escaneado` | escaneado | 4/4 | 48.5 s | gemma4:e2b (texto) 10.13 s; gemma4:e2b (texto) 36.25 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_foto` | foto | 4/4 | 49.8 s | gemma4:e2b (texto) 11.53 s; gemma4:e2b (texto) 37.32 s | no | 4.26 GB |
| `auto__comprobante_domicilio_vencido_digital` | digital | 4/4 | 47.8 s | gemma4:e2b (texto) 11.07 s; gemma4:e2b (texto) 36.61 s | no | 4.31 GB |
| `auto__comprobante_domicilio_vencido_escaneado` | escaneado | 4/4 | 48.0 s | gemma4:e2b (texto) 11.44 s; gemma4:e2b (texto) 34.28 s | no | 4.22 GB |
| `auto__comprobante_domicilio_vencido_foto` | foto | 4/4 | 47.5 s | gemma4:e2b (texto) 10.02 s; gemma4:e2b (texto) 36.56 s | no | 4.19 GB |
| `auto__credencial_elector_domicilio_distinto_digital` | digital | 6/6 | 63.2 s | gemma4:e2b (texto) 12.91 s; gemma4:e2b (texto) 50.24 s | no | 4.02 GB |
| `auto__credencial_elector_domicilio_distinto_escaneado` | escaneado | 6/6 | 61.6 s | gemma4:e2b (texto) 12.28 s; gemma4:e2b (texto) 47.77 s | no | 4.08 GB |
| `auto__credencial_elector_domicilio_distinto_foto` | foto | 6/6 | 60.5 s | gemma4:e2b (texto) 11.12 s; gemma4:e2b (texto) 48.64 s | no | 4.26 GB |
| `auto__credencial_elector_sano_digital` | digital | 6/6 | 52.5 s | gemma4:e2b (texto) 9.64 s; gemma4:e2b (texto) 42.8 s | no | 4.26 GB |
| `auto__credencial_elector_sano_escaneado` | escaneado | 6/6 | 60.8 s | gemma4:e2b (texto) 11.43 s; gemma4:e2b (texto) 48.11 s | no | 4.2 GB |
| `auto__credencial_elector_sano_foto` | foto | 6/6 | 65.0 s | gemma4:e2b (texto) 14.32 s; gemma4:e2b (texto) 50.07 s | no | 3.96 GB |
| `auto__credencial_elector_vencido_digital` | digital | 6/6 | 61.5 s | gemma4:e2b (texto) 12.9 s; gemma4:e2b (texto) 48.55 s | no | 4.01 GB |
| `auto__credencial_elector_vencido_escaneado` | escaneado | 6/6 | 62.8 s | gemma4:e2b (texto) 10.67 s; gemma4:e2b (texto) 50.8 s | no | 3.9 GB |
| `auto__credencial_elector_vencido_foto` | foto | 6/6 | 56.2 s | gemma4:e2b (texto) 9.34 s; gemma4:e2b (texto) 45.51 s | no | 3.65 GB |
| `auto__pasaporte_domicilio_distinto_digital` | digital | 7/7 | 66.3 s | gemma4:e2b (texto) 12.34 s; gemma4:e2b (texto) 53.85 s | no | 3.67 GB |
| `auto__pasaporte_domicilio_distinto_escaneado` | escaneado | 7/7 | 72.4 s | gemma4:e2b (texto) 13.33 s; gemma4:e2b (texto) 57.18 s | no | 3.57 GB |
| `auto__pasaporte_domicilio_distinto_foto` | foto | 7/7 | 66.5 s | gemma4:e2b (texto) 12.61 s; gemma4:e2b (texto) 52.95 s | no | 3.23 GB |
| `auto__pasaporte_sano_digital` | digital | 7/7 | 56.6 s | gemma4:e2b (texto) 9.59 s; gemma4:e2b (texto) 46.87 s | no | 3.49 GB |
| `auto__pasaporte_sano_escaneado` | escaneado | 7/7 | 70.5 s | gemma4:e2b (texto) 13.47 s; gemma4:e2b (texto) 55.29 s | no | 3.36 GB |
| `auto__pasaporte_sano_foto` | foto | 7/7 | 57.0 s | gemma4:e2b (texto) 8.78 s; gemma4:e2b (texto) 47.36 s | no | 3.47 GB |
| `auto__pasaporte_vencido_digital` | digital | 7/7 | 66.0 s | gemma4:e2b (texto) 13.72 s; gemma4:e2b (texto) 52.12 s | no | 3.52 GB |
| `auto__pasaporte_vencido_escaneado` | escaneado | 7/7 | 71.3 s | gemma4:e2b (texto) 12.96 s; gemma4:e2b (texto) 56.61 s | no | 3.53 GB |
| `auto__pasaporte_vencido_foto` | foto | 7/7 | 69.0 s | gemma4:e2b (texto) 11.71 s; gemma4:e2b (texto) 56.31 s | no | 3.74 GB |
| `cls__comprobante_domicilio_sano_escaneado__como_pasaporte` | escaneado | - | 80.5 s | gemma4:e2b (texto) 30.1 s; gemma4:e2b (texto) 48.07 s | no | 4.39 GB |
| `cls__credencial_elector_sano_digital__como_pasaporte` | digital | - | 55.3 s | gemma4:e2b (texto) 9.97 s; gemma4:e2b (texto) 45.25 s | no | 3.74 GB |
| `cls__pasaporte_sano_foto__como_credencial_elector` | foto | - | 51.7 s | gemma4:e2b (texto) 8.76 s; gemma4:e2b (texto) 42.0 s | no | 3.7 GB |

## RAM por bloque

| Bloque | RAM libre minima | Abortado por RAM |
|---|---|---|
| 1 | 4.39 GB | no |
