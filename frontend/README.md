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
- Codigos acordados que aun no estan en los catalogos de main (`CODIGOS_PENDIENTES_DE_MAIN` en
  `src/tipos/codigos.ts`): `DOCUMENTO_CON_ERROR` (409), `SECUENCIA_AGOTADA` (409) y las informativas
  `VAL-003` (falta un campo opcional, documento) y `EXP-002` (tipo no pedido por el proceso,
  expediente). Los mocks ya los usan. Cuando entren en main se pasan a los oficiales y se quitan de
  la lista; `backend/tests/test_contrato_frontend.py` falla para recordarlo.
- `/documentos/{id}/original`: URL a `public/mock-originales/` o, si se subio en la sesion, al propio fichero.

## Pantallas
- Login (`paginas/PaginaLogin.tsx`): usuario y contrasena -> token, rol y `expires_in`; mensajes
  segun el codigo (`utilidades/mensajes.ts`); foco inicial en usuario y, si las credenciales fallan,
  en la contrasena; aviso si la sesion caduco. Vuelve a la pagina que se pidio.
- Sesion: se recupera con `GET /auth/yo` al recargar; un 401 o la caducidad local llevan al login.
- Layout (`componentes/Estructura.tsx`): enlace "Saltar al contenido", navegacion, usuario, rol y
  "Cerrar sesion".
- Roles: `<RutaProtegida roles={[...]}>` para rutas (si no, "Sin permiso") y
  `<SoloRol roles={[...]} alternativa={...}>` para partes de una pantalla. Es solo interfaz: la API
  vuelve a comprobar el rol.

## Tests
```
npm test        # Vitest
```
- Mocks (Node): cobertura del contrato (falla si un endpoint no tiene handler) y flujos.
- Pantallas (jsdom + Testing Library + msw/node, `src/pruebas/app.tsx`): login con los 3 usuarios del
  mock, errores, recuperacion de sesion, caducidad y control de roles.
Si `docs/contratos/endpoints.md` no esta (contenedor que solo monta `frontend/`), la cobertura se omite.

## Tipos y datos de los mocks
- `src/tipos/contrato.ts` refleja `backend/app/schemas/resultado.py` campo a campo (las claves
  siempre estan: los opcionales son `T | null`) y `docs/contratos/endpoints.md`.
- `src/mocks/datos/*.json`: 4 folios ficticios coherentes con `fixtures/generados/INDICE.md`
  (`--hoy 2026-09-30`): alertas de las 4 severidades, `CMP-001` de domicilio, `EXP-001`, una
  correccion, un documento en error (`SYS-001`), uno pendiente y un folio aprobado.
  `MOCK-001` (informativa) solo existe en los mocks; se sustituira por `VAL-003` o `EXP-002` cuando
  esten en el catalogo de main.
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
