// @vitest-environment jsdom
// Pestana Resumen del expediente: cifras, "Lo que tienes que hacer" y el resumen en Markdown (bloque I).
// Datos ficticios del mock.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { esperarExpediente, montarExpediente } from '../pruebas/expediente'
import { MENSAJES_ERROR } from '../utilidades/mensajes'

const mock = usarServidorMock()

async function abrir(folio: string, ruta = `/folios/${folio}?pestana=resumen`) {
  await entrarComo('revisor.demo')
  montarExpediente(ruta)
  await esperarExpediente(folio)
  return userEvent.setup()
}
const resumen = () => screen.findByRole('region', { name: 'Resumen del expediente' })

describe('resumen del expediente', () => {
  it('"Ver resumen" de la cabecera abre la pestaña Resumen con el Markdown renderizado', async () => {
    const u = await abrir('ONB-2026-000004', '/folios/ONB-2026-000004')
    await u.click(screen.getByRole('link', { name: 'Ver resumen' }))
    const seccion = await resumen()
    expect(screen.getByRole('link', { name: 'Resumen' }).getAttribute('aria-current')).toBe('page')
    expect(await within(seccion).findByRole('heading', { level: 1, name: /Expediente ONB-2026-000004/ })).toBeTruthy()
    expect(within(seccion).getByRole('heading', { level: 2, name: 'Documentos' })).toBeTruthy()
    expect(within(seccion).getAllByRole('listitem').length).toBeGreaterThan(3)
    expect(within(seccion).queryByRole('button', { name: 'Cerrar resumen' })).toBeNull() // es una pestana
  })

  it('sin ruta_resumen_md no se pide y se dice', async () => {
    await abrir('ONB-2026-000001')
    expect(screen.getByText('Todavía no hay resumen en texto de este folio.')).toBeTruthy()
    expect(mock.peticiones.some((p) => p.endsWith('/resumen.md'))).toBe(false)
  })

  it('404 RESUMEN_NO_DISPONIBLE con un mensaje claro', async () => {
    const original = mock.estado.folios.get('ONB-2026-000004')!
    const u = await abrir('ONB-2026-000004', '/folios/ONB-2026-000004')
    original.ruta_resumen_md = null // deja de existir tras cargar la vista
    await u.click(screen.getByRole('link', { name: 'Ver resumen' }))
    expect((await within(await resumen()).findByRole('alert')).textContent).toBe(MENSAJES_ERROR.RESUMEN_NO_DISPONIBLE)
  })

  it('no renderiza HTML crudo del Markdown', async () => {
    mock.estado.folios.get('ONB-2026-000004')!.referencia_externa = '<img src="x" onerror="alert(1)"><script>alert(2)</script>CLI-X'
    await abrir('ONB-2026-000004')
    const seccion = await resumen()
    await within(seccion).findByRole('heading', { level: 1 })
    expect(seccion.querySelector('img, script')).toBeNull()
    expect(within(seccion).getByText(/Referencia:/).textContent).toContain('CLI-X')
  })

  it('tres cifras: documentos por color, comparaciones y la recomendación de la IA', async () => {
    await abrir('ONB-2026-000003')
    const cifras = screen.getByRole('region', { name: 'Cifras del expediente' })
    // Credencial verde; pasaporte y comprobante en error (rojo); el no reconocido, amarillo
    expect(within(cifras).getByTestId('cifra-colores').textContent).toBe('1 en verde · 1 en amarillo · 2 en rojo')
    expect(cifras.textContent).toContain('0 de 0')
    expect(cifras.textContent).toContain('Recomendación de la IA')
  })

  it('"Lo que tienes que hacer": amarillos, rojos, avisos sin revisar y comparaciones que no coinciden, con su enlace', async () => {
    await abrir('ONB-2026-000002')
    const tareas = screen.getByRole('region', { name: 'Lo que tienes que hacer' })
    const elementos = within(tareas).getAllByRole('listitem').map((li) => li.textContent!)
    expect(elementos.some((t) => t.startsWith('Expediente: revisa el aviso CMP-001'))).toBe(true)
    expect(elementos.some((t) => t.startsWith('Domicilio: no coincide entre Credencial de elector y Comprobante de domicilio'))).toBe(true)
    const irAlDocumento = within(tareas).getAllByRole('link', { name: /Ir al documento/ })[0]
    expect(irAlDocumento.getAttribute('href')).toMatch(/^\/folios\/ONB-2026-000002\?doc=/)
    expect(within(tareas).getByRole('link', { name: /Ir a los avisos del expediente/ }).getAttribute('href'))
      .toBe('/folios/ONB-2026-000002#alertas-expediente')
  })

  it('sin nada pendiente lo dice', async () => {
    await abrir('ONB-2026-000004')
    expect(within(screen.getByRole('region', { name: 'Lo que tienes que hacer' })).getByText('No queda nada pendiente.')).toBeTruthy()
  })
})
