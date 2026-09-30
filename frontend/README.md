# frontend (responsable: PERSONA_3)

React 18 + Vite. Consume `docs/contratos/endpoints.md`. Hasta que la API exista, usar msw con
respuestas construidas a partir del ejemplo de `ResultadoDocumento` en `backend/app/schemas/resultado.py`.

Pantallas MVP: login, lista de folios, carga de documentos, vista de expediente (diapositiva 8):
documentos del folio, detalle, datos extraidos con confianza, alertas por severidad,
comparaciones, acciones del revisor.

## Arranque
Requisitos: Node ^20.19 o >=22.12 (Vite 8).
```
cd frontend
cp .env.example .env      # VITE_API_URL y VITE_USAR_MOCKS; .env no se sube
npm ci
npm run dev               # http://localhost:5173
npm run build             # comprueba tipos (tsc) y genera dist/
npm run lint              # oxlint
```
Con Docker: servicio `frontend` de `docker-compose.yml` (este `Dockerfile`, Node 22).

## Stack
React 18 (el del stack del proyecto; por eso react-router 7, porque el 8 exige React 19),
react-router, Tailwind CSS 4 (plugin de Vite) e iconos lucide-react. Sin librerias de componentes.

## Estructura de `src/`
| Carpeta | Contenido |
|---|---|
| `api/` | `cliente.ts` (HTTP), `sesion.ts` (token), `auth.ts` (login y `/auth/yo`) |
| `mocks/` | Handlers de msw (tarea 3); `mocks/datos/` con los JSON ficticios |
| `paginas/` | Una pagina por ruta: login, folios, expediente |
| `componentes/` | Sesion (`ProveedorSesion`, `RutaProtegida`), `Estructura` comun |
| `tipos/` | `contrato.ts` (Contrato 1 exacto y peticiones/respuestas del 2), `codigos.ts` (errores y alertas oficiales) |
| `utilidades/` | `entorno.ts` (variables `VITE_*`) |

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
- `src/mocks/handlers.ts`: un handler por endpoint de `docs/contratos/endpoints.md`, con los roles
  del contrato y los errores de `codigos_error.md`. Otra ruta bajo `/api/v1`: 404 `RUTA_NO_ENCONTRADA`
  o 405 `METODO_NO_PERMITIDO`.
- Estado en memoria (`src/mocks/estado.ts`, se pierde al recargar). Lo que simula `src/mocks/logica.ts`:
  - subida: 202 `pendiente`, `procesando` a los 3 s y `completado` a los 9 s. Si el fichero es uno de
    `public/mock-originales` (mismo SHA-256), se usan sus valores; si no, los de un documento sano del tipo;
  - mismo SHA-256 en el folio: `DUP-001`; tipo declarado distinto del detectado: `CLS-001`;
  - regla 2.2 en la decision; folio cerrado tras decidir (409 `FOLIO_CERRADO`);
  - confirmar clasificacion (mismo tipo: resuelve `CLS-001`; otro: vuelve a `pendiente` y reprocesa);
  - recomendaciones, comparaciones y `CMP-001` se recalculan tras cada cambio.
  Los documentos de los datos iniciales no avanzan: el pendiente de `ONB-2026-000002` sigue pendiente.
- Comportamientos que el contrato no fijaba, acordados con PERSONA_1:
  - decidir con documentos `pendiente` o `procesando`: 409 `DOCUMENTO_EN_PROCESO`;
  - corregir datos o confirmar la clasificacion de un documento en `error`: 409 `DOCUMENTO_CON_ERROR`
    (sus alertas si se pueden resolver);
  - `EXP-001`: una por tipo requerido que falta, con `campo` = nombre del tipo. Se crean con el folio
    y se recalculan solo cuando un documento se procesa o se confirma (no al subirlo). Cuenta el
    **tipo efectivo** (`src/utilidades/expediente.ts`): confirmado; si no, detectado; si no, declarado.
    Si el revisor la marco como falso positivo (`aplica=false`), se conserva. La pantalla de carga
    usara `tiposRequeridosQueFaltan` con la misma regla para avisar de lo que falta;
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
    de rango. `endpoints.md` se actualiza en el PR de contratos del ADR-008.
