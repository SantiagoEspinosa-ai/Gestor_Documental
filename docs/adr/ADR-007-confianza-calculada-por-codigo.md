# ADR-007: Confianza calculada por el codigo para VAL-002 y CLS-002

Fecha: 2026-09-30. Estado: PROPUESTO (revisar entre los tres antes del dia 6; no aplicar hasta
aceptarlo).

## Contexto
- `docs/contratos/codigos_alertas.md` (aceptado en ADR-006) define dos alertas basadas en confianza:
  - `VAL-002` (preventiva): la confianza de un campo es menor que `confianza_minima_campo` de la
    ficha (0,80 en pasaporte y credencial; 0,75 en comprobante de domicilio).
  - `CLS-002` (preventiva): `confianza_clasificacion` es menor que `confianza_minima_clasificacion`
    (0,85 en pasaporte y credencial; 0,80 en comprobante de domicilio).
- La regla de recomendacion del mismo catalogo recomienda `aprobar` si no hay alertas criticas ni
  bloqueantes "y las confianzas estan sobre el minimo".
- El Contrato 1 no dice quien calcula `nivel_confianza_por_campo` ni `confianza_clasificacion`. Hoy
  se da por hecho que las rellena el modelo con lo que devuelve.
- Las pruebas de `docs/motor_ia/pruebas_ollama.md` (2026-09-30) muestran que la confianza que
  devuelve el modelo no informa de nada:
  - `qwen2.5vl:3b` (modelo de vision elegido) devuelve siempre 0,9 o 1 en todos los campos, tambien
    en fechas mal convertidas (dia y mes intercambiados).
  - `gemma4:e2b`, con la vision rota, se invento los 7 campos del pasaporte con confianzas de 0,85 a
    0,98 (0,95 en el nombre).
  - El borrador de prompt v2 pide expresamente bajar la confianza si hay dudas. No cambio nada: 0,9
    en todos los campos.
- Consecuencia: con los umbrales actuales, `VAL-002` y `CLS-002` no saltarian nunca, y un documento
  con datos inventados cumpliria la condicion de confianza para recomendar `aprobar`.

## Decision propuesta
1. `nivel_confianza_por_campo` y `confianza_clasificacion` los calcula el codigo del motor
   (`motor_ia`) con comprobaciones deterministas, reproducibles y con tests. Por campo:

   | Comprobacion | Como |
   |---|---|
   | El valor aparece en el documento | Se busca en el texto del PDF (`pdf_digital`) o del OCR, normalizando mayusculas, acentos y espacios; las fechas, tras `normalizar_fecha` |
   | Cumple el patron | `patron` de la ficha, si lo tiene |
   | El tipo es valido | `fecha`: fecha existente; `anio`: cuatro cifras en un rango razonable |
   | El campo no aparece | Valor `null` -> confianza 0 |

   Para la clasificacion: proporcion de las `caracteristicas_esperadas` del tipo **detectado** que
   se encuentran en el texto del documento (PDF u OCR). No depende de la extraccion, que se hace con
   la ficha del tipo declarado (ADR-006, 2.5).

   Las `caracteristicas_esperadas` son descripciones en lenguaje natural ("Fotografia del titular",
   "Zona de lectura mecanica (MRZ) de dos lineas al pie") que no aparecen literalmente en el texto.
   Por eso cada ficha declara marcadores verificables en una clave opcional nueva,
   `marcadores_clasificacion`: una lista de expresiones regulares que se buscan en el texto. Ejemplos
   orientativos:

   | Tipo | Caracteristica esperada | Marcador |
   |---|---|---|
   | `pasaporte` | Zona MRZ de dos lineas | linea que empieza por `P<` seguida de `[A-Z<]{3}` |
   | `pasaporte` | Numero de pasaporte | el `patron` de `numero_pasaporte` |
   | `credencial_elector` | Clave de elector y CURP | el `patron` de `curp` |
   | `comprobante_domicilio` | Fecha de emision o periodo | `periodo` o `fecha de emision` |

   Las caracteristicas que no se pueden verificar con texto (p. ej. la fotografia) no llevan
   marcador y no cuentan. `marcadores_clasificacion` es un cambio de las fichas YAML y del cargador
   (`configuracion`, PERSONA_2), no de un contrato congelado. Si una ficha no declara marcadores,
   su confianza de clasificacion es 0 y salta `CLS-002`, para que no pase desapercibido.

   Con pocos marcadores la proporcion es muy gruesa: con tres solo toma los valores 0; 0,33; 0,67
   y 1, y un umbral de 0,85 equivale a "todos". El numero de marcadores por ficha y su calibracion
   se deciden en la etapa 2 con los fixtures de PERSONA_3, **sin cambiar los umbrales**
   (`confianza_minima_clasificacion` de las fichas).

   Las fichas `config/tipos/*.yaml` son ficheros compartidos: anadirles `marcadores_clasificacion`
   va en un PR pequeno y con aviso al equipo (CLAUDE.md, "Ramas y flujo de trabajo", punto 4),
   cuando se acepte este ADR.

   Los pesos exactos de cada comprobacion se fijan en la etapa 2, con tests, y se documentan en
   `docs/motor_ia/SPEC_CONFIGURACION.md`.
