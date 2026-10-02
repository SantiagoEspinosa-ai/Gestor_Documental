# ADR-010: Etapa 3 - enmascaramiento con "mostrar" auditado, procesos en solo lectura y forma de /antecedentes

Fecha: 2026-10-02. Estado: PROPUESTO.
Propone: PERSONA_1 (tarea H7 del traspaso, PR #13). Revisa: PERSONA_2.
Cierra los huecos 4 y 8 del ADR-006 (aplazados a la etapa 3) y aplica los recortes aceptados R3, R7 y
R8 (`docs/PLAN_PROYECTO.md`, seccion 8). Afecta al Contrato 2 (`docs/contratos/endpoints.md`) y a las
fichas (`config/tipos/*.yaml`). No cambia el Contrato 1 (`resultado.py`) ni la interfaz del motor.

## Resumen para la reunion

| Punto | Descripcion | Implementa | Decision |
|---|---|---|---|
| A1 | Campos sensibles: solo CURP, numero de pasaporte y clave de elector (R8), con `sensible: true` en la ficha | PERSONA_2 (YAML y cargador, H15) | Pendiente |
| A2 | Mascara `****` + 4 ultimos caracteres | PERSONA_1 (API) | Pendiente |
| A3 | Enmascarado para todos los roles por defecto; revisor y admin pueden "mostrar"; integrador nunca | PERSONA_1 (API y UI, H17) | Pendiente |
| A4 | `POST /documentos/{id}/revelar` con auditoria `dato_revelado` (nombre del campo, nunca el valor) | PERSONA_1 | Pendiente |
| A5 | Tambien se enmascaran evidencias, comparaciones, "antes" de las correcciones, webhooks, `resumen.md` y logs | PERSONA_1 (API, resumen, webhooks); PERSONA_2 (logs del motor) | Pendiente |
| A6 | `sensible` sale en `CampoFicha` de `GET /tipos-documentales` | PERSONA_2 (cargador) y PERSONA_1 (router y UI) | Pendiente |
| B | Procesos: solo lectura (R3); la edicion queda fuera del MVP | Hecho (H8, PR #20) | Pendiente |
| C1 | Antecedentes por `referencia_externa` del folio (R7) | PERSONA_2 (H14) | Pendiente |
| C2 | Mismo proceso y misma referencia, folios cerrados, dentro de la caducidad, sin el actual, maximo 10 | PERSONA_2 (H14) | Pendiente |
| C3 | Sin permiso del proceso o sin referencia: 200 con `permitido: false` y lista vacia | PERSONA_1 (router, H16) | Pendiente |
| C4 | Forma de cada antecedente | PERSONA_1 (router) y PERSONA_2 (busqueda) | Pendiente |
| C5 | Roles: revisor y admin | PERSONA_1 | Pendiente |

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
     evidencia de cualquier campo del mismo documento se enmascara cada aparicion literal de un valor
     sensible (la linea MRZ del pasaporte contiene el numero de pasaporte).
   - Comparaciones (`comparaciones` del expediente y mensajes de `CMP-001`): valores enmascarados.
   - Correcciones ("Corregido por revisor (antes: X)"): el valor anterior, enmascarado.
   - Respuesta de `PATCH /documentos/{id}/datos`: enmascarada, aunque el revisor acabe de escribirlo.
   - Webhooks (`documento.completado`, `folio.estado_cambiado`): enmascarados siempre.
   - `resumen.md` y lo que la memoria indexe a partir de el: enmascarados (decision ya tomada para la
     etapa 3).
   - Logs de la plataforma y del motor: nunca valores de `datos_extraidos`; como mucho el nombre del
     campo.
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
5. **Reparto.** PERSONA_2 implementa `rag.servicio.buscar_antecedentes(referencia_externa, proceso, *,
   desde, excluir_folio, limite=10)` sobre la memoria de folios (H14). PERSONA_1 hace el router, que
   decide `permitido` y `motivo` antes de llamar a la busqueda, y la pantalla "Antecedentes" en el
   expediente (H16).

## Alternativas

| Alternativa | Consecuencias |
|---|---|
| A3-b: el integrador recibe los datos completos | Es el sistema que consume el resultado, pero una API o un webhook con CURP en claro amplia la exposicion. Si un cliente lo necesita, se decide con su contrato de tratamiento de datos, fuera del MVP |
| A3-c: solo enmascarar en la UI | Rechazada en el ADR-006: la API seguiria devolviendo el valor |
| A4-b: `GET /documentos/{id}/datos/{campo}` | Un `GET` con efecto (auditoria) puede repetirse por cachés o precargas y dejar entradas falsas |
| A5-b: enmascarar solo `datos_extraidos` | El valor se escaparia por la evidencia (MRZ), las comparaciones, las correcciones y el webhook |
| A6-b: lista `campos_enmascarados` en cada `ResultadoDocumento` | Cambia el Contrato 1, que esta congelado; la ficha ya es la fuente de los campos |
| C3-b: `403` si el proceso no permite antecedentes | La UI tendria que distinguir este 403 del de rol; exige un codigo de error nuevo |
| C2-b: incluir folios abiertos | No tienen `resumen.md` ni decision, y la memoria no los indexa |
| C1-b: HMAC de la CURP | Identifica mejor a la persona, pero exige guardar y comparar un derivado de un dato sensible; descartado en R7 |

## A quien afecta

| Persona | Que cambia |
|---|---|
| PERSONA_1 (plataforma) | Enmascarar en todas las respuestas, comparaciones, correcciones, webhooks y `resumen.md`; `POST /documentos/{id}/revelar` con `dato_revelado`; router de antecedentes; `sensible` en `CampoFicha` (router) |
| PERSONA_1 (interfaz) | Boton "mostrar" en campos sensibles para revisor y admin (H17); pantalla de antecedentes (H16); `contrato.ts` y mocks regenerados con `scripts/generar_datos_mock.py` |
| PERSONA_2 (motor y configuracion) | `sensible: true` en las tres fichas y en el cargador (H15); `buscar_antecedentes` y memoria de folios sobre el `resumen.md` enmascarado (H14); logs del motor sin valores |

## Aplicacion
- **Cuando se acepte**: un PR de contratos con la linea de `endpoints.md` para `POST
  /documentos/{id}/revelar`, la forma de `GET /folios/{folio}/antecedentes` (y el rol admin), `sensible`
  en `CampoFicha` y la nota de enmascaramiento en "Reglas"; la accion de auditoria `dato_revelado` ya
  esta prevista en `endpoints.md` (ADR-006 1.5) y en `core/modelos.py`.
- **Etapa 3, dias 9-11**: H15 (PERSONA_2) antes que el enmascaramiento de la API; despues H17 y la
  pantalla de antecedentes (H16) cuando `buscar_antecedentes` este en `main`.
- El xfail de `antecedentes` en `tests/test_openapi_contrato.py` se quita cuando el router exista.

## Consecuencias
- Ningun valor sensible sale de la API en claro salvo por "mostrar", y cada uso queda auditado con el
  campo y el usuario.
- El integrador y los webhooks no exponen CURP, numero de pasaporte ni clave de elector.
- La pantalla distingue "no permitido", "sin referencia" y "sin antecedentes" sin codigos de error
  nuevos.
- Si se rechaza: el enmascaramiento queda solo en la UI (sin proteccion real) y `/antecedentes` sigue
  sin forma, lo que bloquea H16 y H17.
