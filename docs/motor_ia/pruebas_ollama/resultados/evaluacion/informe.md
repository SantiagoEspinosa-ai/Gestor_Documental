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
| CLS-001 en casos correctos (falsos positivos) | 4 | 0 | NO APROBADO |
| Resultados con SYS-001 o SYS-002 (todos los bloques) | 0 | 0 | APROBADO |
| Excepciones (resultado no valido) | 0 | 0 | APROBADO |
| Abortos por RAM | 1 | 0 | NO APROBADO |
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
| dificil | auto | correctos | 19/34 | >= 26 | NO APROBADO |
| dificil | auto | incorrectos | 7/34 | <= 3 | NO APROBADO |
| dificil | auto | tipo_correcto | 6/6 | >= 6 | APROBADO |
| extremo | auto | incorrectos | 10/34 | <= 7 | NO APROBADO |
| extremo | auto | tipo_correcto | 2/6 | >= 4 | NO APROBADO (referencia) |
| extremo | auto | reintento si >= la mitad de obligatorios vacios | 0/2 | todos | NO APROBADO |

## Fixtures de dificultad: correctos, vacios e incorrectos

| Nivel | Ruta | Modalidad | Correctos | Vacios | Incorrectos | Reintentos con vision |
|---|---|---|---|---|---|---|
| dificil | auto | escaneado | 10/17 (59 %) | 3 | 4 | 0/3 |
| dificil | auto | foto | 9/17 (53 %) | 5 | 3 | 0/3 |
| extremo | auto | escaneado | 3/17 (18 %) | 9 | 5 | 0/3 |
| extremo | auto | foto | 6/17 (35 %) | 6 | 5 | 0/3 |

Reintentos con vision (resultado con texto antes del reintento -> resultado final):

Ninguno.

## Campos que fallan (todos los bloques)

| Ruta | Nivel | Archivo | Campo | Estado | Esperado | Extraido |
|---|---|---|---|---|---|---|
| auto | dificil | `comprobante_domicilio_sano_escaneado_dificil.pdf` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | GALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO |
| auto | dificil | `credencial_elector_sano_escaneado_dificil.pdf` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA9O0101MDFXXX01 |
| auto | dificil | `credencial_elector_sano_foto_dificil.jpg` | `clave_elector` | vacio | EJPRAN90010199M101 | None |
| auto | dificil | `credencial_elector_sano_foto_dificil.jpg` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA900101MDFXXX01 EJPRAN90010199M101 |
| auto | dificil | `credencial_elector_sano_foto_dificil.jpg` | `vigencia` | vacio | 2029 | None |
| auto | dificil | `pasaporte_sano_escaneado_dificil.pdf` | `fecha_expedicion` | vacio | 2021-09-30 | None |
| auto | dificil | `pasaporte_sano_escaneado_dificil.pdf` | `fecha_nacimiento` | incorrecto | 1990-01-01 | 2021-09-30 |
| auto | dificil | `pasaporte_sano_escaneado_dificil.pdf` | `nacionalidad` | vacio | UTOPICA | None |
| auto | dificil | `pasaporte_sano_escaneado_dificil.pdf` | `numero_pasaporte` | incorrecto | ZX0000001 | X00000015UTO9001011F3109306 |
| auto | dificil | `pasaporte_sano_escaneado_dificil.pdf` | `sexo` | vacio | F | None |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `fecha_expedicion` | vacio | 2021-09-30 | None |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `fecha_vencimiento` | incorrecto | 2031-09-30 | 3009/2021 |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `nacionalidad` | vacio | UTOPICA | None |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 2X0000001 |
| auto | dificil | `pasaporte_sano_foto_dificil.jpg` | `sexo` | vacio | F | None |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | Cormero de pense rosa 34 |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `nombre_titular` | incorrecto | ANA EJEMPLO PRUEBA | orta11 Of PAODO moon YA TIO |
| auto | extremo | `comprobante_domicilio_sano_escaneado_extremo.pdf` | `proveedor` | vacio | SERVICIOS DE EJEMPLO S.A. | None |
| auto | extremo | `comprobante_domicilio_sano_foto_extremo.jpg` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | CALLE FICTICIA 123, SERVICIOS DE EJEMPLO SA. |
| auto | extremo | `comprobante_domicilio_sano_foto_extremo.jpg` | `fecha_emision` | incorrecto | 2026-09-15 | 1509 2026 |
| auto | extremo | `comprobante_domicilio_sano_foto_extremo.jpg` | `proveedor` | incorrecto | SERVICIOS DE EJEMPLO S.A. | carat Oak PURO MP |
| auto | extremo | `credencial_elector_sano_escaneado_extremo.pdf` | `clave_elector` | vacio | EJPRAN90010199M101 | None |
| auto | extremo | `credencial_elector_sano_escaneado_extremo.pdf` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA900 IOI MOF 100x0 1 ESPRANSOO1019904101 |
| auto | extremo | `credencial_elector_sano_escaneado_extremo.pdf` | `domicilio` | incorrecto | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO | CALLE FICTICIA 122, COLONIA DEMO, CIUDAD EJEMPLO |
| auto | extremo | `credencial_elector_sano_escaneado_extremo.pdf` | `fecha_nacimiento` | incorrecto | 1990-01-01 | 1990 |
| auto | extremo | `credencial_elector_sano_foto_extremo.jpg` | `curp` | incorrecto | AEPA900101MDFXXX01 | AEPA000101MDFXXX01 |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `fecha_expedicion` | vacio | 2021-09-30 | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `fecha_nacimiento` | vacio | 1990-01-01 | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `fecha_vencimiento` | vacio | 2031-09-30 | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `nacionalidad` | vacio | UTOPICA | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `nombre_completo` | vacio | ANA EJEMPLO PRUEBA | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `numero_pasaporte` | vacio | ZX0000001 | None |
| auto | extremo | `pasaporte_sano_escaneado_extremo.pdf` | `sexo` | vacio | F | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `fecha_expedicion` | vacio | 2021-09-30 | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `fecha_nacimiento` | vacio | 1990-01-01 | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `fecha_vencimiento` | vacio | 2031-09-30 | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `nacionalidad` | vacio | UTOPICA | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `nombre_completo` | vacio | ANA EJEMPLO PRUEBA | None |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `numero_pasaporte` | incorrecto | ZX0000001 | 1093060ccceeeecccecoó |
| auto | extremo | `pasaporte_sano_foto_extremo.jpg` | `sexo` | vacio | F | None |