2. No cambia el significado de ningun codigo: `VAL-002` y `CLS-002` conservan su condicion, su
   severidad y sus umbrales. Solo cambia de donde sale la confianza que comparan.
3. No cambia la forma del Contrato 1: los campos existen y son `float` entre 0 y 1. Al aceptar este
   ADR se anota en el comentario de esos campos de `resultado.py` que la confianza la calcula el
   codigo (en el PR de contratos).
4. La confianza que devuelve el modelo se guarda solo en la auditoria, en el `detalle` de
   `documento_procesado` (ADR-006, 1.5), junto a `modelo` y `version_prompt`. No se usa en reglas,
   recomendaciones ni en la UI.
5. Se mantiene la regla de ADR-006, 2.4: un campo corregido por el revisor pasa a confianza 1,0.

## Alternativas

| Alternativa | Consecuencias |
|---|---|
| A. Mantenerlo como esta: la confianza la da el modelo | Sin trabajo extra. `VAL-002` y `CLS-002` no saltan nunca. La UI muestra barras de confianza del 90-100 % tambien en datos inventados. La recomendacion `aprobar` se apoya en un dato que no es fiable |
| B. Bajar `VAL-002` y `CLS-002` a severidad `informativa` | Cambia el significado de dos codigos del catalogo. No resuelve el problema: con la confianza del modelo siguen sin saltar, y la recomendacion y la UI siguen usando la confianza del modelo |
| **C. La propuesta: confianza calculada por el codigo** | Las alertas saltan cuando un dato no se puede verificar. Confianza reproducible y testeable, sin depender del modelo. Coste: una funcion en `motor_ia` con tests en la etapa 2 |

## A quien afecta

| Persona | Que cambia |
|---|---|
| PERSONA_1 (plataforma) | La recomendacion por documento y global (`codigos_alertas.md`) compara confianzas calculadas por el codigo; la regla no cambia. La auditoria de `documento_procesado` guarda la confianza del modelo en `detalle` |
| PERSONA_3 (interfaz) | La barra de confianza de la tabla de datos muestra la confianza calculada. La forma de los datos y los mocks no cambian; puede cambiar el texto de ayuda de la barra (p. ej. "confianza verificada") |
| PERSONA_2 (motor IA) | `motor_ia` calcula ambas confianzas y deja la del modelo para la auditoria; `validacion/reglas.py` emite `VAL-002` con la confianza calculada; `configuracion` acepta `marcadores_clasificacion`. Las tres fichas YAML los declaran en un PR pequeno aparte, con aviso (ficheros compartidos) |

Aplicacion: etapa 2, antes de `validacion/reglas.py`. Si se acepta, lo implementa PERSONA_2.

## Consecuencias
- `VAL-002` y `CLS-002` pasan a ser utiles: avisan cuando un dato no se puede verificar.
- En `imagen` y `pdf_escaneado` sin OCR no hay texto con el que comparar: la comprobacion "aparece
  en el documento" no se cumple, esos campos tienen confianza baja y `VAL-002`, y la clasificacion
  `CLS-002`. Es lo esperado (el dato no se ha podido verificar), y esos documentos van a
  `revision_manual`.
  - El contenedor del backend ya incluye Tesseract (`tesseract-ocr`, `spa` y `eng` en
    `backend/Dockerfile`): en Docker, los documentos `imagen` y `pdf_escaneado` si se pueden verificar.
  - Solo ocurre al ejecutar fuera de Docker en una maquina sin Tesseract, como el Windows de
    PERSONA_2 hoy.
- La confianza deja de ser la "seguridad del modelo" y pasa a ser "grado de verificacion del dato".
  Hay que explicarlo en la UI y en la documentacion de la API para integradores.
- Los tests no necesitan el modelo: la confianza se calcula sobre respuestas guardadas y texto fijo.
- Si se rechaza: se mantiene la alternativa A y se documenta en la spec que `VAL-002` y `CLS-002` no
  son fiables con los modelos actuales.
