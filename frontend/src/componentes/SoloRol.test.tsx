// @vitest-environment jsdom
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { RutaProtegida } from './RutaProtegida'
import { SoloRol } from './SoloRol'

usarServidorMock()

function Pantalla() {
  return (
    <Routes>
      <Route path="/" element={
        <div>
          <p>Siempre</p>
          <SoloRol roles={['revisor']}><p>Solo revisión</p></SoloRol>
          <SoloRol roles={['admin', 'integrador']} alternativa={<p>No disponible</p>}><p>Admin o integración</p></SoloRol>
        </div>} />
      <Route element={<RutaProtegida roles={['admin']} />}>
        <Route path="/auditoria" element={<p>Auditoría</p>} />
      </Route>
      <Route path="/login" element={<p>Login</p>} />
    </Routes>
  )
}

describe('SoloRol y RutaProtegida con roles', () => {
  it.each([
    ['revisor.demo', ['Solo revisión', 'No disponible'], ['Admin o integración']],
    ['admin.demo', ['Admin o integración'], ['Solo revisión', 'No disponible']],
    ['integrador.demo', ['Admin o integración'], ['Solo revisión']],
  ] as const)('%s ve lo que le corresponde', async (usuario, visibles, ocultos) => {
    await entrarComo(usuario)
    montar('/', <Pantalla />)
    expect(await screen.findByText('Siempre')).toBeTruthy()
    // SoloRol se pinta cuando ya se conoce el rol (GET /auth/yo)
    for (const texto of visibles) expect(await screen.findByText(texto)).toBeTruthy()
    for (const texto of ocultos) expect(screen.queryByText(texto)).toBeNull()
  })

  it('sin sesión, SoloRol no muestra nada', async () => {
    montar('/', <Pantalla />)
    expect(await screen.findByText('Siempre')).toBeTruthy()
    expect(screen.queryByText('Solo revisión')).toBeNull()
  })

  it('RutaProtegida con roles: el revisor ve "Sin permiso" y el admin entra', async () => {
    await entrarComo('revisor.demo')
    const { unmount } = montar('/auditoria', <Pantalla />)
    expect(await screen.findByRole('heading', { name: /Sin permiso/ })).toBeTruthy()
    unmount()
    await entrarComo('admin.demo')
    montar('/auditoria', <Pantalla />)
    expect(await screen.findByText('Auditoría')).toBeTruthy()
  })
})
