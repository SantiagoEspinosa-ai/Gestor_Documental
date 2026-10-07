// @vitest-environment jsdom
// Retirar y restaurar un documento (ADR-013) en el expediente: revisor y admin con el folio abierto; motivo
// obligatorio y confirmacion; el retirado sale atenuado, marcado y sin acciones de revision. Datos ficticios.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { PaginaExpediente } from './PaginaExpediente'

const mock = usarServidorMock()

async function abrir(folio: string, usuario: 'revisor.demo' | 'admin.demo' | 'integrador.demo' = 'revisor.demo') {
  await entrarComo(usuario)
  montar(`/folios/${folio}`, <Routes><Route path="/folios/:folio" element={<PaginaExpediente tiemposSondeo={{ inicialMs: 30, maximoMs: 30 }} />} /></Routes>)
  await screen.findByRole('heading', { name: new RegExp(`Expediente ${folio}`) })
  return userEvent.setup()
}
const documentos = () => screen.getByRole('navigation', { name: 'Documentos del folio' })
const alertasExpediente = () => screen.getByRole('region', { name: 'Alertas del expediente' })

describe('retirar y restaurar documentos', () => {
  it('revisor: motivo obligatorio, confirmación, el documento queda atenuado y EXP-001 aparece; restaurar lo deshace', async () => {
    const u = await abrir('ONB-2026-000002')
    await u.click(within(documentos()).getByRole('button', { name: /comprobante/i }))
    expect(within(alertasExpediente()).queryByText('EXP-001')).toBeNull()
    await u.click(screen.getByRole('button', { name: 'Retirar' }))
    const retirar = screen.getByRole('button', { name: 'Retirar documento' }) as HTMLButtonElement
    expect(retirar.disabled).toBe(true) // sin motivo no se puede
    await u.type(screen.getByLabelText(/Motivo de la retirada/), 'ab')
    expect(retirar.disabled).toBe(true)
    await u.type(screen.getByLabelText(/Motivo de la retirada/), 'c: es de otra persona')
    await u.click(retirar)
    const dialogo = screen.getByRole('alertdialog', { name: 'Confirmar la retirada' })
    expect(mock.peticiones.filter((p) => p.endsWith('/retirar'))).toEqual([]) // aun no se ha enviado
    await u.click(within(dialogo).getByRole('button', { name: 'Sí, retirar' }))
    await waitFor(() => expect(screen.getByTestId('aviso').textContent).toBe('Documento retirado del folio.'))
    const marca = screen.getByRole('region', { name: 'Documento retirado' })
    expect(marca.textContent).toContain('Motivo: “abc: es de otra persona”')
    expect(within(documentos()).getByText('Retirado')).toBeTruthy()
    expect(within(alertasExpediente()).getByText('EXP-001')).toBeTruthy()
    // Sin acciones de revision sobre el retirado
    expect(screen.queryByRole('button', { name: /^Corregir / })).toBeNull()
    expect(screen.queryByRole('button', { name: /Confirmar clasificación/ })).toBeNull()

    await u.click(within(marca).getByRole('button', { name: 'Restaurar' }))
    await waitFor(() => expect(screen.getByTestId('aviso').textContent).toBe('Documento restaurado.'))
    expect(within(documentos()).queryByText('Retirado')).toBeNull()
    expect(within(alertasExpediente()).queryByText('EXP-001')).toBeNull()
    expect(screen.getByRole('button', { name: 'Retirar' })).toBeTruthy()
  })

  it('admin también puede retirar', async () => {
    await abrir('ONB-2026-000001', 'admin.demo')
    expect(within(documentos()).getByText('Retirado')).toBeTruthy() // el duplicado retirado de los datos
    expect(screen.getByRole('button', { name: 'Retirar' })).toBeTruthy()
  })

  it('el integrador ve el retirado pero no los botones', async () => {
    const u = await abrir('ONB-2026-000001', 'integrador.demo')
    const retirado = within(documentos()).getByText('Retirado').closest('button')!
    await u.click(retirado)
    expect(screen.getByRole('region', { name: 'Documento retirado' }).textContent).toContain('Subido dos veces por error')
    expect(screen.queryByRole('button', { name: 'Restaurar' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retirar' })).toBeNull()
  })

  it('con el folio cerrado no hay botón Retirar', async () => {
    await abrir('ONB-2026-000004')
    expect(screen.queryByRole('button', { name: 'Retirar' })).toBeNull()
  })
})
