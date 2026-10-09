// @vitest-environment jsdom
// Antecedentes del folio en el expediente (H16, ADR-010 C), contra los mocks.
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { montarExpediente } from '../pruebas/expediente'

const mock = usarServidorMock()

/** Los antecedentes estan en la pestana Resumen */
function abrir(folio: string) {
  montarExpediente(`/folios/${folio}?pestana=resumen`)
}

describe('antecedentes en el expediente', () => {
  it.each(['revisor.demo', 'admin.demo'] as const)('%s ve el antecedente con enlace, estado, decisión y fragmento', async (usuario) => {
    await entrarComo(usuario)
    abrir('ONB-2026-000002')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    const elemento = await within(seccion).findByRole('listitem', { name: 'Antecedente ONB-2026-000004' })
    const enlace = within(elemento).getByRole('link', { name: 'ONB-2026-000004' })
    expect(enlace.getAttribute('href')).toBe('/folios/ONB-2026-000004')
    expect(elemento.textContent).toContain('Aprobado')
    expect(elemento.textContent).toContain('Decisión: Aprobado')
    // El fragmento se pinta como Markdown seguro: el titulo, no el "#" crudo
    expect(within(elemento).getByRole('heading', { name: /Expediente ONB-2026-000004/ })).toBeTruthy()
    expect(elemento.textContent).not.toContain('# Expediente')
    expect(mock.peticiones).toContain('GET /folios/ONB-2026-000002/antecedentes')
  })

  it('el integrador no ve la sección ni la pide', async () => {
    await entrarComo('integrador.demo')
    abrir('ONB-2026-000002')
    await screen.findByRole('region', { name: 'Lo que tienes que hacer' })
    expect(screen.queryByRole('region', { name: 'Antecedentes' })).toBeNull()
    expect(mock.peticiones.filter((p) => p.endsWith('/antecedentes'))).toEqual([])
  })

  it('folio sin referencia: el motivo legible', async () => {
    await entrarComo('revisor.demo')
    abrir('ONB-2026-000003')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    expect(await within(seccion).findByText(/no tiene referencia externa/)).toBeTruthy()
    expect(within(seccion).queryByRole('listitem', { name: /^Antecedente / })).toBeNull()
  })

  it('proceso sin antecedentes: el motivo legible', async () => {
    mock.estado.procesos.find((p) => p.nombre === 'onboarding')!.permitir_antecedentes = false
    await entrarComo('revisor.demo')
    abrir('ONB-2026-000002')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    expect(await within(seccion).findByText('El proceso de este folio no consulta antecedentes.')).toBeTruthy()
  })

  it('sin antecedentes', async () => {
    await entrarComo('revisor.demo')
    abrir('ONB-2026-000001')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    expect(await within(seccion).findByText(/Sin antecedentes/)).toBeTruthy()
  })

  it('antecedente sin fragmento en la memoria', async () => {
    mock.servidor.use(http.get('*/api/v1/folios/:folio/antecedentes', () => HttpResponse.json({
      permitido: true, motivo: null,
      elementos: [{ folio: 'ONB-2026-000004', fecha_solicitud: null, estado_general: 'rechazado', decision_humana: 'rechazar',
        fecha_decision: '2026-09-26T12:30:00Z', fragmento_resumen: null }],
    })))
    await entrarComo('revisor.demo')
    abrir('ONB-2026-000002')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    expect(await within(seccion).findByText('Sin resumen en la memoria de folios.')).toBeTruthy()
    expect(within(seccion).getByRole('listitem', { name: 'Antecedente ONB-2026-000004' }).textContent).toContain('Decisión: Rechazado')
  })

  it('error al cargar', async () => {
    mock.servidor.use(http.get('*/api/v1/folios/:folio/antecedentes',
      () => HttpResponse.json({ codigo: 'ERROR_INTERNO', mensaje: 'x' }, { status: 500 })))
    await entrarComo('revisor.demo')
    abrir('ONB-2026-000002')
    const seccion = await screen.findByRole('region', { name: 'Antecedentes' })
    expect((await within(seccion).findByRole('alert')).textContent).toMatch(/No se pudieron cargar los antecedentes/)
  })
})