- Campos sin valor: siempre `null`, nunca `""` ni solo espacios (tambien al corregir con PATCH de
  datos), con confianza 0 (ADR-007) y sin evidencia. La UI muestra `null` como "no detectado".
- Codigos acordados que aun no estan en los catalogos de main (`CODIGOS_PENDIENTES_DE_MAIN` en
  `src/tipos/codigos.ts`): `DOCUMENTO_CON_ERROR` (409) y la informativa `EXP-002` (tipo no pedido
  por el proceso, expediente). Los mocks ya los usan. Cuando entren en main se pasan a los oficiales
  y se quitan de la lista; `backend/tests/test_contrato_frontend.py` falla para recordarlo.
  `SECUENCIA_AGOTADA`, `VAL-003` (valor tomado de la MRZ), `VAL-004` (campo opcional ausente o null,
  uno por campo), `SYS-003` y `SYS-005` ya son oficiales.
- `/documentos/{id}/original`: URL a `public/mock-originales/` o, si se subio en la sesion, al propio
  fichero. Como la URL prefirmada real (caduca a los 300 s), cada peticion devuelve una nueva y la
  anterior deja de valer: la UI la pide cada vez que abre el visor.

## Pantallas
- Login (`paginas/PaginaLogin.tsx`): usuario y contrasena -> token, rol y `expires_in`; mensajes
  segun el codigo (`utilidades/mensajes.ts`); foco inicial en usuario y, si las credenciales fallan,
  en la contrasena; aviso si la sesion caduco. Vuelve a la pagina que se pidio.
- Sesion: se recupera con `GET /auth/yo` al recargar; un 401 o la caducidad local llevan al login.
- Layout (`componentes/Estructura.tsx`): enlace "Saltar al contenido", navegacion, usuario, rol y
  "Cerrar sesion".
- Folios (`paginas/PaginaFolios.tsx`, revisor y admin): `GET /folios` paginado (20), filtros de
  proceso y estado, columnas folio, proceso, fecha de solicitud, estado, recomendacion, documentos e
  indicador de bloqueantes sin resolver. "Nuevo folio" (integrador y revisor): proceso de
  `GET /procesos` y referencia opcional; lleva a la carga. El integrador no tiene `GET /folios`: ve un
  campo para abrir un folio por su numero.
  - Pendiente del PR de contratos del ADR-008 (aceptado): la columna `referencia_externa` no esta
    porque `ResumenFolio` aun no la tiene en `resultado.py` (pedirla con `GET /folios/{folio}` por fila
    costaba una peticion por folio). Vuelve cuando ese PR este en main. La carga de un folio si la
    muestra (viene en `ResultadoExpediente`).
- Carga (`paginas/PaginaCarga.tsx`, `/folios/{folio}/carga`): arrastrar o elegir varios archivos;
  extension validada contra `formatos_permitidos` del tipo declarado (`nombre_visible`); aviso de los
  tipos requeridos que faltan con el tipo efectivo; subida multipart; sondeo de `GET /documentos/{id}`
  cada 3 s hasta completado o error, que se para al salir; `DUP-001` y errores de analisis visibles.
  Solo lectura si el folio esta cerrado o el rol no puede subir (admin).
