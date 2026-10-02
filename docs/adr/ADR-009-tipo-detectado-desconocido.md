# ADR-009: Valor reservado "desconocido" en tipo_documental_detectado

Fecha: 2026-10-01. Estado: PROPUESTO.
Propone: PERSONA_2 (a raiz de la revision de PERSONA_3 en el PR #11). Afecta a: Contrato 1
(`backend/app/schemas/resultado.py`, comentario de `tipo_documental_detectado`) y Contrato 2
(`docs/contratos/endpoints.md`, "Reglas"). Este ADR no cambia ninguno de los dos contratos: los
comentarios se aplican en un PR de contratos aparte cuando se acepte (ver "Aplicacion"). No cambia
ningun tipo ni ninguna forma de respuesta.

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| 1 | Documentar `"desconocido"` como valor reservado de `tipo_documental_detectado` | PERSONA_2 (PR de contratos) | Pendiente |
| 2 | Ninguna ficha puede llamarse `desconocido` (el cargador lo rechaza) | PERSONA_2 (`configuracion/cargador.py`) | Pendiente |
| 3 | Los consumidores no lo tratan como nombre de ficha; en el expediente no cubre ningun tipo requerido hasta que el revisor confirme el tipo y emite `EXP-002` | PERSONA_1 (expediente: solo el mensaje de `EXP-002`; UI) | Pendiente |

## Contexto
- El motor (`motor_ia`, etapa 1) devuelve `tipo_documental_detectado = "desconocido"` cuando clasifica
  el documento pero no encaja en ninguna ficha. Tambien cuando el modelo devuelve un tipo que no esta
  en la lista (`DESCONOCIDO` en `motor_ia/proveedores/base.py`).
- Con tipo declarado, eso dispara `CLS-001` (critica). Si el texto del OCR da `desconocido`, el motor
  reclasifica con vision y decide `CLS-001` con esa clasificacion (`SPEC_CONFIGURACION.md`, seccion 3).
- El Contrato 1 dice `tipo_documental_detectado: str | None` y no menciona el valor. `endpoints.md`
  tampoco. Hoy hay tres significados distintos y solo dos estan documentados:

  | Valor | Significado |
  |---|---|
  | nombre de una ficha | Tipo detectado |
  | `null` | No se clasifico: el revisor confirmo el tipo (`tipo_confirmado`, ADR-006 2.5), el documento aun no se ha analizado o fallo antes de clasificar |
  | `"desconocido"` | Se clasifico, pero no es ninguno de los tipos configurados (**no documentado**) |

- Riesgos si no se documenta:
  - **Tipo efectivo del expediente**: `_tipo_efectivo` usa `confirmado > detectado > declarado`. Con
    `"desconocido"`, el documento no cubre ningun tipo requerido y salta `EXP-001`. Es un
    comportamiento razonable, pero implicito: nadie lo ha decidido ni esta escrito.
  - **Busqueda de ficha**: cualquier codigo que haga `obtener(detectado)` falla, porque no existe
    esa ficha.
  - **UI**: `DetalleDocumento.tsx` muestra el texto tal cual (`ficha(tipo)?.nombre_visible ?? tipo`)
    y no encuentra el umbral de confianza.
  - **Fichas**: si alguien crea una ficha `desconocido`, el valor se vuelve ambiguo.

## Decision propuesta
1. **`"desconocido"` es un valor reservado** de `tipo_documental_detectado`: "clasificado, pero no
   corresponde a ninguna ficha configurada". Se distingue de `null` (no se clasifico).
   - Se documenta con un comentario en `resultado.py`, sin cambiar el tipo `str | None`.
   - En `endpoints.md`, "Reglas", se anade una linea con los tres valores y como tratarlos.
2. **Ninguna ficha puede llamarse `desconocido`**. `configuracion/cargador.py` lo rechaza con un
   error de configuracion (validacion estricta, como las demas claves). Como consecuencia,
   `confirmar-clasificacion` con `{tipo_documental: "desconocido"}` da el mismo error que con
   cualquier tipo inexistente.
3. **Los consumidores no lo tratan como nombre de ficha**:
   - **Tipo efectivo** (expediente): un documento `desconocido` **no cubre ningun tipo requerido**
     hasta que el revisor confirme el tipo (`confirmar-clasificacion`). Salta `EXP-001` ademas de
     `CLS-001`. Es lo que ya hace `_tipo_efectivo`: se documenta, sin cambiar el codigo. Motivo: un
     documento que el motor no reconoce puede no ser el que se declaro.
   - **`EXP-002`** (expediente, informativa): `desconocido` tampoco esta en `tipos_requeridos` ni en
     `tipos_opcionales` del proceso, asi que `recalcular_exp002` emite `EXP-002` en el documento, con
     `campo = "desconocido"`. **Se mantiene a proposito**: es la unica senal para el revisor cuando no
     hay tipo declarado ni confirmado. Desaparece al confirmar un tipo previsto.
   - **Tipo de extraccion** (ADR-006 2.5): no cambia, porque el declarado ya va antes que el detectado.
   - **Fichas**: nunca se busca la ficha `desconocido`. Hoy `validacion.comparar` ya lo tolera,
     porque una ficha ausente no tiene campos.
   - **UI**: muestra "Tipo no reconocido" y no busca la ficha.
4. **No se anaden codigos de alerta**: se reutiliza `EXP-002`, y no hace falta el `CLS-003` que la
   spec dejaba abierto (`SPEC_CONFIGURACION.md`, seccion 10). Alertas de un documento `desconocido`:

   | Caso | Alertas |
   |---|---|
   | Con tipo declarado | `CLS-001` (critica, motor) + `EXP-001` (bloqueante, expediente) si el declarado era un tipo requerido que ningun otro documento cubre + `EXP-002` (informativa, en el documento) |
   | Sin tipo declarado ni confirmado | `EXP-002` (informativa). El motor no extrae: `completado` con datos vacios |
   | Con tipo confirmado | Ninguna de estas: no se clasifica (`tipo_documental_detectado = null`) |

## Alternativas

| Alternativa | Consecuencias |
|---|---|
| A. Dejarlo como esta | Sin trabajo. El valor sigue sin documentar y los tres riesgos del contexto siguen abiertos |
| A2. Documentarlo, pero que en el expediente cuente como el declarado | El documento cubriria su requerido sin que nadie confirme el tipo: solo avisaria `CLS-001`. Exige cambiar `_tipo_efectivo` |
| B. Devolver `null` en lugar de `"desconocido"` | No hay valor especial. Pero se pierde la diferencia entre "no se clasifico" y "no se reconoce el tipo", que el revisor necesita para decidir si confirma el tipo o rechaza el documento |
| C. Tipo cerrado (`Literal` o `Enum` con las fichas + `desconocido`) | Lo comprueba Pydantic, pero las fichas son configurables (`config/tipos/*.yaml`): el contrato dependeria de la configuracion. Cambia el tipo de un contrato congelado |
| **D. La propuesta: valor reservado documentado** | Sin cambio de forma ni de tipo. Solo comentarios en los contratos, una validacion en el cargador y una regla para los consumidores |

## A quien afecta

| Persona | Que cambia |
|---|---|
| PERSONA_1 (plataforma) | Sin cambios de logica: `_tipo_efectivo` ya hace que `desconocido` no cubra ningun requerido, `recalcular_exp002` ya emite `EXP-002` y la ingesta valida el tipo declarado y el confirmado contra las fichas. En la etapa 2, junto con H4, el mensaje de `EXP-002` pasa a "Tipo de documento no reconocido" para `desconocido` (hoy: "Tipo de documento no previsto en el proceso: desconocido"). Revisar que ningun codigo nuevo busque la ficha del detectado sin comprobarlo |
| PERSONA_2 (motor IA) | Comentario en `resultado.py` y linea en `endpoints.md` (PR de contratos). El cargador rechaza una ficha llamada `desconocido`, con su test. El motor no cambia |
| PERSONA_1 (interfaz, desde el traspaso del PR #13) | `DetalleDocumento.tsx`: muestra "Tipo no reconocido" para `"desconocido"` y no busca su ficha. En los mocks, un documento con `tipo_documental_detectado: "desconocido"` |

## Aplicacion
- **Cuando se acepte**: un PR de contratos con el comentario de `resultado.py` y la linea de
  `endpoints.md`, antes de la etapa 2.
- **Etapa 2**: el cambio del cargador (PERSONA_2), y el de la UI y el mensaje de `EXP-002` (PERSONA_1,
  junto con H4), cada uno en su rama.

## Consecuencias
- Los tres valores de `tipo_documental_detectado` quedan documentados, y cada consumidor sabe que
  hacer con cada uno.
- Un documento no reconocido no cubre ningun requerido: el revisor ve `CLS-001`, `EXP-001` (si era
  requerido) y `EXP-002`, y confirma el tipo (`EXP-001` y `EXP-002` se recalculan) o rechaza el
  documento. Sin tipo declarado, la senal es `EXP-002`.
- Si se rechaza: se documenta en `SPEC_CONFIGURACION.md` que `"desconocido"` sigue sin recogerse en
  el contrato, y cada consumidor lo trata por su cuenta.