## Clasificacion con tipo declarado equivocado (CLS-001)

| Archivo | Declarado | Detectado | Alertas |
|---|---|---|---|
| `comprobante_domicilio_sano_escaneado.pdf` | pasaporte | comprobante_domicilio | CLS-001 |
| `credencial_elector_sano_digital.pdf` | pasaporte | credencial_elector | CLS-001 |
| `pasaporte_sano_foto.jpg` | credencial_elector | pasaporte | CLS-001 |

## Casos: tiempos, modelos, RAM y reintentos

| Caso | Nivel | Modalidad | Correctos | Vacios | Incorrectos | Tiempo | Llamadas | Reintento con vision | RAM libre minima |
|---|---|---|---|---|---|---|---|---|---|
| `auto__comprobante_domicilio_sano_escaneado_dificil` | dificil | escaneado | 3/4 | 0 | 1 | 70.1 s | gemma4:e2b (texto) 29.83 s; gemma4:e2b (texto) 38.49 s | no | 4.08 GB |
| `auto__comprobante_domicilio_sano_foto_dificil` | dificil | foto | 4/4 | 0 | 0 | 48.4 s | gemma4:e2b (texto) 10.04 s; gemma4:e2b (texto) 37.08 s | no | 4.06 GB |
| `auto__credencial_elector_sano_escaneado_dificil` | dificil | escaneado | 5/6 | 0 | 1 | 60.7 s | gemma4:e2b (texto) 11.42 s; gemma4:e2b (texto) 48.4 s | no | 4.01 GB |
| `auto__credencial_elector_sano_foto_dificil` | dificil | foto | 3/6 | 2 | 1 | 62.4 s | gemma4:e2b (texto) 11.53 s; gemma4:e2b (texto) 50.19 s | no | 3.85 GB |
| `auto__pasaporte_sano_escaneado_dificil` | dificil | escaneado | 2/7 | 3 | 2 | 75.7 s | gemma4:e2b (texto) 27.86 s; gemma4:e2b (texto) 46.41 s | no | - GB |
| `auto__pasaporte_sano_foto_dificil` | dificil | foto | 2/7 | 3 | 2 | 58.3 s | gemma4:e2b (texto) 11.49 s; gemma4:e2b (texto) 45.97 s | no | - GB |
| `auto__comprobante_domicilio_sano_escaneado_extremo` | extremo | escaneado | 1/4 | 1 | 2 | 42.3 s | gemma4:e2b (texto) 11.26 s; gemma4:e2b (texto) 29.72 s | no | 4.08 GB |
| `auto__comprobante_domicilio_sano_foto_extremo` | extremo | foto | 1/4 | 0 | 3 | 44.8 s | gemma4:e2b (texto) 9.55 s; gemma4:e2b (texto) 34.47 s | no | 4.04 GB |
| `auto__credencial_elector_sano_escaneado_extremo` | extremo | escaneado | 2/6 | 1 | 3 | 57.8 s | gemma4:e2b (texto) 10.58 s; gemma4:e2b (texto) 46.4 s | no | 4.11 GB |
| `auto__credencial_elector_sano_foto_extremo` | extremo | foto | 5/6 | 0 | 1 | 238.5 s | qwen2.5vl:3b (vision) 102.17 s; qwen2.5vl:3b (vision) 135.85 s | no | 0.99 GB |
| `auto__pasaporte_sano_escaneado_extremo` | extremo | escaneado | 0/7 | 7 | 0 | 51.1 s | gemma4:e2b (texto) 9.28 s; gemma4:e2b (texto) 40.73 s | no | - GB |
| `auto__pasaporte_sano_foto_extremo` | extremo | foto | 0/7 | 6 | 1 | 59.7 s | gemma4:e2b (texto) 10.72 s; gemma4:e2b (texto) 48.18 s | no | - GB |
| `auto__comprobante_domicilio_domicilio_distinto_digital` | normal | digital | 4/4 | 0 | 0 | 78.0 s | gemma4:e2b (texto) 39.93 s; gemma4:e2b (texto) 38.01 s | no | 4.41 GB |
| `auto__comprobante_domicilio_domicilio_distinto_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 50.9 s | gemma4:e2b (texto) 10.2 s; gemma4:e2b (texto) 38.45 s | no | 4.32 GB |
| `auto__comprobante_domicilio_domicilio_distinto_foto` | normal | foto | 4/4 | 0 | 0 | 48.1 s | gemma4:e2b (texto) 10.53 s; gemma4:e2b (texto) 36.61 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_digital` | normal | digital | 4/4 | 0 | 0 | 47.1 s | gemma4:e2b (texto) 10.36 s; gemma4:e2b (texto) 36.6 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 48.5 s | gemma4:e2b (texto) 10.13 s; gemma4:e2b (texto) 36.25 s | no | 4.33 GB |
| `auto__comprobante_domicilio_sano_foto` | normal | foto | 4/4 | 0 | 0 | 49.8 s | gemma4:e2b (texto) 11.53 s; gemma4:e2b (texto) 37.32 s | no | 4.26 GB |
| `auto__comprobante_domicilio_vencido_digital` | normal | digital | 4/4 | 0 | 0 | 47.8 s | gemma4:e2b (texto) 11.07 s; gemma4:e2b (texto) 36.61 s | no | 4.31 GB |
| `auto__comprobante_domicilio_vencido_escaneado` | normal | escaneado | 4/4 | 0 | 0 | 48.0 s | gemma4:e2b (texto) 11.44 s; gemma4:e2b (texto) 34.28 s | no | 4.22 GB |
| `auto__comprobante_domicilio_vencido_foto` | normal | foto | 4/4 | 0 | 0 | 47.5 s | gemma4:e2b (texto) 10.02 s; gemma4:e2b (texto) 36.56 s | no | 4.19 GB |
| `auto__credencial_elector_domicilio_distinto_digital` | normal | digital | 6/6 | 0 | 0 | 63.2 s | gemma4:e2b (texto) 12.91 s; gemma4:e2b (texto) 50.24 s | no | 4.02 GB |
| `auto__credencial_elector_domicilio_distinto_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 61.6 s | gemma4:e2b (texto) 12.28 s; gemma4:e2b (texto) 47.77 s | no | 4.08 GB |
| `auto__credencial_elector_domicilio_distinto_foto` | normal | foto | 6/6 | 0 | 0 | 60.5 s | gemma4:e2b (texto) 11.12 s; gemma4:e2b (texto) 48.64 s | no | 4.26 GB |
| `auto__credencial_elector_sano_digital` | normal | digital | 6/6 | 0 | 0 | 52.5 s | gemma4:e2b (texto) 9.64 s; gemma4:e2b (texto) 42.8 s | no | 4.26 GB |
| `auto__credencial_elector_sano_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 60.8 s | gemma4:e2b (texto) 11.43 s; gemma4:e2b (texto) 48.11 s | no | 4.2 GB |
| `auto__credencial_elector_sano_foto` | normal | foto | 6/6 | 0 | 0 | 65.0 s | gemma4:e2b (texto) 14.32 s; gemma4:e2b (texto) 50.07 s | no | 3.96 GB |
| `auto__credencial_elector_vencido_digital` | normal | digital | 6/6 | 0 | 0 | 61.5 s | gemma4:e2b (texto) 12.9 s; gemma4:e2b (texto) 48.55 s | no | 4.01 GB |
| `auto__credencial_elector_vencido_escaneado` | normal | escaneado | 6/6 | 0 | 0 | 62.8 s | gemma4:e2b (texto) 10.67 s; gemma4:e2b (texto) 50.8 s | no | 3.9 GB |
| `auto__credencial_elector_vencido_foto` | normal | foto | 6/6 | 0 | 0 | 56.2 s | gemma4:e2b (texto) 9.34 s; gemma4:e2b (texto) 45.51 s | no | 3.65 GB |
| `auto__pasaporte_domicilio_distinto_digital` | normal | digital | 7/7 | 0 | 0 | 66.3 s | gemma4:e2b (texto) 12.34 s; gemma4:e2b (texto) 53.85 s | no | 3.67 GB |
| `auto__pasaporte_domicilio_distinto_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 72.4 s | gemma4:e2b (texto) 13.33 s; gemma4:e2b (texto) 57.18 s | no | 3.57 GB |
| `auto__pasaporte_domicilio_distinto_foto` | normal | foto | 7/7 | 0 | 0 | 66.5 s | gemma4:e2b (texto) 12.61 s; gemma4:e2b (texto) 52.95 s | no | 3.23 GB |
| `auto__pasaporte_sano_digital` | normal | digital | 7/7 | 0 | 0 | 56.6 s | gemma4:e2b (texto) 9.59 s; gemma4:e2b (texto) 46.87 s | no | 3.49 GB |
| `auto__pasaporte_sano_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 70.5 s | gemma4:e2b (texto) 13.47 s; gemma4:e2b (texto) 55.29 s | no | 3.36 GB |
| `auto__pasaporte_sano_foto` | normal | foto | 7/7 | 0 | 0 | 57.0 s | gemma4:e2b (texto) 8.78 s; gemma4:e2b (texto) 47.36 s | no | 3.47 GB |
| `auto__pasaporte_vencido_digital` | normal | digital | 7/7 | 0 | 0 | 66.0 s | gemma4:e2b (texto) 13.72 s; gemma4:e2b (texto) 52.12 s | no | 3.52 GB |
| `auto__pasaporte_vencido_escaneado` | normal | escaneado | 7/7 | 0 | 0 | 71.3 s | gemma4:e2b (texto) 12.96 s; gemma4:e2b (texto) 56.61 s | no | 3.53 GB |
| `auto__pasaporte_vencido_foto` | normal | foto | 7/7 | 0 | 0 | 69.0 s | gemma4:e2b (texto) 11.71 s; gemma4:e2b (texto) 56.31 s | no | 3.74 GB |
| `cls__comprobante_domicilio_sano_escaneado__como_pasaporte` | normal | escaneado | - | - | - | 80.5 s | gemma4:e2b (texto) 30.1 s; gemma4:e2b (texto) 48.07 s | no | 4.39 GB |
| `cls__credencial_elector_sano_digital__como_pasaporte` | normal | digital | - | - | - | 55.3 s | gemma4:e2b (texto) 9.97 s; gemma4:e2b (texto) 45.25 s | no | 3.74 GB |
| `cls__pasaporte_sano_foto__como_credencial_elector` | normal | foto | - | - | - | 51.7 s | gemma4:e2b (texto) 8.76 s; gemma4:e2b (texto) 42.0 s | no | 3.7 GB |

## RAM por bloque

| Bloque | RAM libre minima | Abortado por RAM |
|---|---|---|
| 1 | 4.39 GB | no |
| 3 | 0.99 GB | si |
