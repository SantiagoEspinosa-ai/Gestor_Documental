// @vitest-environment jsdom
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { PaginaCarga } from './PaginaCarga'
import { PaginaFolios } from './PaginaFolios'

const mock = usarServidorMock()

function Rutas({ tamano = 20 }: { tamano?: number }) {
  return (
    <Routes>
      <Route path="/folios" element={<PaginaFolios tamanoPagina={tamano} />} />
      <Route path="/folios/:folio/carga" element={<PaginaCarga tiemposSondeo={{ inicialMs: 30, maximoMs: 30 }} />} />
    </Routes>
  )
}

const filas = () => screen.getAllByRole('row').slice(1) // sin la cabecera
const celdas = (fila: HTMLElement) => within(fila).getAllByRole('cell').map((c) => c.textContent)

describe('pantalla de folios', () => {
  it('lista los folios del más reciente al más antiguo con todas las columnas', async () => {
    await entrarComo('revisor.demo')
    montar('/folios', <Rutas />)
    await screen.findByRole('rowheader', { name: 'ONB-2026-000003' })
    expect(filas().map((f) => within(f).getByRole('rowheader').textContent))
      .toEqual(['ONB-2026-000003', 'ONB-2026-000002', 'ONB-2026-000001', 'ONB-2026-000004'])
    const cabeceras = screen.getAllByRole('columnheader').map((c) => c.textContent)
    expect(cabeceras).not.toContain('Referencia externa') // vuelve con el ADR-008
    const f1 = filas()[2]
    expect(celdas(f1).slice(0, 5)).toEqual(['onboarding', '28/09/2026, 09:15', 'En revisión', 'Revisión manual', '4'])
    expect(within(f1).getByText('1 alerta bloqueante sin resolver')).toBeTruthy()
    expect(celdas(filas()[3])[2]).toBe('Aprobado')
    expect(screen.getByText('Página 1 de 1 (4 folios)')).toBeTruthy()
    // Una sola peticion de lista: ya no se pide GET /folios/{folio} por fila
    expect(mock.peticiones.filter((p) => p.startsWith('GET /folios/'))).toEqual([])
  })

  it('filtra por estado_general y por proceso', async () => {
    await entrarComo('admin.demo')
    montar('/folios', <Rutas />)
    await screen.findByRole('rowheader', { name: 'ONB-2026-000003' })
    const u = userEvent.setup()
    await u.selectOptions(screen.getByLabelText('Estado'), 'aprobado')
    await waitFor(() => expect(filas().map((f) => within(f).getByRole('rowheader').textContent)).toEqual(['ONB-2026-000004']))
    expect(mock.peticiones).toContain('GET /folios')
    await u.selectOptions(screen.getByLabelText('Estado'), 'rechazado')
    expect(await screen.findByText('No hay folios con esos filtros.')).toBeTruthy()
    await u.selectOptions(screen.getByLabelText('Estado'), '')
    await u.selectOptions(screen.getByLabelText('Proceso'), 'onboarding')
    await waitFor(() => expect(filas()).toHaveLength(4))
  })

  it('pagina con Anterior y Siguiente', async () => {
    await entrarComo('revisor.demo')
    montar('/folios', <Rutas tamano={2} />)
    await screen.findByText('Página 1 de 2 (4 folios)')
    const u = userEvent.setup()
    const siguiente = screen.getByRole('button', { name: /Siguiente/ })
    await u.click(siguiente)
    await screen.findByText('Página 2 de 2 (4 folios)')
    await waitFor(() => expect(filas().map((f) => within(f).getByRole('rowheader').textContent)).toEqual(['ONB-2026-000001', 'ONB-2026-000004']))
    expect((siguiente as HTMLButtonElement).disabled).toBe(true)
    await u.click(screen.getByRole('button', { name: /Anterior/ }))
    await screen.findByText('Página 1 de 2 (4 folios)')
  })

  it('"Nuevo folio" crea el folio con proceso y referencia y lleva a su carga', async () => {
    await entrarComo('revisor.demo')
    montar('/folios', <Rutas />)
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: 'Nuevo folio' }))
    const proceso = screen.getByLabelText('Proceso', { selector: '#nuevo-proceso' })
    expect(document.activeElement).toBe(proceso)
    await u.selectOptions(proceso, 'onboarding')
    await u.type(screen.getByLabelText('Referencia externa (opcional)'), 'CLI-000900')
    await u.click(screen.getByRole('button', { name: 'Crear folio' }))
    expect(await screen.findByRole('heading', { name: /Carga de documentos — ONB-2026-000005/ })).toBeTruthy()
    expect(screen.getByText(/Referencia CLI-000900/)).toBeTruthy()
    expect(mock.estado.folios.get('ONB-2026-000005')?.referencia_externa).toBe('CLI-000900')
  })

  it('el integrador no ve la lista (no tiene GET /folios) pero crea y abre folios; el admin no crea', async () => {
    await entrarComo('integrador.demo')
    const { unmount } = montar('/folios', <Rutas />)
    expect(await screen.findByText(/Tu rol no puede ver la lista de folios/)).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getByRole('button', { name: 'Nuevo folio' })).toBeTruthy()
    const u = userEvent.setup()
    await u.type(screen.getByLabelText('Número de folio'), 'onb-2026-000003')
    await u.click(screen.getByRole('button', { name: 'Abrir' }))
    expect(await screen.findByRole('heading', { name: /ONB-2026-000003/ })).toBeTruthy()
    expect(mock.peticiones).not.toContain('GET /folios')
    unmount()

    await entrarComo('admin.demo')
    montar('/folios', <Rutas />)
    await screen.findByRole('rowheader', { name: 'ONB-2026-000003' })
    expect(screen.queryByRole('button', { name: 'Nuevo folio' })).toBeNull()
  })
})
