// Arranque de msw en el navegador. Solo se importa si VITE_USAR_MOCKS=true (ver main.tsx).
import { setupWorker } from 'msw/browser'
import { crearEstado } from './estado'
import { crearHandlers } from './handlers'

export async function iniciarMocks(): Promise<void> {
  const { handlers } = crearHandlers(crearEstado())
  await setupWorker(...handlers).start({
    onUnhandledRequest: 'bypass', // ficheros de Vite, fuentes, etc.
    serviceWorker: { url: '/mockServiceWorker.js' },
  })
  console.info('[mocks] msw activo: usuarios admin.demo, revisor.demo, integrador.demo (ver src/mocks/usuarios.ts)')
}
