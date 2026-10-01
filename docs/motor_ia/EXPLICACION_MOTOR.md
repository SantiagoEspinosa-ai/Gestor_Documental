# Como funciona el motor IA (explicacion para el equipo)

Documento en lenguaje sencillo para el equipo y la presentacion. El detalle tecnico de cada decision esta en
[SPEC_CONFIGURACION.md](SPEC_CONFIGURACION.md) y las pruebas en [pruebas_ollama.md](pruebas_ollama.md).
Todos los documentos usados en las pruebas son **ficticios** (fixtures de PERSONA_3).

Palabras que se repiten:

| Palabra | Que significa aqui |
|---|---|
| Modelo | Programa de inteligencia artificial que lee el documento y devuelve los datos. Funciona en nuestra maquina (Ollama), sin enviar nada fuera |
| Modelo de texto | Lee solo texto. Rapido |
| Modelo de vision | "Mira" la imagen del documento. Mas lento, pero lee aunque no haya texto |
| OCR | Programa (Tesseract) que convierte una imagen en texto, como un escaner que "lee" |
| Prompt | Las instrucciones escritas que le damos al modelo. Las guardamos con version (v1, v2, v3...) |
| Ficha | Descripcion de cada tipo de documento: que campos tiene y cuales son obligatorios (`config/tipos/*.yaml`) |
| Campo | Un dato del documento: nombre, numero de pasaporte, fecha de nacimiento... |
| Alerta | Aviso que el motor deja para el revisor (p. ej. `CLS-001`: el tipo no coincide) |
| Fixture | Documento ficticio de prueba. Niveles: normal, dificil (peor calidad) y extremo (muy mala calidad) |

## 1. Como funciona, de principio a fin

1. **Llega el archivo** (PDF o foto) con el tipo que dice el usuario (p. ej. "pasaporte").
2. **Se prepara**: se mira si el PDF tiene texto dentro (PDF digital) o es una imagen (escaneado o foto). Si es
   imagen, el OCR saca el texto que puede. Cada pagina queda con su imagen y su texto.
3. **Se elige el modelo**: si todas las paginas tienen texto suficiente (30 letras o mas), va al modelo de
   texto; si no, al de vision.
4. **Se clasifica**: el modelo dice que tipo de documento es. Si no coincide con el declarado, alerta `CLS-001`.
5. **Se extraen los campos** de la ficha.
6. **Se comprueba si el OCR era malo** (las cuatro senales del apartado 3). Si lo era, se repite con vision.
7. **Se limpian los datos en codigo**: fechas a un formato unico, textos vacios a "sin dato", campos que no son
   de la ficha fuera.
8. **Se devuelve el resultado** (siempre con la misma forma, el "Contrato 1"), con las alertas y el registro de
   cada llamada al modelo: que modelo, cuanto tardo y **por que** se uso vision si se uso.

```
  Archivo (PDF / foto) + tipo declarado
              |
              v
  +-------------------------+
  | Preparar                |  PDF digital -> texto del PDF
  | (orquestador)           |  escaneado / foto -> imagen + OCR
  +-------------------------+
              |
              v
     Todas las paginas con >= 30 letras?
        |                         |
       si                         no  (senal 1)
        |                         |
        v                         v
  Modelo de TEXTO           Modelo de VISION -----------------+
  gemma4:e2b                qwen2.5vl:3b                      |
        |                                                     |
        v                                                     |
  Clasificar: que tipo es?                                    |
        |                                                     |
        +-- "desconocido" (senal 2) --> reclasificar con      |
        |                               vision y extraer con  |
        |                               vision -------------->+
        v                                                     |
  Extraer campos con texto                                    |
        |                                                     |
        +-- mitad o mas de obligatorios vacios (senal 3) --+  |
        +-- algun campo con formato imposible (senal 4) ---+  |
        |                                                  |  |
        |        (salvo si el tipo es otro distinto:       v  |
        |         CLS-001 y no se repite)          Repetir con VISION
        |                                                  |  |
        v                                                  v  v
  +--------------------------------------------------------------+
  | Limpiar en codigo: fechas, vacios -> null, solo campos de la  |
  | ficha. Alertas (CLS-001, SYS-...). Registro de cada llamada.  |
  +--------------------------------------------------------------+
              |
              v
     Resultado (Contrato 1) -> validacion (etapa 2) -> revisor
```

Lo importante: **el texto es la via rapida y la vision es la via segura**. Usamos vision solo cuando hay una senal
de que el texto no basta, porque en esta maquina la vision tarda el doble o mas.

## 2. Por que estos modelos

