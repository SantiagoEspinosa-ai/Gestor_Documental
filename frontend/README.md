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

## Tipos y datos de los mocks
- `src/tipos/contrato.ts` refleja `backend/app/schemas/resultado.py` campo a campo (las claves
  siempre estan: los opcionales son `T | null`) y `docs/contratos/endpoints.md`.
- `src/mocks/datos/*.json`: 4 folios ficticios coherentes con `fixtures/generados/INDICE.md`
  (`--hoy 2026-09-30`): alertas de las 4 severidades, `CMP-001` de domicilio, `EXP-001`, una
  correccion, un documento en error (`SYS-001`), uno pendiente y un folio aprobado.
  `MOCK-001` (informativa) solo existe en los mocks: el catalogo no tiene codigos informativos.
- `public/mock-originales/`: copias de los fixtures que usan los mocks (mismo SHA-256).
- `backend/tests/test_contrato_frontend.py` comprueba todo lo anterior contra los contratos,
  `config/` y el generador de fixtures:
  `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_contrato_frontend.py`.

## Sesion
Token, rol e instante de caducidad (`Date.now() + expires_in * 1000`) en `sessionStorage`, con
respaldo en memoria si el navegador lo bloquea. Al recargar se recupera con `GET /auth/yo`; al
caducar se cierra sola aunque no haya peticiones.
