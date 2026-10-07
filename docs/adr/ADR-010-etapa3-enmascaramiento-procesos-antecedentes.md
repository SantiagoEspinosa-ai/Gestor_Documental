# ADR-010: Etapa 3 - enmascaramiento con "mostrar" auditado, procesos en solo lectura y forma de /antecedentes

Fecha: 2026-10-02. Estado: ACEPTADO (2026-10-05, PERSONA_1 y PERSONA_2 en la revision del PR #21).
Propone: PERSONA_1 (tarea H7 del traspaso, PR #13). Revisa: PERSONA_2.
Cierra los huecos 3, 4 y 8 del ADR-006 (edicion de procesos, enmascaramiento y `/antecedentes`,
aplazados a la etapa 3) y aplica los recortes aceptados R3, R7 y
R8 (`docs/PLAN_PROYECTO.md`, seccion 8). Afecta al Contrato 2 (`docs/contratos/endpoints.md`) y a las
fichas (`config/tipos/*.yaml`). No cambia el Contrato 1 (`resultado.py`) ni la interfaz del motor.

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| A1 | Campos sensibles: solo CURP, numero de pasaporte y clave de elector (R8), con `sensible: true` en la ficha | PERSONA_2 (YAML y cargador, H15) | Aceptada |
| A2 | Mascara `****` + 4 ultimos caracteres | PERSONA_1 (API) | Aceptada |
| A3 | Enmascarado para todos los roles por defecto; revisor y admin pueden "mostrar"; integrador nunca | PERSONA_1 (API y UI, H17) | Aceptada |
| A4 | `POST /documentos/{id}/revelar` con auditoria `dato_revelado` (nombre del campo, nunca el valor) | PERSONA_1 | Aceptada |
| A5 | Tambien se enmascaran evidencias, comparaciones, "antes" de las correcciones, webhooks, `resumen.md` y logs | PERSONA_1 (API, resumen, webhooks); PERSONA_2 (logs del motor) | Aceptada |
| A6 | `sensible` sale en `CampoFicha` de `GET /tipos-documentales` | PERSONA_2 (cargador) y PERSONA_1 (router y UI) | Aceptada |
| B | Procesos: solo lectura (R3); la edicion queda fuera del MVP | Hecho (H8, PR #20) | Aceptada |
| C1 | Antecedentes por `referencia_externa` del folio (R7) | PERSONA_1 (`expediente.servicio`, H16) | Aceptada |
| C2 | Mismo proceso y misma referencia, folios cerrados, dentro de la caducidad, sin el actual, maximo 10 | PERSONA_1 (consulta en `expediente.servicio`, H16) | Aceptada |
| C3 | Sin permiso del proceso o sin referencia: 200 con `permitido: false` y lista vacia | PERSONA_1 (router, H16) | Aceptada |
| C4 | Forma de cada antecedente; `fragmento_resumen` de la memoria | PERSONA_1 (router) y PERSONA_2 (`rag.servicio.fragmento_resumen`, H14) | Aceptada |
| C5 | Roles: revisor y admin | PERSONA_1 | Aceptada |

## Contexto
- ADR-006, hueco 4: el enmascaramiento real tiene que hacerse en el backend; hacerlo solo en la UI no
  protege nada, porque la API seguiria devolviendo el valor. Quedo aplazado a la etapa 3, igual que la
  forma de `/antecedentes` (hueco 8) y la edicion de procesos.
- `endpoints.md` ya preve la accion de auditoria `dato_revelado` y que `detalle` nunca lleva valores
  sensibles sin enmascarar (ADR-006 1.5, ADR-008). `GET /folios/{folio}/antecedentes` existe en el
  contrato con la forma "pendiente de ADR de etapa 3"; el test de H2 lo marca como pendiente.
- Recortes aceptados en el PR #13: R3 (procesos en solo lectura), R7 (antecedentes por
  `referencia_externa`, sin HMAC de la CURP) y R8 (enmascarar solo CURP, numero de pasaporte y clave de
  elector).

## Decision propuesta

### A. Enmascaramiento de datos sensibles
1. **Campos (A1).** Un campo es sensible si su ficha lo marca con `sensible: true`. Con R8, solo
   `curp` (credencial de elector), `clave_elector` (credencial de elector) y `numero_pasaporte`
   (pasaporte). El cargador acepta la clave (por defecto `false`) y la valida como booleano.
2. **Mascara (A2).** `****` seguido de los 4 ultimos caracteres del valor. Un valor de 4 caracteres o
   menos se muestra como `****`. `null` sigue siendo `null` ("no detectado"). Es la misma mascara que
   ya usa la UI en la auditoria.
3. **Quien ve que (A3).**
   - Todas las respuestas de la API llevan los campos sensibles enmascarados, para todos los roles.
   - Revisor y admin pueden pedir el valor real de un campo con "mostrar" (A4).
   - El integrador nunca: su `POST /documentos/{id}/revelar` da `403 SIN_PERMISO`. Recibe el resultado
     enmascarado por la API y por el webhook.
4. **"Mostrar" (A4).** `POST /documentos/{id}/revelar` con cuerpo `{campo}`.
   - Respuesta `200 {campo, valor}` con el valor vigente (el corregido, si lo hay).
   - Roles: revisor y admin. Funciona tambien con el folio cerrado (consultar no cambia el folio).
   - Errores: `422 PETICION_INVALIDA` si el campo no existe en la ficha o no es sensible; `409
     DOCUMENTO_EN_PROCESO` o `409 DOCUMENTO_CON_ERROR` si el documento no tiene resultado.
   - Cada llamada correcta deja una entrada `dato_revelado` con `detalle: {campo}`. Nunca el valor.
   - Es `POST` y no `GET` porque tiene efecto (la auditoria) y no debe quedar en cachés ni repetirse por
     una precarga del navegador. La respuesta lleva `Cache-Control: no-store`.
   - La UI no guarda el valor revelado: lo muestra mientras el revisor no cambie de documento o de
     pantalla.
5. **Donde mas aparece el valor (A5).** Se enmascara en todos estos sitios, no solo en
   `datos_extraidos`:
   - `evidencia_por_campo`: la evidencia de un campo sensible se sustituye por su mascara. Ademas, en la
     evidencia de cualquier campo del mismo documento se enmascara cada aparicion literal del valor
     sensible, tanto del extraido como del corregido: si el OCR leyo mal un caracter y el revisor lo
     corrigio, la evidencia conserva el valor mal leido. En el pasaporte, la linea 2 de la MRZ se tapa
     entera dentro de cualquier evidencia, porque contiene el numero de pasaporte aunque no coincida
     letra a letra con el valor (revision de PERSONA_2 en el PR #21).
   - Comparaciones (`comparaciones` del expediente y mensajes de `CMP-001`): valores enmascarados.
   - Correcciones ("Corregido por revisor (antes: X)"): el valor anterior, enmascarado.
   - Respuesta de `PATCH /documentos/{id}/datos`: enmascarada, aunque el revisor acabe de escribirlo.
   - Webhooks (`documento.completado`, `folio.estado_cambiado`): enmascarados siempre.
   - `resumen.md` y lo que la memoria indexe a partir de el: enmascarados (decision ya tomada para la
     etapa 3).
   - Logs de la plataforma y del motor: nunca valores de `datos_extraidos`; como mucho el nombre del
     campo. PERSONA_2 confirma que los logs del motor ya no llevan valores y que `datos_auditoria` no
     incluye datos del documento; lo cubre con un test en H15.
   - Prompts: no se enmascaran, porque el motor necesita el texto para extraer y Ollama es local. La
     barrera de privacidad del ADR-003 (`PERMITIR_PROVEEDORES_NO_PRIVADOS=false`) impide que salgan a
     un proveedor no privado.
   - La base de datos guarda el valor real: el enmascaramiento es de salida. Cifrarlo en reposo queda
     fuera del MVP.
6. **Como sabe la UI que campos son sensibles (A6).** `CampoFicha` de `GET /tipos-documentales` anade
   `sensible: boolean`. Cambio del Contrato 2: va en el PR de contratos de este ADR, junto con
   `frontend/src/tipos/contrato.ts`, `ingesta/tipos.py` (arma cada campo con claves fijas) y el test de
   H2.

### B. Procesos (R3)
- La configuracion de procesos es de solo lectura en el MVP: `GET /procesos` sin cambios y pantalla
  `/procesos` para el admin (H8, PR #20). La UI muestra del webhook solo el host, nunca la URL
  completa.
- Los procesos se cambian en `config/procesos.yaml` y se cargan al arrancar la API. La edicion por el
  admin (ADR-006: prefijo inmutable; `webhook_url`, `permitir_antecedentes` y
  `caducidad_antecedentes_dias` editables) queda fuera del MVP.

### C. Antecedentes
1. **Identidad (C1).** La persona se identifica por la `referencia_externa` del folio (R7, opcion a)
   del ADR-006). Sin HMAC de la CURP y sin clave nueva. Un folio sin referencia no tiene antecedentes.
2. **Que folios cuentan (C2).** Los del mismo proceso y la misma `referencia_externa`, ya cerrados (con
   decision humana), cuya `fecha_decision` este dentro de `caducidad_antecedentes_dias` del proceso,
   sin el folio actual. Como mucho 10, del mas reciente al mas antiguo. Solo los cerrados porque la
   memoria indexa el `resumen.md`, que se genera al decidir.
3. **Respuesta (C3 y C4).** `GET /folios/{folio}/antecedentes` devuelve siempre `200`:
   ```
   {permitido: bool, motivo: "proceso_sin_antecedentes" | "folio_sin_referencia" | null,
    elementos: [Antecedente]}
   Antecedente: {folio, fecha_solicitud, estado_general, decision_humana, fecha_decision,
                 fragmento_resumen: str | null}
   ```
   - `permitir_antecedentes=false` en el proceso: `permitido: false`, `motivo:
     "proceso_sin_antecedentes"`, lista vacia.
   - Folio sin `referencia_externa`: `permitido: false`, `motivo: "folio_sin_referencia"`, lista vacia.
   - Permitido y sin coincidencias: `permitido: true`, `motivo: null`, lista vacia.
   - `fragmento_resumen`: un trozo del `resumen.md` del antecedente, ya enmascarado; `null` si no hay.
   - Folio que no existe: `404 FOLIO_NO_ENCONTRADO`, como el resto de rutas del folio.
4. **Roles (C5).** Revisor y admin. El contrato hoy dice solo revisor; el admin lo necesita para
   auditar. El integrador: `403 SIN_PERMISO`.
5. **Reparto.** Elegir los folios (C2) es una consulta sobre tablas de la plataforma (`folios`, columnas
   `estado_general`, `decision` y `decision_fecha`; en el Contrato 1, `decision_humana` y
   `fecha_decision`), asi que la hace PERSONA_1 en
   `expediente.servicio` (no en el router, por el ADR-005), y no se duplican esos datos en la memoria.
   PERSONA_2 solo expone `rag.servicio.fragmento_resumen(folio) -> str | None`, ya enmascarado, a
   partir de la memoria de folios (H14); mientras no exista, `fragmento_resumen` va a `null`. El router
   (PERSONA_1) decide `permitido` y `motivo`, llama a `expediente.servicio` y anade el fragmento. La
   pantalla "Antecedentes" en el expediente es de PERSONA_1 (H16). Cambio respecto al borrador, tras la
   revision de PERSONA_2 en el PR #21.

## Alternativas

| Alternativa | Consecuencias |
|---|---|
| A3-b: el integrador recibe los datos completos | Es el sistema que consume el resultado, pero una API o un webhook con CURP en claro amplia la exposicion. Si un cliente lo necesita, se decide con su contrato de tratamiento de datos, fuera del MVP |
| A3-c: solo enmascarar en la UI | Rechazada en el ADR-006: la API seguiria devolviendo el valor |
| A4-b: `GET /documentos/{id}/datos/{campo}` | Un `GET` con efecto (auditoria) puede repetirse por cachés o precargas y dejar entradas falsas |
| A4-c: `POST /documentos/{id}/datos/{campo}/revelar` (la propuesta del ADR-006, hueco 4) | Equivalente; se prefiere el campo en el cuerpo para validarlo como el resto de peticiones (422 `PETICION_INVALIDA`) y no meter nombres de campo en la ruta ni en los logs de acceso |
| A5-b: enmascarar solo `datos_extraidos` | El valor se escaparia por la evidencia (MRZ), las comparaciones, las correcciones y el webhook |
| A6-b: lista `campos_enmascarados` en cada `ResultadoDocumento` | Cambia el Contrato 1, que esta congelado; la ficha ya es la fuente de los campos |
| C3-b: `403` si el proceso no permite antecedentes | La UI tendria que distinguir este 403 del de rol; exige un codigo de error nuevo |
| C2-c: que la memoria (`rag`) elija los folios con `buscar_antecedentes` | Duplicaria en la memoria datos que ya estan en `folios` (estado, decision, fecha) y haria depender la lista de H14; descartada en la revision del PR #21 |
| C2-b: incluir folios abiertos | No tienen `resumen.md` ni decision, y la memoria no los indexa |
| C1-b: HMAC de la CURP | Identifica mejor a la persona, pero exige guardar y comparar un derivado de un dato sensible; descartado en R7 |

## A quien afecta

| Persona | Que cambia |
|---|---|
| PERSONA_1 (plataforma) | Enmascarar en todas las respuestas, comparaciones, correcciones, webhooks y `resumen.md`; `POST /documentos/{id}/revelar` con `dato_revelado`; consulta de antecedentes en `expediente.servicio` y su router; `sensible` en `CampoFicha` (router) |
| PERSONA_1 (interfaz) | Boton "mostrar" en campos sensibles para revisor y admin (H17); pantalla de antecedentes (H16); `contrato.ts` y mocks regenerados con `scripts/generar_datos_mock.py` |
| PERSONA_2 (motor y configuracion) | `sensible: true` en las tres fichas y en el cargador (H15); `rag.servicio.fragmento_resumen(folio)` y memoria de folios sobre el `resumen.md` enmascarado (H14); logs del motor sin valores (ya cumplido; test en H15) |

## Aplicacion
- **Cuando se acepte**: un PR de contratos con la linea de `endpoints.md` para `POST
  /documentos/{id}/revelar`, la forma de `GET /folios/{folio}/antecedentes` (y el rol admin), `sensible`
  en `CampoFicha` y la nota de enmascaramiento en "Reglas"; la accion de auditoria `dato_revelado` ya
  esta prevista en `endpoints.md` (ADR-006 1.5); en el codigo hay que anadirla a
  `ACCIONES_AUDITORIA` (`core/modelos.py`), que `core/auditoria.registrar` valida. Sin migracion: la
  columna no tiene CHECK en BD.
- **Orden**: primero el PR de reglas de coherencia de PERSONA_2 (toca el cargador, los YAML,
  `contrato.ts` e `ingesta/tipos.py`); despues H15 (`sensible: true`), no en paralelo, porque comparten
  ficheros; despues el enmascaramiento de la API y H17 (PERSONA_1).
- **Antecedentes (H16)**: la consulta y el router no esperan a la memoria; `fragmento_resumen` va a
  `null` hasta que `rag.servicio.fragmento_resumen` este en `main`.
- El xfail de `antecedentes` en `tests/test_openapi_contrato.py` se quita cuando el router exista.

## Consecuencias
- Ningun valor sensible sale de la API en claro salvo por "mostrar", y cada uso queda auditado con el
  campo y el usuario.
- El integrador y los webhooks no exponen CURP, numero de pasaporte ni clave de elector.
- La pantalla distingue "no permitido", "sin referencia" y "sin antecedentes" sin codigos de error
  nuevos.
- Si se rechaza: el enmascaramiento queda solo en la UI (sin proteccion real) y `/antecedentes` sigue
  sin forma, lo que bloquea H16 y H17.

## Adenda post-MVP (PROPUESTA, pendiente de aceptar en el PR)
No cambia nada de lo aceptado arriba; solo anade puntos.

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| A4b | Accion de auditoria `original_visto` en `GET /documentos/{id}/original` | PERSONA_1 | Propuesta |
| A4c | `motivo` opcional en `POST /documentos/{id}/revelar`, guardado tapado en `dato_revelado` | PERSONA_1 | Propuesta |

- **A4b, que**: cada `GET /documentos/{id}/original` correcto deja `original_visto` con el usuario, el
  folio y el `documento_id` en sus columnas y `detalle` vacio: nada del contenido del documento. Con `403`
  o `404` no deja registro.
- **A4b, por que**: el original muestra los campos sensibles sin mascara. Sin este registro, la
  trazabilidad de A4 ("cada uso queda auditado con el campo y el usuario") queda incompleta: se puede ver
  la CURP abriendo el original sin dejar rastro. Lo detecto la revision de seguridad.
- **A4b, que no cambia**: sin migracion (la columna `accion` no tiene CHECK en BD) y la lista de acciones
  sigue cerrada: se anade a `ACCIONES_AUDITORIA`, `endpoints.md` y `contrato.ts`, que
  `test_contrato_frontend` mantiene iguales.
- **A4c, que**: `POST /documentos/{id}/revelar` acepta `motivo` opcional (texto de 3 a 200 caracteres; fuera
  de rango, `422 PETICION_INVALIDA`). Si viene, se guarda en `detalle.motivo` de `dato_revelado`. En la UI,
  un campo corto opcional junto a "Mostrar" que nunca bloquea.
- **A4c, como se protege**: es texto libre, asi que el motivo se guarda tapado con la misma barrera que los
  logs (A5): `enmascaramiento.enmascarar_texto` tapa los valores sensibles del documento y, con
  `logs.tapar`, cualquier CURP, clave de elector, pasaporte o MRZ, sea o no del documento.
- **A4c, que no cambia**: compatible hacia atras (sin `motivo`, todo igual que en A4); sin migracion; el
  motivo no es obligatorio. Pedirlo obligatorio seria otra decision.
