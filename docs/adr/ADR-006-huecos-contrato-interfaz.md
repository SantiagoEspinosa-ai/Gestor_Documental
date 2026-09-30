# ADR-006: Huecos del contrato para la UI del revisor

Fecha: 2026-09-30. Estado: ACEPTADO el 2026-09-30 (revision del PR #1: comentarios de PERSONA_1 y
PERSONA_2, y confirmacion de ambos, con reaccion +1, de K, el catalogo de alertas y la regla de
extraccion).
Propone: PERSONA_3. Afecta a: Contrato 1 (`backend/app/schemas/resultado.py`) y Contrato 2
(`docs/contratos/endpoints.md`). Este ADR no modifica ninguno de los dos: los cambios se aplican en
un PR de contratos aparte (ver "Aplicacion").

## Resumen para la reunion

| Punto | Descripcion | Bloque | Implementa | Decision |
|---|---|---|---|---|
| 1.1 | `GET /folios` paginado con `ResumenFolio` | 1 | PERSONA_1 | Aceptada la propuesta |
| 1.2 | `GET /procesos` visible para el revisor y con forma definida | 1 | PERSONA_1 | Aceptada la propuesta |
| 1.3 | `id` en `Alerta` y ruta de resolver por `alerta_id` | 1 | PERSONA_1 | Aceptada la propuesta: opcion con `alerta_id` |
| 1.4 | Catalogo de errores y codigos HTTP (`codigos_error.md`) | 1 | PERSONA_1 | Aceptada la propuesta, con `RESUMEN_NO_DISPONIBLE` (J) |
| 1.5 | Forma de `/tipos-documentales` y `/auditoria` | 1 | PERSONA_2 + PERSONA_1 | Aceptada la propuesta |
| 2.1 | Resolver alertas de expediente | 2 | PERSONA_1 | Aceptada la propuesta |
| 2.2 | `aplica`, comentario, autor y fecha en `Alerta` + regla de bloqueo | 2 | PERSONA_1 | Aceptada la propuesta |
| 2.3 | `CMP-001` solo en `alertas_expediente` | 2 | PERSONA_1 | Aceptada la propuesta |
| 2.4 | `correcciones` visibles en `ResultadoDocumento` | 2 | PERSONA_1 | Aceptada la propuesta |
| 2.5 | `tipo_documental_confirmado` y reproceso si cambia el tipo | 2 | PERSONA_1 + PERSONA_2 | Aceptada la propuesta, con la regla de extraccion |
| G | Datos de la decision y folio cerrado | 3 (pregunta) | PERSONA_1 | Resuelto: se guardan; folio cerrado sin reapertura |
| H | Caducidad de sesion, `GET /auth/yo`, formato del login | 3 (pregunta) | PERSONA_1 | Resuelto: JSON, `expires_in` y `GET /auth/yo` |
| I | Reprocesar documentos en `error` | 3 (pregunta) | PERSONA_1 + PERSONA_2 | Resuelto: fuera del MVP |
| J | Respuesta de `resumen.md` antes de existir | 3 (pregunta) | PERSONA_1 | Resuelto: 404 `RESUMEN_NO_DISPONIBLE` |
| K | Enums para `estado_general` y `decision_humana` | 3 (pregunta) | Los tres | Resuelto: `EstadoGeneral` y `DecisionHumana` |
| 3 | Edicion de procesos | 4 (aplazado) | - | Aplazado a ADR de etapa 3 |
| 4 | Enmascaramiento en backend y "mostrar" auditado | 4 (aplazado) | - | Aplazado a ADR de etapa 3 |
| 8 | Forma de `/antecedentes` y `referencia_persona` | 4 (aplazado) | - | Aplazado a ADR de etapa 3 |
| 6 | Referencia y fecha en la cabecera del expediente | Depende de ADR-004 | - | ADR-004 aceptado; se aplica en el PR de contratos |
| Coord. | Reparto de `modulos/rag` y aplicacion de este ADR | - | Los tres | Aceptado |

## Contexto
El frontend se construye contra mocks (msw) sacados solo de los Contratos 1 y 2, y no puede
inventar campos. Al disenar las pantallas del MVP (folios, carga, expediente, revision) aparecen
huecos: endpoints que no existen, respuestas sin forma definida y reglas ambiguas. Hoy cerrarlos
cuesta poco porque la API aun no esta implementada. En la etapa 2 costaria retrabajo a los tres.

