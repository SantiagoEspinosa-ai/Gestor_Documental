// Utilidades para los tests de pantallas: servidor msw con estado propio, reloj controlable,
// sesion iniciada con los usuarios del mock y la app montada en una ruta.
import { render } from '@testing-library/react'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter, type InitialEntry } from 'react-router'
import { afterAll, beforeAll, beforeEach } from 'vitest'
import { iniciarSesion } from '../api/auth'
import { borrarSesion } from '../api/sesion'
import { App } from '../App'
import { ProveedorSesion } from '../componentes/ProveedorSesion'
import { crearEstado, type EstadoMock } from '../mocks/estado'
import { crearHandlers } from '../mocks/handlers'
import { USUARIOS_DEMO } from '../mocks/usuarios'

export const INICIO_RELOJ = Date.UTC(2026, 9, 1, 10, 0, 0)

/** Registra el servidor msw del fichero de test; cada test empieza con un estado nuevo */
export function usarServidorMock() {
  const servidor = setupServer()
  // servidor: para sobrescribir un handler en un test (servidor.use); se restablece en cada test
  const contexto = { estado: null as unknown as EstadoMock, t: INICIO_RELOJ, peticiones: [] as string[], consultas: [] as string[], servidor }
  servidor.events.on('request:start', ({ request }) => {
    const url = new URL(request.url)
    contexto.peticiones.push(`${request.method} ${url.pathname.replace(/^\/api\/v1/, '')}`)
    contexto.consultas.push(`${request.method} ${url.pathname.replace(/^\/api\/v1/, '')}${url.search}`)
  })
  beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
  afterAll(() => servidor.close())
  beforeEach(() => {
    contexto.t = INICIO_RELOJ
    contexto.peticiones = []
    contexto.consultas = []
    contexto.estado = crearEstado(() => contexto.t)
    servidor.resetHandlers(...crearHandlers(contexto.estado).handlers)
    borrarSesion()
  })
  return contexto
}

export async function entrarComo(usuario: 'admin.demo' | 'revisor.demo' | 'integrador.demo'): Promise<void> {
  const demo = USUARIOS_DEMO.find((u) => u.usuario === usuario)!
  await iniciarSesion(demo.usuario, demo.contrasena)
}

/** `ruta` puede ser una entrada con estado, p. ej. {pathname: '/login', state: {desde: '...'}} */
export function montar(ruta: InitialEntry, contenido: ReactNode = <App />) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ProveedorSesion>{contenido}</ProveedorSesion>
    </MemoryRouter>,
  )
}

/** Simula recargar la pagina con mocks: msw vuelve a arrancar con un estado nuevo (sin memoria de tokens) */
export function reiniciarMocks(contexto: ReturnType<typeof usarServidorMock>): void {
  contexto.estado = crearEstado(() => contexto.t)
  contexto.servidor.resetHandlers(...crearHandlers(contexto.estado).handlers)
}
