# Calibracion de la confianza calculada (ADR-007)

Generado por `docs/motor_ia/pruebas_ollama/calibrar_confianza.py`, sin llamar al modelo. Pesos:
0,6 x aparece + 0,4 x formato; tope 0,5 si fallan los digitos de la MRZ. Umbrales sin cambiar.

## A. Valores correctos en el texto de cada documento

Si la extraccion fuera perfecta: campos con confianza >= `confianza_minima_campo` (si no, VAL-002 falso) y
clasificaciones >= `confianza_minima_clasificacion` (si no, CLS-002 falso).

| Nivel | Documentos | Campos >= minimo | Clasificacion >= minimo |
|---|---|---|---|
| normal | 27 | 152/153 (99 %) | 27/27 (100 %) |
| dificil | 6 | 30/34 (88 %) | 2/6 (33 %) |
| extremo | 6 | 13/34 (38 %) | 0/6 (0 %) |
| especimen | 5 | 23/27 (85 %) | 4/5 (80 %) |

Por modalidad (nivel normal):

| Modalidad | Campos >= minimo | Clasificacion >= minimo |
|---|---|---|
| pdf_digital | 51/51 (100 %) | 9/9 (100 %) |
| pdf_escaneado | 50/51 (98 %) | 9/9 (100 %) |
| imagen | 51/51 (100 %) | 9/9 (100 %) |

Campos correctos por debajo del minimo (nivel, tipo, campo: documentos):

- dificil / credencial_elector / `vigencia`: 1
- dificil / pasaporte / `fecha_nacimiento`: 1
- dificil / pasaporte / `numero_pasaporte`: 1
- dificil / pasaporte / `sexo`: 1
- especimen / comprobante_domicilio / `domicilio`: 1
- especimen / comprobante_domicilio / `fecha_emision`: 1
- especimen / comprobante_domicilio / `nombre_titular`: 1
- especimen / comprobante_domicilio / `proveedor`: 1
- extremo / comprobante_domicilio / `domicilio`: 2
- extremo / comprobante_domicilio / `nombre_titular`: 1
- extremo / credencial_elector / `clave_elector`: 2
- extremo / credencial_elector / `curp`: 2
- extremo / credencial_elector / `domicilio`: 1
- extremo / credencial_elector / `fecha_nacimiento`: 1
- extremo / credencial_elector / `nombre_completo`: 1
- extremo / credencial_elector / `vigencia`: 1
- extremo / pasaporte / `fecha_expedicion`: 2
- extremo / pasaporte / `fecha_nacimiento`: 1
- extremo / pasaporte / `fecha_vencimiento`: 1
- extremo / pasaporte / `nacionalidad`: 1
- extremo / pasaporte / `nombre_completo`: 1
- extremo / pasaporte / `numero_pasaporte`: 2
- extremo / pasaporte / `sexo`: 2
- normal / pasaporte / `sexo`: 1

Clasificacion por documento (confianza del tipo correcto):

| Documento | Nivel | Caracteres de texto | Clasificacion | Minimo |
|---|---|---|---|---|
| `comprobante_domicilio_sano_escaneado_dificil.pdf` | dificil | 254 | 0.800 | 0.80 |
| `comprobante_domicilio_sano_escaneado_extremo.pdf` | extremo | 121 | 0.600 | 0.80 |
| `comprobante_domicilio_sano_foto_dificil.jpg` | dificil | 232 | 0.800 | 0.80 |
| `comprobante_domicilio_sano_foto_extremo.jpg` | extremo | 158 | 0.000 | 0.80 |
| `credencial_elector_sano_escaneado_dificil.pdf` | dificil | 170 | 0.143 | 0.85 |
| `credencial_elector_sano_escaneado_extremo.pdf` | extremo | 144 | 0.000 | 0.85 |
| `credencial_elector_sano_foto_dificil.jpg` | dificil | 133 | 0.286 | 0.85 |
| `credencial_elector_sano_foto_extremo.jpg` | extremo | 17 | 0.000 | 0.85 |
| `pasaporte_sano_escaneado_dificil.pdf` | dificil | 162 | 0.429 | 0.85 |
| `pasaporte_sano_escaneado_extremo.pdf` | extremo | 92 | 0.143 | 0.85 |
| `pasaporte_sano_foto_dificil.jpg` | dificil | 161 | 0.429 | 0.85 |
| `pasaporte_sano_foto_extremo.jpg` | extremo | 133 | 0.143 | 0.85 |
| `comprobante_domicilio_sano_especimen_buena.jpg` | especimen | 314 | 1.000 | 0.80 |
| `comprobante_domicilio_sano_especimen_dificil.jpg` | especimen | 14 | 0.000 | 0.80 |
| `credencial_elector_sano_especimen_buena.jpg` | especimen | 220 | 1.000 | 0.85 |
| `credencial_elector_sano_especimen_dificil.jpg` | especimen | 221 | 1.000 | 0.85 |
| `pasaporte_sano_especimen_buena.jpg` | especimen | 279 | 1.000 | 0.85 |

## B. Valores extraidos en la evaluacion

Campos con valor (los vacios llevan VAL-001/VAL-004). Objetivo: correctos >= minimo e incorrectos < minimo.

| Nivel | Ruta | Correctos >= minimo | Incorrectos < minimo (detectados) | Confianza del modelo en los incorrectos |
|---|---|---|---|---|
| normal | auto | 152/153 (99 %) | - | - |
| dificil | auto | 28/31 (90 %) | 0/2 (0 %) | 0.9, 1.0 |
| dificil | vision | 29/33 (88 %) | 0/1 (0 %) | 0.9 |
| extremo | auto | 11/28 (39 %) | 2/6 (33 %) | 0.9 |
| extremo | vision | 12/31 (39 %) | 2/3 (67 %) | 0.9 |

Incorrectos que pasan el minimo (errores silenciosos que la confianza no ve):

- `auto__comprobante_domicilio_sano_escaneado_dificil` / `domicilio`: 1.00
- `auto__comprobante_domicilio_sano_escaneado_extremo` / `nombre_titular`: 1.00
- `auto__comprobante_domicilio_sano_escaneado_extremo` / `domicilio`: 1.00
- `auto__comprobante_domicilio_sano_escaneado_extremo` / `proveedor`: 1.00
- `auto__pasaporte_sano_foto_dificil` / `numero_pasaporte`: 1.00
- `auto__pasaporte_sano_foto_extremo` / `nombre_completo`: 1.00
- `vision__pasaporte_sano_foto_dificil` / `numero_pasaporte`: 1.00
- `vision__pasaporte_sano_foto_extremo` / `nombre_completo`: 1.00

Clasificacion del tipo detectado (CLS-002 si < minimo):

| Nivel | Ruta | Casos | Con CLS-002 |
|---|---|---|---|
| normal | auto | 27 | 0 |
| dificil | auto | 6 | 4 |
| dificil | vision | 6 | 4 |
| extremo | auto | 6 | 6 |
| extremo | vision | 6 | 6 |

Casos con el tipo declarado equivocado (CLS-001): 3; el tipo detectado tiene confianza 1.00, 1.00, 1.00.
