// @vitest-environment jsdom
// "Ver resumen" del expediente (bloque I). Datos ficticios del mock.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { MENSAJES_ERROR } from '../utilidades/mensajes'
import { PaginaExpediente } from './PaginaExpediente'

const mock = usarServidorMock()

async function abrir(folio: string) {
  await entrarComo('revisor.demo')
  montar(`/folios/${folio}`, <Routes><Route path="/folios/:folio" element={<PaginaExpediente intervaloSondeoMs={30} />} /></Routes>)
  await screen.findByRole('heading', { name: new RegExp(`Expediente ${folio}`) })
  return userEvent.setup()
}

describe('resumen del expediente', () => {
  it('folio aprobado con resumen: "Ver resumen" lo muestra renderizado desde Markdown', async () => {
    const u = await abrir('ONB-2026-000004')
    await u.click(screen.getByRole('button', { name: 'Ver resumen' }))
    const resumen = await screen.findByRole('region', { name: 'Resumen del expediente' })
    expect(await within(resumen).findByRole('heading', { level: 1, name: /Expediente ONB-2026-000004/ })).toBeTruthy()
    expect(within(resumen).getByRole('heading', { level: 2, name: 'Documentos' })).toBeTruthy()
    expect(within(resumen).getAllByRole('listitem').length).toBeGreaterThan(3)
    await u.click(within(resumen).getByRole('button', { name: 'Cerrar resumen' }))
    expect(screen.queryByRole('region', { name: 'Resumen del expediente' })).toBeNull()
  })

  it('sin ruta_resumen_md no hay boton', async () => {
    await abrir('ONB-2026-000001')
    expect(screen.queryByRole('button', { name: 'Ver resumen' })).toBeNull()
  })

  it('404 RESUMEN_NO_DISPONIBLE con un mensaje claro', async () => {
    const u = await abrir('ONB-2026-000004')
    mock.estado.folios.get('ONB-2026-000004')!.ruta_resumen_md = null // deja de existir tras cargar la vista
    await u.click(screen.getByRole('button', { name: 'Ver resumen' }))
    const resumen = screen.getByRole('region', { name: 'Resumen del expediente' })
    expect((await within(resumen).findByRole('alert')).textContent).toBe(MENSAJES_ERROR.RESUMEN_NO_DISPONIBLE)
  })

  it('no renderiza HTML crudo del Markdown', async () => {
    mock.estado.folios.get('ONB-2026-000004')!.referencia_externa = '<img src="x" onerror="alert(1)"><script>alert(2)</script>CLI-X'
    const u = await abrir('ONB-2026-000004')
    await u.click(screen.getByRole('button', { name: 'Ver resumen' }))
    const resumen = await screen.findByRole('region', { name: 'Resumen del expediente' })
    await within(resumen).findByRole('heading', { level: 1 })
    expect(resumen.querySelector('img, script')).toBeNull()
    expect(within(resumen).getByText(/Referencia:/).textContent).toContain('CLI-X')
  })
})
