# frontend (responsable: PERSONA_1; heredado de PERSONA_3, PR #13)

React 18 + Vite. Consume el Contrato 2 (`docs/contratos/endpoints.md`) con los tipos del Contrato 1
(`backend/app/schemas/resultado.py`). En desarrollo puede trabajar contra mocks de msw construidos
desde esos contratos y alineados con la API de PERSONA_1 (PR #3); en la etapa 2 pasa a la API real
cambiando solo `.env`.

Pantallas: login, lista de folios, carga de documentos, vista de expediente (diapositiva 8:
documentos del folio, detalle, datos extraidos con confianza, alertas por severidad,
comparaciones), acciones del revisor, resumen del expediente y auditoria (admin).

## Arranque
Requisitos: Node >= 22.22 (algunas dependencias del `package-lock.json` piden `^22.22.2`; la imagen de Docker
y el CI usan Node 22).
```
cd frontend
cp .env.example .env      # VITE_API_URL y VITE_USAR_MOCKS; .env no se sube
npm ci
npm run dev               # http://localhost:5173
npm run build             # comprueba tipos (tsc) y genera dist/
npm run lint              # oxlint
```
Con Docker: servicio `frontend` de `docker-compose.yml` (este `Dockerfile`, Node 22).

## Variables (`.env`, a partir de `.env.example`)
Solo variables `VITE_*`: acaban en el codigo que recibe el navegador, asi que nunca llevan secretos.
| Variable | Valor de ejemplo | Para que |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Base de la API; el cliente llama a `${VITE_API_URL}/api/v1` (`utilidades/entorno.ts`) |
| `VITE_USAR_MOCKS` | `true` | `true`: msw responde la API en el navegador (solo con `npm run dev`). `false`: API real |

## Stack
React 18 (el del stack del proyecto; por eso react-router 7, porque el 8 exige React 19),
react-router, Tailwind CSS 4 (plugin de Vite) e iconos lucide-react. Sin librerias de componentes.

## Estructura de `src/`
| Carpeta | Contenido |
|---|---|
| `api/` | `cliente.ts` (HTTP), `sesion.ts` (token), `auth.ts` (login y `/auth/yo`), `folios.ts`, `revision.ts`, `auditoria.ts` |
| `mocks/` | msw: `handlers.ts` (un handler por endpoint), `logica.ts` (simulacion), `estado.ts`, `token.ts` (token ficticio), `usuarios.ts`, `navegador.ts`; `mocks/datos/` con los JSON ficticios |
| `paginas/` | Una pagina por ruta: login, folios, carga, expediente, auditoria, procesos, sin permiso y no encontrada |
| `componentes/` | Sesion (`ProveedorSesion`, `RutaProtegida`, `SoloRol`), `Estructura` comun, expediente (`DetalleDocumento`, `VisorOriginal`, `BarraConfianza`, `ListaAlertas`, `AccionesRevisor`, `ResumenExpediente`), `FormularioNuevoFolio`, `Insignias`, `AvisoSondeoDetenido` |
| `tipos/` | `contrato.ts` (Contrato 1 exacto y peticiones/respuestas del 2), `codigos.ts` (errores y alertas oficiales y pendientes de main) |
| `utilidades/` | `entorno.ts` (variables `VITE_*`), `etiquetas.ts`, `mensajes.ts` (texto por codigo de error), `valores.ts`, `expediente.ts` (tipo efectivo, regla 2.2), `sondeo.ts`, `auditoria.ts` (detalle legible), `navegacion.ts` (vuelta tras el login), `procesos.ts` (webhook sin la URL) |
| `pruebas/` | Ayudas de los tests de pantallas (`app.tsx`, `preparar.ts`, `Ubicacion.tsx`) |

Fuera de `src/`: `e2e/` (Playwright), `scripts/comprobar-build-sin-mocks.mjs` y `public/mock-originales/`.

## Contrato del cliente HTTP (`src/api/cliente.ts`)
- Entrada: `peticion<T>(ruta, {metodo, cuerpo | formulario, respuesta: 'json' | 'texto'})` contra
  `${VITE_API_URL}/api/v1`, con `Authorization: Bearer <token>` si hay sesion.
- Salida: el cuerpo tipado, o lanza `ErrorApi {estado, codigo, message}` con el `{codigo, mensaje}`
  de la API. Codigos solo locales: `SIN_CONEXION` (estado 0) y `RESPUESTA_NO_VALIDA` (el cuerpo no
  tiene el formato del contrato).
- 401: borra la sesion y avisa (`alSesionCaducada`). Lo decide el estado HTTP, no el codigo. El
  login no cuenta: su 401 son credenciales incorrectas.
- 409 `FOLIO_CERRADO`: `error.esSoloLectura` y aviso `alFolioCerrado`; la UI pasa a solo lectura.

## Mocks (msw v2)
Solo en desarrollo (`npm run dev`) y con `VITE_USAR_MOCKS=true` en `.env`, `main.tsx` arranca msw
(`src/mocks/navegador.ts`) antes de pintar la app y todas las peticiones a `/api/v1` las responde el
navegador. Un `npm run build` nunca los incluye, aunque `.env` diga `true`: la condicion
`import.meta.env.DEV` elimina el codigo, el plugin `sin-mocks-en-build` de `vite.config.ts` quita
`mockServiceWorker.js` y `mock-originales/` de `dist/`, y `scripts/comprobar-build-sin-mocks.mjs`
hace fallar el build si queda algun rastro.
- Usuarios ficticios (`src/mocks/usuarios.ts`): `admin.demo` / `demo-admin`, `revisor.demo` /
  `demo-revisor`, `integrador.demo` / `demo-integrador`. Token de 3600 s.
- Token ficticio (`src/mocks/token.ts`): como un JWT, lleva dentro el usuario y la caducidad
  (`mock.<carga base64url>.<firma>`) y el mock lo valida sin memoria de lo que emitio. Por eso, igual
  que con la API real, la sesion sobrevive a una recarga o a escribir una URL en la barra. La "firma"
  (hash FNV-1a con una constante publica) solo detecta un token retocado a mano; no es seguridad. Un
  token retocado, inventado o del formato anterior da 401 `NO_AUTENTICADO`; uno caducado, `TOKEN_CADUCADO`.
- `src/mocks/handlers.ts`: un handler por endpoint de `docs/contratos/endpoints.md`, con los roles
  del contrato y los errores de `codigos_error.md`. Otra ruta bajo `/api/v1`: 404 `RUTA_NO_ENCONTRADA`
  o 405 `METODO_NO_PERMITIDO`.
- Estado en memoria (`src/mocks/estado.ts`): los datos (folios, subidas, decisiones, auditoria) vuelven
  a los iniciales al recargar; la sesion no se pierde (ver "Token ficticio"). Lo que simula `src/mocks/logica.ts`:
  - subida: 202 `pendiente`, `procesando` a los 3 s y `completado` a los 9 s. Si el fichero es uno de
    `public/mock-originales` (mismo SHA-256), se usan sus valores; si no, los de un documento sano del tipo;
  - mismo SHA-256 en el folio: `DUP-001`; tipo declarado distinto del detectado: `CLS-001`;
  - regla 2.2 en la decision; folio cerrado tras decidir (409 `FOLIO_CERRADO`);
  - confirmar clasificacion (ver abajo);
  - comparaciones, `CMP-001` y recomendacion global se recalculan tras cada cambio.

  Los documentos de los datos iniciales no avanzan: el pendiente de `ONB-2026-000002` sigue pendiente.
- **Alineado con la API de `main` tras el PR #9** (lo comprueban `handlers.test.ts` y los datos regenerados):
  - `PATCH /documentos/{id}/datos` (igual que `_valor_corregido`):
    - valida con la ficha de **extraccion** (confirmado > declarado > detectado);
    - `null` solo en un campo `obligatorio: false`; `""` o solo espacios, 422 tambien en un opcional (la UI nunca los envia);
    - `anio`: entero de 1000 a 9999 o texto de 4 cifras, guardado como entero (la API acepta `"0999"` y guarda `999`; ver "Pendientes");
    - el resto, texto no vacio: `fecha` en `AAAA-MM-DD` y `patron` si la ficha lo tiene;
    - 422 `campo desconocido: X` o `valor no valido para el campo X` (nombra el campo, nunca el valor), sin aplicar nada;
    - una entrada `dato_corregido` por PATCH;
  - `n_bloqueantes_sin_resolver` y la decision usan las alertas **visibles**: las del expediente y las de la version vigente de cada documento;
  - confirmar clasificacion:
    - con el mismo tipo, las `CLS-001` sin revisar pasan a falso positivo ("Resuelta al confirmar la clasificacion");
    - con otro tipo, el documento vuelve a `pendiente` sin tocar `CLS-001` y, mientras tanto, se ve la version anterior;
    - al completar, desaparecen las alertas del motor de esa version (aunque estuvieran revisadas) y sus correcciones, y solo quedan las de plataforma (`DUP-001`, `EXP-002`);
  - `EXP-001`:
    - solo cuentan los documentos `completado` (uno pendiente, procesando o en error no cubre su tipo);
    - mensaje "Falta el documento requerido: {nombre_visible}";
  - `CMP-001`:
    - comparaciones como `validacion.comparar`: por campo, con todos los documentos completados con valor de los tipos relacionados; los vacios no participan; normaliza mayusculas, acentos, espacios y fechas en varios formatos;
    - mensaje "Los documentos no coinciden en {campo}";
  - `EXP-001`, `CMP-001` y `EXP-002`: cuando la condicion desaparece se borran la sin revisar y la confirmada; solo se conserva el falso positivo (`aplica=false`);
  - recomendacion global (`expediente/recomendacion.py`): `revision_manual` si no hay documentos o alguno no esta completado, si hay una critica o bloqueante que no es falso positivo, o si algun documento no tiene ficha, confianza de clasificacion o confianzas por encima de los minimos; si no, `aprobar`. No usa la recomendacion del documento, que la da el analisis y, como la API (D3), se recalcula al corregir datos (no al resolver alertas). Al corregir, los mocks quitan tambien las `VAL-001`/`VAL-002`/`VAL-004` (salvo falso positivo) y la `VAL-003` sin revisar del campo corregido, pero no reevaluan las `REG-*`;
  - `detalle` de la auditoria (tabla de `api/README.md`):
    - `documento_procesado`: `{proveedor, respaldo_usado}` (modelo y `version_prompt` en sus columnas);
    - `dato_corregido`: `{campos}`;
    - `clasificacion_confirmada`: `{tipo, reproceso}`;
    - `alerta_resuelta`: `{alerta_id, codigo, aplica}`;
  - documento en `error` por fallo de S3 o del motor (`ONB-2026-000003`, el comprobante):
    - sin resultado, sin `SYS-00x` y sin entrada `documento_procesado`;
    - la UI lo explica sin codigo;
    - el aviso de tipos que faltan de la carga tampoco lo cuenta.
- Comportamientos que el contrato no fijaba, acordados con PERSONA_1:
  - decidir con documentos `pendiente` o `procesando`: 409 `DOCUMENTO_EN_PROCESO`;
  - corregir datos o confirmar la clasificacion de un documento en `error`: 409 `DOCUMENTO_CON_ERROR`
    (sus alertas si se pueden resolver);
  - `EXP-001`: una por tipo requerido que falta, con `campo` = nombre del tipo. Se crean con el folio
    y se recalculan solo cuando un documento se procesa o se confirma (no al subirlo). Cuenta el
    **tipo efectivo** (`src/utilidades/expediente.ts`): confirmado; si no, detectado; si no, declarado.
    La pantalla de carga usa `tiposRequeridosQueFaltan` con la misma regla para avisar de lo que falta,
    contando tambien los que se estan analizando (no los que acabaron en error);
  - `EXP-002` (definida por PERSONA_1 en el PR #9):
    - va en `alertas_encontradas` **del documento**, no en `alertas_expediente`, y es informativa;
    - se crea una por documento `completado` cuyo tipo efectivo no esta ni en `tipos_requeridos` ni en `tipos_opcionales` (`tipoNoPrevisto`), con `campo` = tipo y mensaje "Tipo de documento no previsto en el proceso: {nombre_visible}";
    - se recalcula al procesar o confirmar. Si el tipo pasa a estar previsto, se borran la sin revisar y la confirmada, y solo se conserva el falso positivo (`aplica=false`);
    - un documento no completado no se toca, y la alerta sobrevive al reproceso porque es de plataforma;
    - no bloquea ni cambia la recomendacion.

    Con `config/procesos.yaml` no sale nunca, porque `onboarding` preve los tres tipos (`pasaporte` es opcional); los tests la provocan quitando el pasaporte de los opcionales;
  - `POST /folios`: 201.
- Alineado con la API real de PERSONA_1 (PR #3):
  - subida: 415 `FORMATO_NO_PERMITIDO` si el contenido no corresponde a la extension (firma del
    fichero) y 422 `PETICION_INVALIDA` si el archivo esta vacio;
  - cuerpos JSON con campos que sobran: 422 `PETICION_INVALIDA` (en PATCH de datos, un campo que no
    es de la ficha, como antes);
  - anio del folio en hora de `America/Mexico_City`;
  - auditoria: `documento_subido` con `{hash_sha256, tamano_bytes, duplicado}` (nunca el nombre del
    fichero) y `folio_creado` con `detalle` vacio;
  - `GET /auditoria` paginada segun el ADR-008 (`PaginaAuditoria`): `tamano_pagina` 50 por defecto y
    de 1 a 100, orden `creado_en` desc e `id` desc, filtro por `folio`, 422 `PETICION_INVALIDA` fuera
    de rango.
- Campos sin valor: siempre `null`, nunca `""` ni solo espacios, con confianza 0 (ADR-007) y sin
  evidencia. La UI muestra `null` como "no detectado".
- Codigos: todos los que usan el frontend y los mocks son oficiales. `DOCUMENTO_CON_ERROR` (409) y la
  informativa `EXP-002` lo son desde el PR #9. `CODIGOS_PENDIENTES_DE_MAIN` (`src/tipos/codigos.ts`)
  queda vacia: si se acuerda un codigo nuevo antes de que llegue a los catalogos de main, va ahi, y
  `backend/tests/test_contrato_frontend.py` avisa cuando entra.
- `/documentos/{id}/original`: URL a `public/mock-originales/` o, si se subio en la sesion, al propio
  fichero. Como la URL prefirmada real (caduca a los 300 s), cada peticion devuelve una nueva y la
  anterior deja de valer: la UI la pide cada vez que abre el visor.

## Pantallas
- Login (`paginas/PaginaLogin.tsx`): usuario y contrasena -> token, rol y `expires_in`; mensajes
  segun el codigo (`utilidades/mensajes.ts`); foco inicial en usuario y, si las credenciales fallan,
  en la contrasena; aviso si la sesion caduco. Vuelve a la ruta completa que se pidio sin sesion
  (pathname, search y hash: `RutaProtegida` la guarda, en todas las rutas protegidas), pero solo si es
  interna (`utilidades/navegacion.ts`, `rutaInternaSegura`): empieza por una sola `/`, sin `//`, URL
  absoluta, barras invertidas ni caracteres de control, y no es `/login`. Si no, va a `/folios`.
  Tras 5 fallos de un usuario en 15 minutos la API responde `429 DEMASIADOS_INTENTOS` (ADR-011) y el login
  muestra "Demasiados intentos fallidos..."; los mocks aplican el mismo limite (`mocks/logica.ts`).
- Sesion: se recupera con `GET /auth/yo` al recargar; un 401 o la caducidad local llevan al login.
- Layout (`componentes/Estructura.tsx`): enlace "Saltar al contenido", navegacion, usuario, rol y
  "Cerrar sesion".
- Folios (`paginas/PaginaFolios.tsx`, revisor y admin): `GET /folios` paginado (20), filtros de
  proceso y estado, columnas folio, referencia (`referencia_externa` de `ResumenFolio`, ADR-008; "—"
  si es `null`), proceso, fecha de solicitud, estado, recomendacion, documentos e indicador de
  bloqueantes sin resolver. Una sola peticion por pagina. "Nuevo folio" (integrador y revisor): proceso de
  `GET /procesos` y referencia opcional; lleva a la carga. El integrador no tiene `GET /folios`: ve un
  campo para abrir un folio por su numero.
- Carga (`paginas/PaginaCarga.tsx`, `/folios/{folio}/carga`, con enlace "Ver expediente"): arrastrar o elegir varios archivos;
  extension validada contra `formatos_permitidos` del tipo declarado (`nombre_visible`); aviso de los
  tipos requeridos que faltan con el tipo efectivo; subida multipart; sondeo de `GET /documentos/{id}`
  hasta completado o error (ver "Sondeo"); `DUP-001` y errores de analisis visibles.
  Solo lectura si el folio esta cerrado o el rol no puede subir (admin).
- Expediente (`paginas/PaginaExpediente.tsx`, `/folios/{folio}`, todos los roles; diapositiva 8):
  - Cabecera: folio, referencia, fecha de solicitud, proceso, estado, recomendacion global y, si esta
    cerrado, la decision con comentario, usuario y fecha. Enlace a la carga.
  - Izquierda: documentos del folio (tambien pendientes y procesando) con su estado. Mientras haya
    alguno en curso, sondeo de `GET /folios/{folio}` (ver "Sondeo").
  - Centro (`componentes/DetalleDocumento.tsx`): original (`componentes/VisorOriginal.tsx`: la URL
    se pide cada vez que se abre porque caduca; `iframe` para PDF, `img` para imagen; solo revisor y
    admin), clasificacion declarada, detectada y confirmada con su confianza, tabla de datos con
    `<BarraConfianza>` (umbral de la ficha; texto de ADR-007), formato segun el tipo del campo, `null`
    como "no detectado", evidencia y "Corregido por revisor (antes: X)"; reglas y modelo usado.
    Datos sensibles (ADR-010, H17, `componentes/DatoSensible.tsx`): un campo `sensible` de la ficha de
    extraccion con valor sale enmascarado (`****1234`, como lo da la API) y, para revisor y admin (nunca el
    integrador; tambien con el folio cerrado), con el boton "Mostrar <campo>": `POST
    /documentos/{id}/revelar` (`api/revision.ts`, `revelarDato`), boton deshabilitado mientras carga, el
    valor completo con "Ocultar" y un aviso `aria-live`. El valor vive solo en el estado del componente
    (nada de storage, URL ni consola) y se oculta al pulsar "Ocultar", al cambiar de documento o de
    pantalla y solo a los `SEGUNDOS_DATO_REVELADO` (60 s, `utilidades/etiquetas.ts`). Errores con
    `mensajeRevelar` (`utilidades/mensajes.ts`): 409 en proceso o con error, 403 y 422; el valor sigue
    enmascarado. Solo en la tabla de datos: comparaciones, evidencia y correcciones siguen enmascaradas.
    Documento en error: mensaje y alerta `SYS-00x`, sin reprocesar (fuera del MVP).
    Documento no reconocido (ADR-009, H4): un detectado `desconocido` (`TIPO_DESCONOCIDO` en
    `tipos/contrato.ts`) sale como "Tipo no reconocido" en la clasificacion, en la lista del expediente y
    en la tabla de la carga; nunca se busca su ficha ni su umbral (`fichaDeTipo` y `nombreTipo` de
    `utilidades/expediente.ts`). Sin ficha para el tipo de extraccion y sin datos, en vez de una tabla
    vacia se ve el aviso "No se han extraído datos: el tipo del documento no está reconocido. Confirma la
    clasificación para analizarlo con la ficha correcta."; el revisor, con el folio abierto, tiene
    "Confirmar clasificación". `desconocido` no cubre ningun requerido (como `_tipo_efectivo` del backend)
    y lleva `EXP-002` "Tipo de documento no reconocido".
  - Derecha: resultado global, `<ListaAlertas>` del documento y del expediente agrupadas por
    severidad (informativa azul, preventiva amarillo, critica naranja, bloqueante rojo; siempre con
    icono y texto) con su estado de revision, y comparaciones con el valor de cada documento.
  - Antecedentes (H16, ADR-010 C, `componentes/Antecedentes.tsx`, solo revisor y admin): `GET
    /folios/{folio}/antecedentes` (`api/folios.ts`, `obtenerAntecedentes`). Lista con el folio (enlace al
    expediente), fechas de solicitud y decision, estado y decision, y el fragmento del resumen con el mismo
    renderizado seguro que "Ver resumen" (react-markdown con `skipHtml`, sin enlaces ni imagenes). Estados:
    cargando, error, no permitido con el motivo legible (`ETIQUETA_MOTIVO_SIN_ANTECEDENTES`: proceso sin
    antecedentes o folio sin referencia), sin antecedentes y antecedente sin fragmento en la memoria.
  - Acciones del revisor (`componentes/AccionesRevisor.tsx`, `api/revision.ts`), solo rol revisor y
    folio abierto: corregir un dato inline mostrando el valor actual (`utilidades/valores.ts`,
    `prepararCorreccion`). En un campo opcional, vaciarlo envia `null`, nunca `""`. En uno obligatorio
    de la ficha no se puede guardar vacio: "Guardar" queda deshabilitado y se explica por que. Un
    `anio` se valida antes de enviar (4 cifras, `AAAA`) y va como entero. Confirmar la clasificacion (si cambia el tipo vuelve a `pendiente` y arranca el sondeo);
    "Aplica" / "Falso positivo" con comentario en alertas de documento y de expediente, por
    `alerta_id`; decision aprobar/rechazar con comentario y confirmacion. Aprobar esta deshabilitado
    mientras haya bloqueantes que no sean falso positivo (regla 2.2) y se listan las que bloquean.
    Nada se decide solo. Se refresca con la respuesta del endpoint (tras una accion de documento
    tambien el expediente). Un 409 (`DOCUMENTO_EN_PROCESO`, `DOCUMENTO_CON_ERROR`, `FOLIO_CERRADO`,
    `DECISION_BLOQUEADA`) muestra el motivo y recarga el expediente.
  - "Ver resumen" (`componentes/ResumenExpediente.tsx`): `GET /folios/{folio}/resumen.md` renderizado
    con `react-markdown` con `skipHtml` (nunca HTML crudo). Solo aparece si `ruta_resumen_md` no es
    `null`; un 404 `RESUMEN_NO_DISPONIBLE` muestra su mensaje. En los mocks solo lo tiene el folio
    aprobado `ONB-2026-000004` (resumen ficticio generado con sus datos).
- Sondeo (`utilidades/sondeo.ts`, hook `useSondeo`, comun a la carga y al expediente): mientras haya
  documentos pendientes o procesando consulta con una espera de 3 s que crece x1,5 hasta 15 s; un
  cambio de estado vuelve a los 3 s. Tras 10 minutos sin cambios (Ollama lento o caido) se detiene y
  muestra "Sigue en proceso" con "Comprobar de nuevo", que consulta en el momento y lo reanuda. Nunca
  solapa consultas y se para al salir de la pantalla.
- Auditoria (`paginas/PaginaAuditoria.tsx`, `/auditoria`, solo admin; enlace "Auditoría" en la
  cabecera solo para ese rol, los demas que entran por URL ven "Sin permiso"): `GET /auditoria`
  segun el ADR-008 (`api/auditoria.ts`), 50 por pagina por defecto (selector 20, 50 o 100), del mas
  reciente al mas antiguo, filtro por folio (texto, en mayusculas y sin espacios) y paginacion con el
  total. Filtro, pagina y tamano van en la URL (`?folio=&pagina=&tamano_pagina=`): se puede compartir
  el enlace y un valor fuera de rango puesto a mano muestra el 422 con un enlace a la auditoria sin
  filtros. Columnas: fecha con segundos, usuario ("Sistema" si es `null`: procesamiento en segundo
  plano), accion con texto legible (`ETIQUETA_ACCION`, lista cerrada del ADR-006 1.5), folio con
  enlace al expediente, documento (id abreviado), detalle y modelo · `version_prompt`.
  - Detalle (`utilidades/auditoria.ts`, `describirDetalle`): nunca JSON en bruto. Frases por accion con
    las claves conocidas (resultado del login; SHA-256 abreviado, tamano y duplicado de la subida;
    resultado del analisis; campo corregido o mostrado; tipo confirmado con su `nombre_visible`;
    alerta y su revision; decision). Cualquier otra clave, o una conocida con un tipo inesperado, sale
    enmascarada (`****` y los 4 ultimos caracteres; objetos y listas ocultos): si la API anade valores
    o comentarios, no se ven completos.
  - Estados: cargando, vacio (con o sin filtro) y error (403 `SIN_PERMISO`, 422 `PETICION_INVALIDA`).
- Procesos (`paginas/PaginaProcesos.tsx`, `/procesos`, solo admin; enlace "Procesos" en la cabecera
  junto a "Auditoría"; los demas que entran por URL ven "Sin permiso"): `GET /procesos` en SOLO
  LECTURA (H8, recorte R3; la edicion queda fuera del MVP por el ADR-006, bloque 4). Tabla con nombre,
  prefijo de folio, tipos requeridos y opcionales con su `nombre_visible` (el nombre tecnico si no hay
  ficha), antecedentes (Si/No) y su caducidad en dias, modelos ("Por defecto" si es `null`) y webhook.
  Del webhook NUNCA se muestra la URL (puede llevar una ruta o un token): "Sin webhook" si es `null`,
  "Configurado (host)" con solo `new URL(...).host`, o "Configurado" si no se puede leer. Nota fija:
  los procesos se cambian en `config/procesos.yaml` y se cargan al arrancar la API. Estados: cargando,
  vacio y error con el mensaje del codigo.
- Roles: `<RutaProtegida roles={[...]}>` para rutas (si no, "Sin permiso") y
  `<SoloRol roles={[...]} alternativa={...}>` para partes de una pantalla. Es solo interfaz: la API
  vuelve a comprobar el rol.

## Tests
```
npm test        # Vitest
```
177 tests en 18 ficheros (2026-10-01):
- Mocks (Node): cobertura del contrato (falla si un endpoint no tiene handler), flujos, datos y token
  (sigue valido tras reiniciar msw; uno retocado o inventado da `NO_AUTENTICADO`).
- Componentes: `BarraConfianza`, `ListaAlertas` y `SoloRol`.
- Utilidades: `expediente` (tipo efectivo, regla 2.2), `mensajes`, `valores`, `sondeo`, `auditoria`
  (detalle por accion, enmascarado) y `navegacion` (rutas internas aceptadas y externas rechazadas).
- Pantallas (jsdom + Testing Library + msw/node, `src/pruebas/app.tsx`): login con los 3 usuarios del
  mock, errores, recuperacion de sesion (tambien tras "recargar" los mocks), caducidad, vuelta tras el
  login con parametros y hash, control de roles, folios (orden, filtros, paginacion, nuevo folio),
  carga (subida, sondeo, tipos que faltan, DUP-001, cerrado, parada del sondeo), expediente, acciones
  del revisor, resumen y auditoria (paginacion, tamano, filtro, detalle por accion sin valores
  completos, vacio, 403, 422 y roles).
- Ayudas: `usarServidorMock()` da `estado`, `peticiones`, `consultas` (con la query) y `servidor`
  (para sobrescribir un handler con `servidor.use`); `reiniciarMocks` simula recargar la pagina (msw
  con estado nuevo) y `<Ubicacion>` (`src/pruebas/Ubicacion.tsx`) muestra la ruta completa del router.
  `src/pruebas/preparar.ts` usa el FormData y el File de Node en jsdom: la conversion de Vitest con
  jsdom 30 pierde el contenido y el nombre de los ficheros.
Si `docs/contratos/endpoints.md` no esta (contenedor que solo monta `frontend/`), la cobertura se omite.

### e2e con Playwright sobre los mocks (`e2e/`)
```
npx playwright install chromium   # una vez: solo Chromium
npm run test:e2e                  # arranca `npm run dev` en el puerto 5174 con VITE_USAR_MOCKS=true
```
- `npm test` (Vitest) no los ejecuta: Vitest solo mira `src/**/*.test.*` y Playwright solo `e2e/**/*.e2e.ts`.
- `playwright.config.ts` fija `VITE_USAR_MOCKS=true` en el proceso del servidor, que manda sobre
  `frontend/.env`. Usa el puerto 5174 para no chocar con un `npm run dev` abierto.
- Los datos de los mocks viven en la memoria de la pagina: cada test empieza con los datos iniciales.
  Un test que necesita lo que hizo antes (una decision, una subida) navega dentro de la app sin
  recargar, porque recargar o `page.goto` reinician los datos. La sesion si sobrevive a la recarga
  (token ficticio).
- Casos: flujo del revisor (login, nuevo folio onboarding, subir credencial y comprobante del caso
  sano, esperar completado, expediente, revisar alertas, aprobar con comentario y folio en solo
  lectura); bloqueante de `ONB-2026-000001` ("Aplica" en `REG-vigencia_documento`, Aprobar
  deshabilitado con el motivo, Rechazar con confirmacion); roles (admin sin acciones, integrador sin
  lista de folios ni original); duplicado (`DUP-001` al subir dos veces y revisarlo como falso positivo);
  auditoria (el revisor rechaza `ONB-2026-000001`, cambia a admin sin recargar con `cambiarDeUsuario`,
  abre "Auditoría", filtra por ese folio, ve "Decisión: Rechazado" y abre el expediente; sin sesion en
  `/auditoria?tamano_pagina=500`, tras el login como admin vuelve con los parametros y ve el 422;
  recargar mantiene la sesion y la URL completa; el revisor
  que entra por URL ve "Sin permiso"); correccion de datos (un obligatorio no se vacia, un opcional
  vaciado queda en "no detectado", y un `anio` con menos de 4 cifras no se guarda); mostrar (el revisor
  muestra y oculta la CURP de una credencial, H17); antecedentes (el revisor ve en el folio 2 su antecedente, el
  folio 4, y lo abre).
- 12 tests en 8 ficheros; `e2e/ayudas.ts` tiene `entrar`, `cambiarDeUsuario` (sin recargar),
  `nuevoFolio`, `subir`, `filaCarga` y `abrirFolio`.
- Salidas en `test-results/` y `playwright-report/` (fuera de git). Si falla, la traza:
  `npx playwright show-trace test-results/<test>/trace.zip`.

### e2e reales de la etapa 2 (contra el backend y Ollama, sin mocks)
- `OLLAMA_BASE_URL` del backend, segun donde corren el backend y Ollama (`.env.example`):

  | Backend | Ollama | `OLLAMA_BASE_URL` |
  |---|---|---|
  | En el equipo (venv) | Instalado en el equipo | `http://localhost:11434` |
  | En un contenedor (`docker compose up`) | Instalado en el equipo (Docker Desktop) | `http://host.docker.internal:11434` (valor por defecto) |
  | En un contenedor | Contenedor, con `docker compose --profile ollama up` | `http://ollama:11434` |

- Modelos que hay que tener descargados en ese Ollama (con el perfil, dentro del contenedor:
  `docker compose exec ollama ollama pull ...`):
  ```
  ollama pull qwen2.5vl:3b   # vision: pdf_escaneado e imagen (~5 GB de RAM)
  ollama pull gemma4:e2b     # texto: pdf_digital
  ```
- Antes de lanzarlos, comprobar que Ollama responde (`GET <OLLAMA_BASE_URL>/api/tags`) y lista los dos
  modelos. Los tiempos reales son de minutos por documento (vision ~110 s), no los ~9 s del mock.
- `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` (por defecto): OpenRouter no se usa nunca, ni como respaldo
  (ADR-003). Si Ollama falla, el documento acaba en `error` con `SYS-001`.

### e2e reales (H6): humo contra la API real con el stub (`e2e-real/`)
```
npm run test:e2e:real   # playwright.real.config.ts: Chromium, workers 1, http://localhost:5173
```
- Requisitos (este proyecto no arranca nada; `e2e-real/comprobar-servidores.ts` lo comprueba antes y
  falla con un mensaje claro):
  - backend en el equipo en `:8000` (`uvicorn app.main:app --port 8000` desde `backend/`, con la BD
    migrada) y con `MOTOR_ANALISIS=stub` en su entorno: el humo no usa Ollama (con `real`, cada documento
    tardaria minutos); `GET /api/v1/procesos` sin token tiene que dar 401;
  - `npm run dev` en `:5173` con `VITE_USAR_MOCKS=false` y `VITE_API_URL=http://localhost:8000`;
  - un usuario de cada rol en variables de entorno del proceso, nunca en el repo:
    `E2E_REVISOR_USUARIO`/`E2E_REVISOR_CLAVE`, `E2E_ADMIN_USUARIO`/`E2E_ADMIN_CLAVE` y
    `E2E_INTEGRADOR_USUARIO`/`E2E_INTEGRADOR_CLAVE` (se crean con `scripts/crear_usuario.py`). Si falta
    alguna, el test se omite con el motivo.
- Sin traza (`trace: 'off'`): guardaria lo escrito en el login y el cuerpo de `POST /auth/login`. Solo
  captura si falla, con la contrasena tapada (`type=password`).
- Casos (cada uno crea su folio con `referencia_externa` `E2E-<timestamp>`, sin depender de datos
  existentes): `revisor_flujo` (folio nuevo con sus 2 `EXP-001`, subir credencial y comprobante del
  caso sano digital con su tipo declarado, esperar "Completado" con `expect.poll` hasta 5 min por
  documento, las `EXP-001` desaparecen, aprobar con comentario y folio cerrado en solo lectura; despues,
  "Ver resumen" muestra el `resumen.md` regenerado con el folio, la referencia `E2E-...` y la decision, sin el
  nombre de la persona en la cabecera);
  `admin_auditoria` (en serie tras el anterior: en `/auditoria?folio=` estan "Folio creado", 2
  "Documento subido", 2 "Documento analizado" y "Decisión del folio"); `integrador_roles` (sin lista de
  folios, "Sin permiso" en `/auditoria` y `/procesos`, y en el expediente de su folio "Tu rol no puede
  ver el original del documento."); `revisor_mostrar` (con el stub no hay datos: el revisor escribe una
  CURP ficticia, sale enmascarada, la muestra y la oculta) y `admin_auditoria_revelado` (en serie: en
  `/auditoria?folio=` hay un "Dato revelado" con "Campo: curp" y nunca el valor).
- Aviso: cada ejecucion sube 3 PDF ficticios (`public/mock-originales`) al bucket de desarrollo, crea 2
  folios en la BD local y escribe sus `resumen.md` (se regeneran en cada cambio). Con el stub tarda unos 30 s.
- `npm test` y `npm run test:e2e` no los recogen (`src/**/*.test.*` y `e2e/**/*.e2e.ts`).
- Falta: los casos del motor real con los folios de `INDICE.md` cuando `procesar_documento` sustituya al
  stub, calentar Ollama antes de cronometrar y los tiempos de H12 (spec de PERSONA_2, seccion 13).

## Tipos y datos de los mocks
- `src/tipos/contrato.ts` refleja `backend/app/schemas/resultado.py` campo a campo (las claves
  siempre estan: los opcionales son `T | null`) y `docs/contratos/endpoints.md`.
- `src/mocks/datos/*.json`: 4 folios ficticios coherentes con `fixtures/generados/INDICE.md`
  (`--hoy 2026-09-30`): alertas de las 4 severidades, `CMP-001` de domicilio, `EXP-001`, una
  correccion, dos documentos en error en `ONB-2026-000003` (el pasaporte con `SYS-001` y el comprobante
  por un fallo de S3 o del motor, sin `SYS-00x`), uno pendiente y un folio aprobado. En
  `ONB-2026-000003`, ademas, un documento subido sin tipo declarado que el motor no reconoce
  (`tipo_documental_detectado: "desconocido"`, sin datos; opcion `no_reconocido` del generador, con un
  fichero que ningun otro documento usa para que el clasificador de los mocks no lo reutilice). Cuatro
  alertas informativas, todas posibles con la configuracion por defecto: dos `VAL-003` (`nacionalidad` y
  `sexo` tomados de la MRZ) en el pasaporte escaneado de `ONB-2026-000001`, `VAL-004` (`proveedor`
  sin leer, `null`) en el comprobante de `ONB-2026-000002` y `EXP-002` ("Tipo de documento no
  reconocido") en el documento no reconocido de `ONB-2026-000003`.
- Sin `SYS-005`: lo emite `motor_ia` cuando el principal falla y se usa el respaldo, y el unico
  respaldo de `config/modelos.yaml` es OpenRouter (`privado: false`), que con
  `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` no se usa nunca (ADR-003). Con esa configuracion, un fallo
  de Ollama da `SYS-001` (documento en error de `ONB-2026-000003`).
- `fecha_y_modelo_utilizado` y la auditoria de `documento_procesado` usan siempre `ollama` con los
  modelos de `.env.example` (`docs/motor_ia/pruebas_ollama.md`): `gemma4:e2b` para los PDF digitales
  (solo texto) y `qwen2.5vl:3b` para escaneados e imagenes. Un documento subido en la sesion toma el
  modelo del original con el mismo SHA-256; si no lo hay, el de su extension (PDF -> texto).
- Confianza (ADR-007): la calcula el codigo comprobando el dato, no el modelo. La barra de la tabla
  de datos usa `ETIQUETA_CONFIANZA` ("Confianza verificada") y `AYUDA_CONFIANZA`
  (`src/utilidades/etiquetas.ts`).
- `public/mock-originales/`: copias de los fixtures que usan los mocks (mismo SHA-256).
- Se generan con `python scripts/generar_datos_mock.py` (no editar los JSON a mano). La fecha es
  fija, `2026-09-30`, y los tests usan la misma, asi que no caducan.
- Para reproducir `DUP-001` contra los documentos de los mocks subiendo fixtures reales, generalos con
  esa fecha: `python scripts/generar_fixtures.py --hoy 2026-09-30` y sube, por ejemplo,
  `credencial_elector_sano_digital.pdf` a `ONB-2026-000003`. Con otra fecha los SHA-256 cambian y
  solo hay `DUP-001` si subes dos veces el mismo fichero en la sesion.
- `backend/tests/test_contrato_frontend.py` comprueba todo lo anterior contra los contratos,
  `config/` y el generador de fixtures:
  `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_contrato_frontend.py`.

## Sesion
Token, rol e instante de caducidad (`Date.now() + expires_in * 1000`) en `sessionStorage`, con
respaldo en memoria si el navegador lo bloquea. Al recargar se recupera con `GET /auth/yo`; al
caducar se cierra sola aunque no haya peticiones. Sin sesion, cualquier ruta protegida lleva al login
y, tras entrar, se vuelve a la ruta completa si es interna (ver "Login" en "Pantallas").

## Pendientes
- HECHO (H1, 2026-10-02): probar la UI contra la API real de PERSONA_1 (`VITE_USAR_MOCKS=false`) y
  reportar como issue cualquier desviacion del contrato. Sin desviaciones; detalle en
  `docs/equipo/PERSONA_1_estado.md`, seccion "H1 (2026-10-02)".
- Etapa 2: humo real con el stub HECHO (H6, ver "e2e reales (H6)"). Falta con el motor real: los
  casos de fixtures sobre `docker compose` y Ollama (ver "e2e reales de la etapa 2").
- Con PERSONA_1 (menor, no bloquea): la API acepta un `anio` `"0999"` y lo guarda como `999`, de 3
  cifras. La UI no lo envia nunca (exige `[1-9]\d{3}`) y el mock hace lo mismo que la API mientras no
  cambie.
- HECHO (H10): forma de `tiempos` (`{segundos_modelo}`) y `tokens` (`{entrada, salida}`) del motor real
  revisada; `describirDetalle` muestra tambien `modalidad`, `paginas`, el prompt de clasificacion y el
  numero de llamadas al modelo, sin enmascararlos por error.
- HECHO (ADR-010, PR A): la API y los mocks enmascaran los campos sensibles (`****` + 4 ultimos) en
  todas las respuestas y para todos los roles. Los mocks (`mocks/logica.ts`: `mascara`,
  `enmascararDocumento`, `enmascararExpediente`) aplican la MISMA mascara que `core/enmascaramiento.py` solo
  al responder: el estado en memoria guarda el valor real, como la BD. `POST /documentos/{id}/revelar`
  responde como la API (revisor y admin, 403 al integrador, 422/404/409, `Cache-Control: no-store` y
  `dato_revelado` con `{campo}`). Al corregir un campo `sensible`, `EditorCampo` empieza vacio (el valor
  llega enmascarado y no debe guardarse la mascara).
- HECHO (H17, PR B): boton "Mostrar" de los datos sensibles para revisor y admin, con auto-ocultado a los
  60 s (ver "Expediente" en "Pantallas").
- Post-MVP (ADR-013, propuesta): en el detalle del documento, revisor y admin con el folio abierto ven "Retirar"
  (`componentes/RetirarDocumento.tsx`): motivo obligatorio de 3 a 200 caracteres y confirmacion. El retirado sale
  atenuado y marcado "Retirado" (tambien en la lista), con su motivo y "Restaurar"; sin acciones de revision. No
  cuenta para la cobertura, las comparaciones, la recomendacion ni las bloqueantes (`cuentaEnElFolio` en
  `utilidades/expediente.ts`). Los mocks lo implementan como la API (`recalcularDuplicados` y los filtros de
  `mocks/logica.ts`); en los datos, el comprobante duplicado de ONB-2026-000001 esta retirado.
- Post-MVP (ADR-010 A4c, aceptada): junto a "Mostrar", un campo corto "Motivo (opcional)" que no bloquea; se
  envia como `motivo` si tiene de 3 a 200 caracteres. La API (y `enmascararTexto` en los mocks) lo guarda
  tapado en `dato_revelado`, y la auditoria lo muestra como "Motivo: ...".
- HECHO (H16): antecedentes del folio en el expediente (ver "Pantallas"). En los mocks, el folio 2 y el 4 tienen
  la misma referencia (`scripts/generar_datos_mock.py`): el 4, cerrado, es el antecedente del 2; el 3 no tiene
  referencia. El fragmento del mock es el principio de su `resumen.md` de mock.
- HECHO (H8, 2026-10-02): pantalla de configuracion de procesos, en solo lectura (recorte R3; ver
  "Procesos" en "Pantallas").
- `resumen.md` (etapa 3, `ResumenExpediente.tsx`): el resumen usa solo listas (datos de cada documento y
  comparaciones), sin tablas, para verse bien con `react-markdown` sin plugins (sin `remark-gfm`).
- HECHO (H4): `desconocido` como "Tipo no reconocido" y aviso si no hay ficha ni datos (ADR-009; ver
  "Documento no reconocido" en "Pantallas"). Queda de H3: los mocks con `version_prompt` y evidencias
  del motor real.
- Fuera del MVP: reprocesar un documento en `error` (ADR-006, I).