Cada propuesta indica quien la implementa y que hacer si se rechaza. Todos los campos nuevos son
opcionales o tienen valor por defecto, asi que no rompen a quien ya consuma el Contrato 1. Solo
hay un cambio de ruta (A), y se hace antes de que exista la API.

Dependencia externa: la referencia externa y la fecha de solicitud en la cabecera del expediente
(hueco 6) dependen del ADR-004 (rama `propuesta/base-etapa0`). Este ADR no lo incluye. El ADR-004
se acepto el 2026-09-30 (ver "ADR-004 y catalogo de codigos de alerta"), asi que
`ResumenFolio.fecha_solicitud` (1.1) se rellena con `folios.creado_en`.

---

## Bloque 1 - Imprescindible en la etapa 1 (decidir antes del dia 3)

### 1.1 Lista de folios (hueco 1)
Problema: solo existe `GET /folios/{folio}`. La pantalla "Folios" no tiene de donde leer la lista.
Propuesta: `GET /folios?proceso=&estado_general=&pagina=1&tamano_pagina=20` (roles revisor, admin),
ordenado del mas reciente al mas antiguo. Respuesta:

    {"elementos": [ResumenFolio], "total": int, "pagina": int, "tamano_pagina": int}

Nuevo modelo `ResumenFolio` en el Contrato 1:

    folio: str
    proceso: str
    estado_general: str
    recomendacion_global: Recomendacion | None = None
    n_documentos: int = 0
    n_bloqueantes_sin_resolver: int = 0
    fecha_solicitud: datetime | None = None   # = folios.creado_en (ADR-004)

Implementa: PERSONA_1 (api + expediente). PERSONA_3: mocks y pantalla.
Si se rechaza: la UI recuerda en el navegador los folios creados desde el y permite abrir uno
escribiendo su numero. Los folios creados por integradores no aparecen en la lista.

### 1.2 Procesos visibles para el revisor (hueco 2)
Problema: `GET /procesos` excluye al revisor, pero el revisor puede hacer `POST /folios` y necesita
elegir proceso. Ademas, la respuesta solo dice "lista".
Propuesta: roles admin, integrador y revisor. Forma de cada elemento:

    {nombre, prefijo_folio, tipos_requeridos, tipos_opcionales, permitir_antecedentes,
     caducidad_antecedentes_dias, webhook_url, modelos}

`webhook_url` y `modelos` se omiten para el rol revisor.
Implementa: PERSONA_1.
Si se rechaza: se quita "Nuevo folio" al revisor (solo los integradores crean folios) y la pantalla
de carga no puede avisar de los tipos requeridos que faltan.

### 1.3 Identidad unica de cada alerta (hueco A)
Problema: la ruta `/documentos/{id}/alertas/{codigo}/resolver` da por hecho que solo hay una alerta
por codigo en cada documento. `VAL-001`, `VAL-002` y `CMP-001` se emiten una vez por campo: un
documento con dos obligatorios ausentes tiene dos `VAL-001`.
Propuesta: anadir `id: str | None = None` a `Alerta`. Lo asigna la plataforma al guardar la alerta
(ya existe `alertas.id` en BD). El motor de IA no lo rellena. Ruta nueva:
`POST /documentos/{id}/alertas/{alerta_id}/resolver`.
Implementa: PERSONA_1. PERSONA_2 no cambia nada.
Si se rechaza: se mantiene `{codigo}`, se anade el parametro `?campo=` y se fija la regla "nunca dos
alertas con el mismo (codigo, campo) en un documento" (PERSONA_1 y PERSONA_2 la garantizan).
Decision: se adopta la opcion con `alerta_id`. La alternativa `{codigo}` + `?campo=` queda descartada.

### 1.4 Catalogo de errores y codigos HTTP (hueco E)
Problema: el formato `{codigo, mensaje}` existe, pero no hay lista de codigos. Los mocks tendrian
que inventarlos.
Propuesta: nuevo fichero `docs/contratos/codigos_error.md`. No seria contrato congelado: se pueden
anadir codigos libremente, pero cambiar uno existente requiere ADR. Todo error de la API, tambien
los de validacion de FastAPI, usa `{codigo, mensaje}`. Lista inicial:

