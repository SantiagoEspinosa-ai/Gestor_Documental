// Configuracion leida de las variables VITE_* (ver frontend/.env.example)
const urlApi = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

export const entorno = {
  /** Base de la API del Contrato 2: `${VITE_API_URL}/api/v1` */
  apiBase: `${urlApi}/api/v1`,
  /** true = msw intercepta la API (src/mocks/navegador.ts). Nunca en un build de produccion */
  usarMocks: import.meta.env.DEV && import.meta.env.VITE_USAR_MOCKS === 'true',
}
