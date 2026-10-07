// @vitest-environment jsdom
// Login, recuperacion de sesion, cabecera y cierre de sesion con los 3 usuarios del mock.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AVISO_SESION_CADUCADA } from '../componentes/ProveedorSesion'
import { USUARIOS_DEMO } from '../mocks/usuarios'
import { App } from '../App'
import { entrarComo, montar, reiniciarMocks, usarServidorMock } from '../pruebas/app'
import { Ubicacion } from '../pruebas/Ubicacion'
import { ETIQUETA_ROL } from '../utilidades/etiquetas'

const mock = usarServidorMock()

async function escribirCredenciales(usuario: string, contrasena: string) {
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Usuario'), usuario)
  await u.type(screen.getByLabelText('Contraseña'), contrasena)
  return u
}

describe('login', () => {
  it.each(USUARIOS_DEMO)('entra como $usuario, ve su rol en la cabecera y cierra sesión', async ({ usuario, contrasena, rol }) => {
    montar('/folios')
    expect(await screen.findByRole('heading', { name: 'Gestor Documental' })).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByLabelText('Usuario')) // foco inicial
    const u = await escribirCredenciales(usuario, contrasena)
    await u.keyboard('{Enter}') // se envia con el teclado
    const cabecera = await screen.findByTestId('usuario-actual')
    expect(within(cabecera).getByText(usuario)).toBeTruthy()
    expect(within(cabecera).getByText(ETIQUETA_ROL[rol])).toBeTruthy()
    const sesion = JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!)
    expect(sesion.rol).toBe(rol)
    expect(sesion.expira_en).toBeGreaterThan(Date.now() + 3500 * 1000) // expires_in = 3600 s

    await u.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    expect(await screen.findByLabelText('Usuario')).toBeTruthy()
    expect(sessionStorage.getItem('gestor_documental.sesion')).toBeNull()
  })

  it('credenciales incorrectas: mensaje del código, contraseña vacía y foco en ella', async () => {
    montar('/login')
    const u = await escribirCredenciales('revisor.demo', 'no-es-esta')
    await u.click(screen.getByRole('button', { name: /Entrar/ }))
    expect((await screen.findByRole('alert')).textContent).toBe('Usuario o contraseña incorrectos.')
    const campo = screen.getByLabelText('Contraseña') as HTMLInputElement
    expect(campo.value).toBe('')
    expect(document.activeElement).toBe(campo)
    expect(campo.getAttribute('aria-invalid')).toBe('true')
    expect(campo.getAttribute('aria-describedby')).toBe('error-login')
  })

  it('sin servidor: mensaje de SIN_CONEXION', async () => {
    montar('/login')
    const u = await escribirCredenciales('revisor.demo', 'demo-revisor')
    const original = globalThis.fetch
    globalThis.fetch = () => Promise.reject(new TypeError('Failed to fetch'))
    try {
      await u.click(screen.getByRole('button', { name: /Entrar/ }))
      expect((await screen.findByRole('alert')).textContent).toBe('No se pudo conectar con el servidor.')
    } finally {
      globalThis.fetch = original
    }
  })

  it('el botón se habilita solo con usuario y contraseña, y la contraseña se puede mostrar', async () => {
    montar('/login')
    const entrar = screen.getByRole('button', { name: /Entrar/ }) as HTMLButtonElement
    expect(entrar.disabled).toBe(true)
    const u = await escribirCredenciales('admin.demo', 'x')
    expect(entrar.disabled).toBe(false)
    await u.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect((screen.getByLabelText('Contraseña') as HTMLInputElement).type).toBe('text')
  })
})