| HTTP | codigo | Cuando |
|---|---|---|
| 401 | CREDENCIALES_INVALIDAS | Login con usuario o contrasena incorrectos |
| 401 | NO_AUTENTICADO | Falta la cabecera Authorization o el token es invalido |
| 401 | TOKEN_CADUCADO | JWT expirado (la UI vuelve al login) |
| 403 | SIN_PERMISO | Rol sin acceso al endpoint |
| 404 | FOLIO_NO_ENCONTRADO / DOCUMENTO_NO_ENCONTRADO / ALERTA_NO_ENCONTRADA / PROCESO_NO_ENCONTRADO | Recurso inexistente |
| 404 | RESUMEN_NO_DISPONIBLE | `GET /folios/{folio}/resumen.md` antes de que exista el resumen (ver J) |
| 409 | DECISION_BLOQUEADA | `aprobar` con una bloqueante sin resolver (ver 2.2) |
| 409 | DOCUMENTO_EN_PROCESO | Accion del revisor sobre un documento `pendiente` o `procesando` |
| 409 | FOLIO_CERRADO | Accion sobre un folio `aprobado` o `rechazado` (ver G) |
| 413 | ARCHIVO_DEMASIADO_GRANDE | Supera el limite de 20 MB |
| 415 | FORMATO_NO_PERMITIDO | Extension fuera de `formatos_permitidos` del tipo |
| 422 | PETICION_INVALIDA | Cuerpo o parametros invalidos |
| 500 | ERROR_INTERNO | Error no controlado (sin detalles internos en `mensaje`) |

Un duplicado no es un error: se sigue devolviendo 202 con la alerta `DUP-001`.
Implementa: PERSONA_1 (manejador global de errores en api). PERSONA_3: mocks y mensajes de la UI.
Si se rechaza: la UI solo distingue por estado HTTP y muestra `mensaje` tal cual.

### 1.5 Forma de `/tipos-documentales` y `/auditoria` (hueco F)
Problema: las dos respuestas son "lista". La UI necesita `nombre_visible` y `formatos_permitidos`
en la carga, y `confianza_minima_campo` y el `tipo` de cada campo en la tabla de datos.
Propuesta `/tipos-documentales`: cada elemento es la ficha YAML tal como la valida `configuracion`:

    {nombre, nombre_visible, categoria, descripcion, formatos_permitidos,
     campos: {<campo>: {tipo, obligatorio, patron?}},
     confianza_minima_clasificacion, confianza_minima_campo, reglas, comparaciones}

Propuesta `/auditoria`: `[{id, usuario, accion, folio, documento_id, detalle, modelo, version_prompt,
creado_en}]`, del mas reciente al mas antiguo. `accion` es una lista cerrada: `login`,
`folio_creado`, `documento_subido`, `documento_procesado`, `dato_corregido`,
`clasificacion_confirmada`, `alerta_resuelta`, `decision_tomada` (y `dato_revelado` en la etapa 3).
`detalle` nunca contiene valores sensibles sin enmascarar.
Implementa: PERSONA_2 (serializar `TipoDocumental` en `configuracion/servicio.py`) y PERSONA_1
(routers y auditoria).
Si se rechaza: la UI usa un umbral fijo de 0.80, muestra los nombres tecnicos de los campos y
muestra `detalle` de la auditoria como JSON sin formato.

---

## Bloque 2 - Necesario en la etapa 2 (decidir antes del dia 6)

### 2.1 Resolver alertas de expediente (hueco 5)
Problema: solo se pueden resolver alertas de documento. `EXP-001` (falta un tipo requerido) es
bloqueante y va en `alertas_expediente`.
Propuesta: `POST /folios/{folio}/alertas/{alerta_id}/resolver` (rol revisor), con el mismo cuerpo
`{aplica, comentario?}` y la misma semantica que la de documento. Devuelve `ResultadoExpediente`.
Implementa: PERSONA_1.
Si se rechaza: las alertas de expediente no se resuelven a mano. Se recalculan: `EXP-001`
desaparece al subir el documento que falta. Si B se acepta, las `CMP-001` pasarian a ir en los
documentos (ver alternativa de 2.3).

### 2.2 Estado de revision de la alerta y regla de bloqueo (hueco 7)
Problema: la BD guarda `aplica` y `comentario`, pero `Alerta` solo expone `resuelta_por_revisor`.
La UI no distingue "aplica" de "falso positivo" y la regla de bloqueo es ambigua.
Propuesta: anadir a `Alerta`:

    aplica: bool | None = None           # None = sin revisar
    comentario_revisor: str | None = None
    resuelta_por: str | None = None      # usuario de la aplicacion
    resuelta_en: datetime | None = None