- Expediente (`paginas/PaginaExpediente.tsx`, `/folios/{folio}`, todos los roles; diapositiva 8):
  - Cabecera: folio, referencia, fecha de solicitud, proceso, estado, recomendacion global y, si esta
    cerrado, la decision con comentario, usuario y fecha. Enlace a la carga.
  - Izquierda: documentos del folio (tambien pendientes y procesando) con su estado. Mientras haya
    alguno en curso, sondeo de `GET /folios/{folio}` cada 3 s, que se para al terminar o al salir.
  - Centro (`componentes/DetalleDocumento.tsx`): original (`componentes/VisorOriginal.tsx`: la URL
    se pide cada vez que se abre porque caduca; `iframe` para PDF, `img` para imagen; solo revisor y
    admin), clasificacion declarada, detectada y confirmada con su confianza, tabla de datos con
    `<BarraConfianza>` (umbral de la ficha; texto de ADR-007), formato segun el tipo del campo, `null`
    como "no detectado", evidencia y "Corregido por revisor (antes: X)"; reglas y modelo usado.
    Documento en error: mensaje y alerta `SYS-00x`, sin reprocesar (fuera del MVP).
  - Derecha: resultado global, `<ListaAlertas>` del documento y del expediente agrupadas por
    severidad (informativa azul, preventiva amarillo, critica naranja, bloqueante rojo; siempre con
    icono y texto) con su estado de revision, y comparaciones con el valor de cada documento.
  - Acciones del revisor (`componentes/AccionesRevisor.tsx`, `api/revision.ts`), solo rol revisor y
    folio abierto: corregir un dato inline mostrando el valor actual (vaciarlo envia `null`, nunca
    `""`); confirmar la clasificacion (si cambia el tipo vuelve a `pendiente` y arranca el sondeo);
    "Aplica" / "Falso positivo" con comentario en alertas de documento y de expediente, por
    `alerta_id`; decision aprobar/rechazar con comentario y confirmacion. Aprobar esta deshabilitado
    mientras haya bloqueantes que no sean falso positivo (regla 2.2) y se listan las que bloquean.
    Nada se decide solo. Se refresca con la respuesta del endpoint (tras una accion de documento
    tambien el expediente). Un 409 (`DOCUMENTO_EN_PROCESO`, `DOCUMENTO_CON_ERROR`, `FOLIO_CERRADO`,
    `DECISION_BLOQUEADA`) muestra el motivo y recarga el expediente.
- Roles: `<RutaProtegida roles={[...]}>` para rutas (si no, "Sin permiso") y
  `<SoloRol roles={[...]} alternativa={...}>` para partes de una pantalla. Es solo interfaz: la API
  vuelve a comprobar el rol.

## Tests
```
npm test        # Vitest
```
- Mocks (Node): cobertura del contrato (falla si un endpoint no tiene handler) y flujos.
- Pantallas (jsdom + Testing Library + msw/node, `src/pruebas/app.tsx`): login con los 3 usuarios del
  mock, errores, recuperacion de sesion, caducidad, control de roles, folios (orden, filtros,
  paginacion, nuevo folio) y carga (subida, sondeo, tipos que faltan, DUP-001, cerrado, parada del
  sondeo). `src/pruebas/preparar.ts` usa el FormData y el File de Node en jsdom: la conversion de
  Vitest con jsdom 30 pierde el contenido y el nombre de los ficheros.
Si `docs/contratos/endpoints.md` no esta (contenedor que solo monta `frontend/`), la cobertura se omite.

## Tipos y datos de los mocks
- `src/tipos/contrato.ts` refleja `backend/app/schemas/resultado.py` campo a campo (las claves
  siempre estan: los opcionales son `T | null`) y `docs/contratos/endpoints.md`.
- `src/mocks/datos/*.json`: 4 folios ficticios coherentes con `fixtures/generados/INDICE.md`
  (`--hoy 2026-09-30`): alertas de las 4 severidades, `CMP-001` de domicilio, `EXP-001`, una
  correccion, un documento en error (`SYS-001`), uno pendiente y un folio aprobado. Las tres
  informativas: `VAL-003` (valor de `nacionalidad` tomado de la MRZ) en el pasaporte de
  `ONB-2026-000001`, `VAL-004` (`proveedor` sin leer, `null`) en el comprobante de `ONB-2026-000002` y
  `SYS-005` (analizado con el proveedor de respaldo, `openrouter` con un modelo ficticio) en la
  credencial de `ONB-2026-000003`.
- Confianza (ADR-007): la calcula el codigo comprobando el dato, no el modelo. La barra de la tabla
  de datos usara `ETIQUETA_CONFIANZA` ("Confianza verificada") y `AYUDA_CONFIANZA`
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
caducar se cierra sola aunque no haya peticiones.
