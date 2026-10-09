// @vitest-environment jsdom
// Retirar y restaurar un documento (ADR-013) en el expediente: solo el revisor con el folio abierto; motivo
// obligatorio y confirmacion; el retirado sale al final de la rejilla, marcado y sin acciones de revision. Datos ficticios.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { abrirDocumento, esperarExpediente, montarExpediente, rejilla, tarjeta, volverALaLista } from '../pruebas/expediente'

const mock = usarServidorMock()

async function abrir(folio: string, usuario: 'revisor.demo' | 'admin.demo' | 'integrador.demo' = 'revisor.demo') {
  await entrarComo(usuario)
  montarExpediente(`/folios/${folio}`)
  await esperarExpediente(folio)
  return userEvent.setup()
}
const alertasExpediente = () => screen.getByRole('region', { name: 'Alertas del expediente' })
const COMPROBANTE = 'comprobante_domicilio_domicilio_distinto_foto.jpg'
const DUPLICADO = '00000000-0000-4000-8000-000001000004' // el duplicado retirado de los datos del folio 1
const retiradoDeLosDatos = () => within(rejilla()).getByTestId(`tarjeta-${DUPLICADO}`)

describe('retirar y restaurar documentos', () => {
  it('revisor: motivo obligatorio, confirmación, el documento queda marcado y EXP-001 aparece; restaurar lo deshace', async () => {
    const u = await abrir('ONB-2026-000002')
    expect(within(alertasExpediente()).queryByText('EXP-001')).toBeNull()
    await abrirDocumento(u, COMPROBANTE)
    await u.click(screen.getByText('Retirar este documento del expediente')) // plegado (details)
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
    // Sin acciones de revision sobre el retirado
    expect(screen.queryByRole('button', { name: /^Corregir |^Escribir el valor/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Cambiar tipo|Confirmar clasificación/ })).toBeNull()

    await volverALaLista(u)
    const carta = tarjeta(COMPROBANTE)
    expect(within(carta).getByTestId(/^semaforo-/).textContent).toBe('Retirado')
    expect(within(rejilla()).getAllByRole('article').at(-1)).toBe(carta) // al final de la rejilla
    expect(within(alertasExpediente()).getByText('EXP-001')).toBeTruthy()

    // Restaurar desde la tarjeta
    await u.click(within(carta).getByRole('button', { name: `Restaurar ${COMPROBANTE}` }))
    await waitFor(() => expect(screen.getByTestId('aviso').textContent).toBe('Documento restaurado.'))
    expect(within(tarjeta(COMPROBANTE)).getByTestId(/^semaforo-/).textContent).not.toBe('Retirado')
    expect(within(alertasExpediente()).queryByText('EXP-001')).toBeNull()
  })

  it('revisor: también se restaura desde el detalle del documento', async () => {
    const u = await abrir('ONB-2026-000001')
    await u.click(within(retiradoDeLosDatos()).getByRole('link', { name: /^Abrir y revisar/ }))
    const marca = await screen.findByRole('region', { name: 'Documento retirado' })
    await u.click(within(marca).getByRole('button', { name: 'Restaurar' }))
    await waitFor(() => expect(screen.getByTestId('aviso').textContent).toBe('Documento restaurado.'))
    expect(screen.queryByRole('region', { name: 'Documento retirado' })).toBeNull()
  })

  it('el admin ve el retirado pero no los botones (solo el revisor retira y restaura)', async () => {
    const u = await abrir('ONB-2026-000001', 'admin.demo')
    expect(within(retiradoDeLosDatos()).getByTestId(/^semaforo-/).textContent).toBe('Retirado')
    expect(within(retiradoDeLosDatos()).queryByRole('button', { name: /Restaurar/ })).toBeNull()
    await u.click(within(retiradoDeLosDatos()).getByRole('link', { name: /^Abrir / }))
    expect((await screen.findByRole('region', { name: 'Documento retirado' })).textContent).toContain('Subido dos veces por error')
    expect(screen.queryByRole('button', { name: 'Restaurar' })).toBeNull()
    expect(screen.queryByText('Retirar este documento del expediente')).toBeNull()
  })

  it('el integrador ve el retirado pero no los botones', async () => {
    const u = await abrir('ONB-2026-000001', 'integrador.demo')
    expect(within(retiradoDeLosDatos()).queryByRole('button', { name: /Restaurar/ })).toBeNull()
    await u.click(within(retiradoDeLosDatos()).getByRole('link', { name: /^Abrir / }))
    expect((await screen.findByRole('region', { name: 'Documento retirado' })).textContent).toContain('Subido dos veces por error')
    expect(screen.queryByRole('button', { name: 'Restaurar' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retirar' })).toBeNull()
  })

  it('con el folio cerrado no hay botón Retirar', async () => {
    const u = await abrir('ONB-2026-000004')
    await abrirDocumento(u, 'pasaporte_sano_digital.pdf')
    expect(screen.queryByText('Retirar este documento del expediente')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retirar' })).toBeNull()
  })
})