Regla (se escribe en endpoints.md): `aprobar` queda bloqueado mientras exista una alerta bloqueante,
de documento o de expediente, con `aplica` distinto de `false`. Si una bloqueante se marca
`aplica=true`, el problema queda confirmado y el folio solo puede rechazarse. Con esta regla la UI
calcula el motivo del boton deshabilitado sin inventar nada.
Implementa: PERSONA_1 (persistencia y control en `/decision`). PERSONA_3: UI.
Si se rechaza: la UI solo muestra "resuelta / sin resolver" y se basa en el 409
`DECISION_BLOQUEADA`, sin poder explicar el motivo de antemano.

### 2.3 Ubicacion de las alertas de comparacion (hueco B)
Problema: `CMP-001` afecta a dos documentos y el contrato no dice donde va.
Propuesta: las `CMP-001` van solo en `alertas_expediente`, una por campo comparado que no coincide y
con `campo` relleno. `comparaciones` conserva los valores. Nunca se duplican en los documentos.
Implementa: PERSONA_1 (`validacion/comparaciones.py`, tarea suya en la etapa 2).
Si se rechaza: la alerta se copia en cada documento implicado y resolver una resuelve la otra
(PERSONA_1 las sincroniza).

### 2.4 Correcciones visibles (hueco C)
Problema: el PATCH guarda en `correcciones`, pero el resultado no indica que campos se corrigieron
ni cual era el valor original.
Propuesta: anadir a `ResultadoDocumento` `correcciones: list[Correccion] = []`, con
`Correccion = {campo, valor_anterior, valor_nuevo, usuario, fecha}`. `datos_extraidos` refleja el
valor corregido, su confianza pasa a 1.0 y su evidencia a `"correccion_revisor"`.
Implementa: PERSONA_1.
Si se rechaza: endpoint aparte `GET /documentos/{id}/correcciones` con la misma forma, sin tocar
el Contrato 1.

### 2.5 Semantica de confirmar clasificacion (hueco D)
Problema: no se sabe si confirmar sobrescribe el tipo detectado, si resuelve `CLS-001` ni si se
vuelve a extraer cuando el revisor elige otro tipo (los campos cambian por tipo).
Propuesta: anadir `tipo_documental_confirmado: str | None = None` a `ResultadoDocumento`.
- Si el tipo confirmado es el mismo con el que se extrajo: se guarda, `CLS-001` queda resuelta
  automaticamente y no se reprocesa.
- Si es distinto del usado para extraer: se guarda, el documento vuelve a `pendiente` y se relanza
  `procesar_documento(documento_id, tipo_confirmado=...)` sin clasificar. La UI arranca el polling.
  - La transicion `completado -> pendiente` se anadira a la seccion "Estados" de endpoints.md.
  - El resultado anterior no se sobrescribe: se conserva como version previa en la tabla
    `resultados` (columna `version`) y el nuevo resultado es la version siguiente.

`procesar_documento` no forma parte del Contrato 3, asi que el parametro nuevo no requiere ADR.
Regla de extraccion (resuelta en la revision):
- Se extrae con la ficha del tipo declarado. Si no hay `tipo_declarado`, con la del tipo detectado.
- Si el detectado difiere del declarado, se emite `CLS-001` y decide el revisor.
- Confirmar un tipo distinto del usado para extraer relanza el procesamiento con
  `tipo_confirmado`, que manda sobre el declarado y el detectado.

Implementa: PERSONA_1 (endpoint y versionado en `resultados`) y PERSONA_2 (parametro
`tipo_confirmado`).
Si se rechaza: confirmar solo registra el tipo y resuelve `CLS-001`. Para volver a extraer, el
revisor sube de nuevo el archivo con el `tipo_declarado` correcto (lo que genera `DUP-001`, que se
marca como falso positivo).

---

## Bloque 3 - Preguntas abiertas (sin propuesta cerrada)

Se conservan tal como se plantearon. Todas quedaron resueltas: ver "Resoluciones del bloque 3".