describe('sesión', () => {
  it('se recupera al recargar con GET /auth/yo', async () => {
    await entrarComo('integrador.demo')
    montar('/folios')
    const cabecera = await screen.findByTestId('usuario-actual')
    expect(within(cabecera).getByText('integrador.demo')).toBeTruthy()
    expect(mock.peticiones).toContain('GET /auth/yo')
  })

  it('un 401 (token caducado en el servidor) lleva al login con aviso', async () => {
    await entrarComo('revisor.demo')
    mock.t += 3601 * 1000 // el servidor ya lo da por caducado
    montar('/folios')
    // Primero se ve "Recuperando la sesión…"; tras el 401 de /auth/yo, el login con el aviso
    expect((await screen.findByText(AVISO_SESION_CADUCADA)).getAttribute('role')).toBe('status')
    expect(screen.getByLabelText('Usuario')).toBeTruthy()
    expect(sessionStorage.getItem('gestor_documental.sesion')).toBeNull()
  })

  it('tras cerrar sesión, el siguiente usuario no vuelve a la página del anterior', async () => {
    const pedida = '/auditoria?folio=ONB-2026-000004'
    await entrarComo('admin.demo')
    montar(pedida, <><App /><Ubicacion /></>)
    expect(await screen.findByRole('heading', { name: 'Auditoría' })).toBeTruthy()
    const u = userEvent.setup()
    await u.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByLabelText('Usuario')
    expect(screen.getByTestId('ubicacion').textContent).toBe('/login')

    await escribirCredenciales('integrador.demo', 'demo-integrador')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByTestId('ubicacion').textContent).toBe('/folios'))
    expect(await screen.findByRole('heading', { name: 'Folios' })).toBeTruthy()
    expect(screen.queryByText(/Sin permiso/i)).toBeNull()
  })

  it('tras una sesión caducada (401) sí vuelve a la página que se estaba viendo', async () => {
    const pedida = '/auditoria?folio=ONB-2026-000004'
    await entrarComo('admin.demo')
    mock.t += 3601 * 1000 // el servidor ya da el token por caducado
    montar(pedida, <><App /><Ubicacion /></>)
    expect(await screen.findByText(AVISO_SESION_CADUCADA)).toBeTruthy()
    const u = await escribirCredenciales('admin.demo', 'demo-admin')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByTestId('ubicacion').textContent).toBe(pedida))
  })

  it('tras entrar vuelve a la página que se pidió', async () => {
    montar('/folios/ONB-2026-000001')
    const u = await escribirCredenciales('revisor.demo', 'demo-revisor')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('ONB-2026-000001'))
  })

  it('tras entrar vuelve a la ruta completa: parámetros y hash', async () => {
    const pedida = '/auditoria?folio=ONB-2026-000004&tamano_pagina=20#tabla'
    montar(pedida, <><App /><Ubicacion /></>)
    await screen.findByLabelText('Usuario')
    expect(screen.getByTestId('ubicacion').textContent).toBe('/login')
    const u = await escribirCredenciales('admin.demo', 'demo-admin')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByTestId('ubicacion').textContent).toBe(pedida))
    expect(await screen.findByText('Página 1 de 1 (9 entradas)')).toBeTruthy() // el filtro y el tamano se aplican
    expect((screen.getByLabelText('Entradas por página') as HTMLSelectElement).value).toBe('20')
  })

  it.each([
    'https://otro.example/folios',
    '//otro.example/folios',
    '/\\otro.example',
    '/\t/otro.example',
    'javascript:alert(1)',
  ])('rechaza volver a %s: va a /folios', async (desde) => {
    montar({ pathname: '/login', state: { desde } }, <><App /><Ubicacion /></>)
    const u = await escribirCredenciales('revisor.demo', 'demo-revisor')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByTestId('ubicacion').textContent).toBe('/folios'))
    expect(await screen.findByRole('heading', { name: 'Folios' })).toBeTruthy()
  })

  it('con mocks, la sesión sobrevive a una recarga: el token no depende de la memoria de msw', async () => {
    await entrarComo('admin.demo')
    reiniciarMocks(mock) // como recargar la pagina: msw arranca de cero con los datos iniciales
    montar('/auditoria')
    const cabecera = await screen.findByTestId('usuario-actual')
    expect(within(cabecera).getByText('admin.demo')).toBeTruthy()
    expect(await screen.findByRole('heading', { name: 'Auditoría' })).toBeTruthy()
    expect(screen.queryByLabelText('Usuario')).toBeNull() // no se ha ido al login
  })
})