Maquina de pruebas: maquina virtual con 2 nucleos, 16 GB de RAM (unos 8 GB libres) y **sin tarjeta grafica**
(GPU). Todo lo que se mide aqui va en CPU, que es mucho mas lento.

| Modelo | Para que lo probamos | Aciertos | Tiempo por documento | RAM | Decision y motivo |
|---|---|---|---|---|---|
| `gemma4:e2b` | Texto | **7/7 y 7/7** (pasaporte) | **~37 s** | ~3 GB | **Elegido para texto**: acierta todo y es el mas rapido |
| `gemma4:e2b` | Vision | 0/7: se invento los datos con confianza 0,95 | ~50 s | ~3 GB | Descartado para vision: en Ollama para Windows no ve las imagenes (no lee ni una imagen con la palabra "HOLA"). Fallo conocido, sin arreglar (issue ollama#16532) |
| `gemma4:e4b` | Texto y vision | sin probar | - | ~9,6 GB | Descartado: no cabe en los ~8 GB libres y tiene el mismo fallo de vision en Windows |
| `qwen2.5vl:3b` | Vision | 4/7 con el prompt inicial; **7/7 en 4 de 4** con las mejoras del apartado 3 | ~110-130 s por pagina | ~4,3 GB | **Elegido para vision**: lee bien las imagenes y cabe en la maquina |
| `qwen2.5vl:3b` | Texto | 4/7 | ~39 s | ~4,3 GB | Descartado para texto: `gemma4:e2b` acierta mas en el mismo tiempo |
| `qwen2.5:7b` | Texto | 6/7 y 7/7 | ~65-75 s | 4,7 GB en disco | Descartado: tarda el doble y en una ejecucion se dejo un campo |
| `llama3.2-vision:11b` | Vision (propuesto en el plan inicial) | sin probar | - | mayor que la RAM libre | Descartado: demasiado grande para 2 nucleos sin GPU |

**Conclusion: `gemma4:e2b` para texto y `qwen2.5vl:3b` para vision.**
- `gemma4:e2b` es el que mas acierta con texto y el mas rapido (~37 s), y es pequeno (~3 GB).
- `qwen2.5vl:3b` es el unico de los probados que ve bien las imagenes en Windows y cabe en la RAM.
- Los dos juntos no caben comodos: se carga **un modelo cada vez** (el otro se descarga de memoria).
- Con texto suficiente, la combinacion OCR + `gemma4:e2b` acierta mas y tarda la mitad que la vision, por eso
  es la via por defecto.

## 3. Historial de mejoras

Cada entrada: **problema -> que se cambio -> mejora medida**. Se anade una entrada con cada cambio de regla, de
modelo o resultado de prueba.

| Fecha | Problema | Que se cambio | Mejora medida |
|---|---|---|---|
| 2026-09-30 | `gemma4:e2b` no ve imagenes en Windows y se inventa los datos | Vision con `qwen2.5vl:3b`; `gemma4:e2b` solo para texto | Vision: 0/7 -> 4/7 (prompt inicial) |
| 2026-09-30 | Al pedirle las fechas convertidas, `qwen2.5vl:3b` intercambia dia y mes (`10/05/2024` -> `2024-10-05`) | El prompt pide las fechas **tal cual** aparecen y el codigo las convierte (`normalizar_fecha`, dia/mes/anio) | 5/7 -> **7/7 en 4 de 4**; fechas 3/3 |
| 2026-09-30 | Imagenes grandes: mas lentas y no mejores | Se reducen a **1000 px** de ancho antes de enviarlas | 5/7 -> 6/7 y ~20 % menos de tiempo (800 px no mejora) |
| 2026-09-30 | Una respuesta se quedo mas de 10 minutos repitiendo `<<<<` | Tope de 800 palabras de salida (`num_predict`) | No se ha vuelto a repetir |
| 2026-09-30 | La confianza que da el modelo es siempre 0,9-1, tambien en datos inventados | ADR-007: la confianza la calculara el codigo (apartado 4) | Pendiente de medir (etapa 2) |
| 2026-10-01 | La vision es lenta y fallaba en escaneados y fotos | **OCR + modelo de texto** si hay texto suficiente; vision solo si no | Escaneado y foto: vision 6/7 en ~130 s -> **OCR + texto 7/7 en ~68 s** |
| 2026-10-01 | Fotos con OCR malo dejan campos vacios | **Reintento con vision** si la mitad o mas de los obligatorios salen vacios | Primera version de la regla (medida junto con la siguiente) |
| 2026-10-01 | Documento con el tipo declarado equivocado: el reintento con vision no podia arreglar nada (se extraia con la ficha equivocada) | **No reintentar si salta `CLS-001` con un tipo concreto** distinto del declarado | Ese caso: **255 s -> 80 s**, mismo resultado |
| 2026-10-01 | Textos vacios (`""` o solo espacios) parecian datos presentes | Se convierten a "sin dato" (`null`) | Las alertas de campo ausente (`VAL-001`, `VAL-004`) los ven; cubierto por tests |
| 2026-10-01 | Fixtures dificiles con la ruta normal: muchos vacios y errores; con OCR muy malo el texto daba "desconocido" y `CLS-001` bloqueaba el reintento | **Cuatro senales de OCR pobre** (texto insuficiente, clasificacion desconocida, obligatorios vacios, formato imposible) y **reclasificacion con vision** cuando el texto da "desconocido" | Dificil: **19/34 -> 31/34** correctos (incorrectos 7 -> 2). Extremo: **9/34 -> 28/34** (incorrectos 10 -> 6). Tipo correcto en extremo 2/6 -> 6/6. Vacios 23 -> 1. Normales sin cambios: 153/153, 59 s |
| 2026-10-01 | Con vision, `fecha_expedicion` del pasaporte salia vacia aunque se lee bien | Prompt `extraccion_v3`: lista de campos **sin la palabra "opcional"** (el modelo se saltaba los campos opcionales) | 4 pasaportes dificiles con vision: **21/28 -> 25/28**, vacios 4 -> 0 |
| 2026-10-01 | Dos documentos a la vez cargarian dos modelos y dejarian la maquina sin RAM (en una prueba la RAM libre bajo a 0,99 GB con los dos modelos cargados) | PERSONA_1 (PR #9): la ingesta procesa **de uno en uno** (`MAX_PROCESAMIENTOS_SIMULTANEOS=1`) y Ollama se arranca con `OLLAMA_MAX_LOADED_MODELS=1` | Un solo analisis y un solo modelo en memoria cada vez; sin medida propia del motor (lo cubren los tests de la ingesta) |

Coste de la regla de OCR pobre: los documentos dificiles tardan mas (~63-82 s -> ~150 s), porque ahora usan
vision. Los normales no cambian (ninguno usa vision).

## 4. Las reglas y su por que

| Regla | Que hace | Por que |
|---|---|---|
| Barrera de privacidad (ADR-003) | Un proveedor que no es privado (en la nube) solo se puede usar si se activa `PERMITIR_PROVEEDORES_NO_PRIVADOS=true`, y solo con documentos ficticios. Por defecto esta cerrada | Los documentos reales tienen datos personales: no pueden salir de nuestra maquina |
| Confianza calculada por el codigo (ADR-007) | La "confianza" de cada campo la calculara el codigo comprobando el dato (aparece en el texto, cumple el formato, es una fecha valida); la del modelo solo se guarda para auditoria | El modelo dice 0,9-1 siempre, incluso cuando se inventa los datos. Con su confianza, un documento inventado podria salir como "aprobar" |
| `SYS-003` (preventiva) | Avisa de que el texto era demasiado largo y se ha recortado | Para no pasarnos del limite del modelo sin que nadie lo sepa: los campos de las ultimas paginas pueden faltar |
| `SYS-005` (informativa) | Avisa de que se uso el proveedor de respaldo porque fallo el principal | Que quede claro que modelo hizo el analisis |
| `VAL-003` (informativa) | Avisa de que un campo se tomo de la MRZ (las dos lineas con `<<<` del pasaporte) porque no se leia en la zona visual | El revisor debe saber de donde sale el dato |
| `VAL-004` (informativa, etapa 2) | Avisa de que un campo opcional viene vacio | Un campo opcional vacio no es un error, pero el revisor debe verlo |
| `CLS-001` (critica) | El tipo declarado no coincide con el detectado. Si el texto dice "desconocido", lo decide la vision | Un documento del tipo equivocado no se puede aprobar |
| Un modelo cada vez | Antes de cargar un modelo se descarga el otro | Los dos juntos dejan la maquina sin RAM (bajo a 0,99 GB en una prueba) |
| Registro del motivo | Cada llamada guarda si fue con texto o con vision y por que | Para auditar y explicar cada decision del motor |

## 5. Resultados de las evaluaciones

Se comparan todos los campos con los valores correctos de `fixtures/generados/INDICE.md`. **Correcto** = igual;
**vacio** = sin dato; **incorrecto** = dato equivocado (el peor caso, porque no se nota).

**Bloque 1: documentos normales, ruta normal** (27 documentos + 3 con el tipo equivocado)

| Modalidad | Correctos | Minimo |
|---|---|---|
| PDF digital | 51/51 | 49/51 |
| Escaneado (OCR + texto) | 51/51 | 47/51 |
| Foto (OCR + texto) | 51/51 | 47/51 |
| Tipo detectado / `CLS-001` con el tipo equivocado | 27/27 / 3 de 3 | 26/27 / 3 de 3 |
| Tiempo medio | 59 s | <= 90 s |

**Bloque 3: documentos dificiles y extremos, ruta normal** (12 documentos)

| Nivel | Antes de la regla de OCR pobre | Despues | Criterio |
|---|---|---|---|
| Dificil: correctos | 19/34 | **31/34** | >= 26 |
| Dificil: incorrectos | 7 | **2** | <= 3 |
| Extremo: correctos | 9/34 | **28/34** | referencia |
| Extremo: incorrectos | 10 | **6** | <= 7 |
| Tipo correcto (dificil / extremo) | 6/6 / 2/6 | **6/6 / 6/6** | 6/6 / >= 4/6 |
| Tiempo medio | ~63-82 s | ~150 s | - |

**Bloque 4: los mismos 12 documentos, solo con vision** (referencia)

| | Correctos | Vacios | Incorrectos |
|---|---|---|---|
| Con `extraccion_v2` (12 casos) | 60/68 | 4 | 4 |
| 12 casos: 8 con `extraccion_v2` + los 4 pasaportes repetidos con `extraccion_v3` | 64/68 | 0 | 4 |

Nota: el bloque 4 no se ha repetido entero; el informe avisa de que mezcla v2 (8 casos) y v3 (4 pasaportes).

**Diagnostico de `fecha_expedicion`** (pasaporte con vision, una llamada por variante)

| Variante | Foto dificil | Escaneado dificil |
|---|---|---|
| A: prompt v3 con "opcional" | vacia | vacia |
| B: sin la palabra "opcional" | **leida** | **leida** |
| C: sin el texto del OCR | vacia | leida |
| D: imagen a 1400 px | leida | vacia |

Solo la B funciona en los dos: es la que se aplico.

**Tiempo por documento** (1 pagina, en la maquina de pruebas sin GPU; medido en la evaluacion del 2026-10-01)

| Documento | Media | Maximo medido |
|---|---|---|
| Normal (PDF digital, escaneado o foto) | ~60 s | 73 s |
| Dificil (usa vision en 3 de 6) | ~150 s | 244 s |
| Extremo (usa vision en 5 de 6) | ~156 s | 193 s |

Limites: cada llamada al modelo de texto puede tardar como mucho **120 s**, y cada llamada de vision **60 s + 150 s
por imagen** (210 s con 1 pagina). En el peor caso, un documento de 1 pagina con OCR malo hace tres llamadas
(clasificar con texto, reclasificar con vision y extraer con vision) y puede llegar a **~9 minutos** (540 s) antes
de dar error. Como los documentos se procesan de uno en uno, si hay varios en cola los tiempos se suman. En una
maquina con GPU estos tiempos bajarian mucho, pero hay que medirlos.

## 6. Lo que falta y los riesgos

| Tema | Situacion | Que hacer |
|---|---|---|
| Maquina con GPU | En esta maquina la vision tarda ~110-150 s por documento | Para la demo hace falta una maquina con GPU (8 GB de memoria grafica o mas) o mas RAM y nucleos |
| Errores silenciosos sin senal | Datos mal leidos que parecen correctos (p. ej. `GALLE FICTICIA 123` en vez de `CALLE`). El comprobante extremo escaneado se queda en 1/4 | Reglas de coherencia en la etapa 2 (CURP con fecha de nacimiento, orden de las fechas) y la confianza del OCR |
| Confianza de Tesseract | El OCR sabe cuando duda de una palabra, pero aun no lo usamos | Usarla como quinta senal de OCR pobre, despues de probar con los especimenes |
| Especimenes | Fotos de movil reales de documentos ficticios impresos (PERSONA_3) | Esperar a que lleguen a `main`. Aviso: desde el 2026-12-14 el comprobante dara `REG-antiguedad_maxima` porque sus fechas impresas no cambian |
| Un documento cada vez | Cada documento tarda de 60 a 150 s y carga un modelo de 3-4 GB; dos a la vez cargarian dos modelos y la maquina se queda sin RAM | **Resuelto por PERSONA_1 (PR #9)**: la ingesta procesa los documentos de uno en uno (`MAX_PROCESAMIENTOS_SIMULTANEOS=1`) y Ollama se arranca con `OLLAMA_MAX_LOADED_MODELS=1` |
| Confianza del modelo | Sigue siendo provisional | Calcularla en el codigo en la etapa 2 (ADR-007) |
| No determinismo | El modelo puede responder distinto con el mismo documento | Los tests usan respuestas guardadas; las evaluaciones se repiten |