| Hueco | Pregunta | Quien decide | Si nadie decide |
|---|---|---|---|
| G | Decision del folio: ¿se guardan comentario, usuario y fecha en `ResultadoExpediente`? Tras aprobar o rechazar, ¿se bloquean las acciones (409 `FOLIO_CERRADO`)? ¿Se puede reabrir un folio? | PERSONA_1 | La UI muestra solo `decision_humana` y trata el folio cerrado como de solo lectura |
| H | Login: ¿devuelve `expires_in`? ¿Existe `GET /auth/yo` para recuperar la sesion al recargar? ¿El cuerpo es JSON o el formulario OAuth2 de FastAPI? | PERSONA_1 | JSON; la UI lee la caducidad del JWT y guarda el rol en `sessionStorage` |
| I | Documento en `error`: ¿existe `POST /documentos/{id}/reprocesar` o queda fuera del MVP? | PERSONA_1 y PERSONA_2 | Fuera del MVP; la UI muestra el error y la alerta `SYS-00x` |
| J | `GET /folios/{folio}/resumen.md` antes de que exista el resumen (etapa 3): ¿404 con `RESUMEN_NO_DISPONIBLE`? | PERSONA_1 | La UI oculta "Ver resumen" si `ruta_resumen_md` es `null` |
| K | ¿Se convierten `estado_general` y `decision_humana` en enums (listas cerradas de valores), como `Severidad`? | Los tres | Se quedan como `str` y los mocks usan los valores de la seccion "Estados" |

## Resoluciones del bloque 3

Decididas en la revision del PR #1 (2026-09-30). G, H, I y J por PERSONA_1 (I tambien con
PERSONA_2); K por los tres.

- G, decision del folio: se guardan comentario, usuario y fecha de la decision en
  `ResultadoExpediente`. Tras aprobar o rechazar, el folio queda cerrado y no se reabre. Cualquier
  accion posterior sobre el folio o sus documentos devuelve 409 `FOLIO_CERRADO`.
- H, sesion: el login recibe JSON `{usuario, contrasena}` y devuelve
  `{access_token, rol, expires_in}`. Nuevo `GET /auth/yo` -> `{usuario, rol}` (todos los roles)
  para recuperar la sesion al recargar.
- I, reprocesar documentos en `error`: fuera del MVP. La UI muestra el error y la alerta `SYS-00x`.
- J, `resumen.md`: `GET /folios/{folio}/resumen.md` devuelve 404 `RESUMEN_NO_DISPONIBLE` mientras no
  exista. El codigo se anade a `codigos_error.md` (ver 1.4).
- K, enums: en el Contrato 1, `estado_general` pasa a `EstadoGeneral` =
  `en_revision | aprobado | rechazado` y `decision_humana` a `DecisionHumana` = `aprobar | rechazar`
  (los mismos valores que el cuerpo de `POST /folios/{folio}/decision`). Asi los mocks y la API no
  pueden usar valores distintos.

## ADR-004 y catalogo de codigos de alerta

Aceptados en la misma revision. Sus ficheros vienen de la rama `propuesta/base-etapa0` y se
incorporan en el PR de contratos, no en este:
- ADR-004: `ResultadoExpediente` incluye `referencia_externa` y `fecha_solicitud`
  (= `folios.creado_en`).
- `docs/contratos/codigos_alertas.md`: aprobado, con `EXP-001` bloqueante. Un folio sin un
  documento requerido no se aprueba, salvo que el revisor marque la alerta como falso positivo
  (2.1 y 2.2). Se ajusta para alinearlo con este ADR: la regla de bloqueo remite a 2.2 y `CMP-001`
  va en `alertas_expediente` (2.3).

---

## Bloque 4 - Aplazado a un ADR de la etapa 3

No se necesitan hasta la etapa 3 y dependen de decisiones que todavia no hay que tomar.

- Hueco 3, edicion de procesos: antes hay que decidir la fuente de verdad. Hoy `procesos.yaml` se
  vuelca a la BD en cada arranque, asi que una edicion desde la UI se perderia al reiniciar.
  Cambiar `prefijo_folio` con folios ya creados romperia la secuencia y las claves de S3. Idea
  inicial: prefijo inmutable y edicion solo de `webhook_url`, `permitir_antecedentes` y
  `caducidad_antecedentes_dias` por el admin. Excede el MVP.
- Hueco 4, enmascaramiento y "mostrar" auditado: el enmascaramiento real tiene que hacerse en el
  backend. Si la API devuelve la CURP completa y la UI solo la tapa, el dato ya esta en el
  navegador (visible en las herramientas de desarrollo) y auditar el clic no protege nada. Hay que
  decidir: marca `sensible: true` en los YAML (PERSONA_2), valores enmascarados en las respuestas
  segun el rol (PERSONA_1), un endpoint `POST /documentos/{id}/datos/{campo}/revelar` que registra
  `dato_revelado` en la auditoria, y como afecta a integradores y webhooks. PERSONA_2 pide que se le
  avise antes de anadir `sensible: true` a los YAML, para aceptarlo en el cargador.
- Hueco 8, forma de `/antecedentes`: la forma depende de como se identifique a la persona
  (`referencia_persona` en `memoria_folios`). Opciones:
  a) `referencia_externa` del folio. Es un identificador opaco del integrador, pero depende del
     ADR-004 y falta en los folios creados sin ella (por ejemplo, desde la UI).
  b) Hash SHA-256 de la CURP normalizada (mayusculas, sin espacios). Funciona sin integrador y no
     guarda la CURP en claro, pero solo existe si hay credencial de elector. Ademas, la CURP tiene
     estructura predecible, asi que un SHA-256 simple se puede revertir por fuerza bruta. Seria
     preferible HMAC-SHA256 con una clave del servidor. Sigue siendo un dato personal seudonimizado
     segun el RGPD.
  Tambien falta decidir la respuesta cuando `permitir_antecedentes=false` (403 o lista vacia).

---

## Coordinacion

Reparto propuesto de `modulos/rag` entre PERSONA_3 y PERSONA_2 (etapa 3):

| Fichero | Responsable | Contenido |
|---|---|---|
| `rag/memoria.py` | PERSONA_3 | Trocear e indexar `resumen.md`, tabla `memoria_folios`, `buscar_antecedentes(referencia_persona, proceso)` con permisos y caducidad |
| `rag/conocimiento.py` | PERSONA_2 | Indexar `docs/conocimiento/*.md` y `buscar(consulta, k)` para `contexto_rag`. Reutiliza `rag/embeddings.py` |
| `rag/servicio.py` | Comun | Unica API publica del modulo (ADR-005, regla 2); solo delega en memoria y conocimiento. Cambios por PR revisado por la otra persona |
| `rag/embeddings.py` | PERSONA_3 | Adaptador de embeddings (Ollama `nomic-embed-text`) que usan memoria y conocimiento (ADR-005, regla 3). El plan asigna a PERSONA_3 el apoyo en RAG |
| `rag/README.md` | Comun | Contrato de entrada y salida de las funciones de `servicio.py` |

- Las migraciones de Alembic de las tablas de `rag` las escribe su responsable, pero se encadenan
  en la historia de migraciones de PERSONA_1 (avisar antes para no crear dos "heads", es decir, dos
  ramas de migraciones en paralelo).
- El router `GET /folios/{folio}/antecedentes` lo hace PERSONA_1 en `api` y llama a
  `rag.servicio.buscar_antecedentes`.
- Quien empiece antes crea `rag/servicio.py` y `rag/README.md` con las firmas de los dos. La otra
  persona las integra con `git merge origin/main`.

Aplicacion de este ADR (aceptado):
1. PERSONA_3 aplica los cambios aceptados a `resultado.py` y `endpoints.md`, crea
   `docs/contratos/codigos_error.md` e incorpora el ADR-004 y `docs/contratos/codigos_alertas.md`,
   en un PR pequeno aparte que revisa PERSONA_1. Se avisa al equipo al abrirlo y al fusionarlo.
2. Mientras tanto, PERSONA_3 puede mockear lo propuesto en `feat/interfaz`, siempre aislado en
   `frontend/src/tipos/propuesta_adr006.ts`, para que no se mezcle con los tipos del contrato
   vigente. Tras fusionarse el PR del punto 1, lo consolida en los tipos definitivos y elimina lo
   que se haya rechazado.
3. Plazos: bloque 1 aceptado antes del dia 3; bloque 2 antes del dia 6.

## Consecuencias
- Los campos nuevos del Contrato 1 son opcionales o tienen valor por defecto: no rompen a nadie.
- El unico cambio que rompe compatibilidad es la ruta de resolver alerta (1.3). No cuesta nada
  porque la API aun no existe.
- La UI no depende de campos inventados. Lo propuesto se mockea aislado y se consolida solo si se
  acepta, asi que los mocks acaban coincidiendo con la API real.
- Si una propuesta se rechaza, su alternativa ya esta escrita y no hace falta otra ronda de
  discusion.
