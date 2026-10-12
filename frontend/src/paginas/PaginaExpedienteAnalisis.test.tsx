// @vitest-environment jsdom
// Progreso del analisis en el expediente (ADR-014) con los mocks: un documento subido recorre las fases con el
// reloj del mock. Tarjeta: icono de la fase, fase corta y "Paso N de 5"; detalle: el flujo completo; al
// terminar, el semaforo. Datos ficticios.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MS_HASTA_COMPLETADO, MS_HASTA_PROCESANDO } from '../mocks/logica'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { esperarExpediente, montarExpediente, tarjeta } from '../pruebas/expediente'
import { olvidarFasesVistas } from '../utilidades/flujoAnalisis'

const mock = usarServidorMock()
const API = 'http://localhost:8000/api/v1'
const ORIGINALES = join(process.cwd(), 'public', 'mock-originales')
const FOTO = 'credencial_elector_vencido_foto.jpg' // imagen: el mock la "analiza" con vision

beforeEach(() => olvidarFasesVistas())
afterEach(() => vi.unstubAllGlobals())

/** Folio nuevo con una foto subida (pendiente) */
async function folioConFoto(): Promise<{ folio: string; id: string }> {
  await entrarComo('revisor.demo')
  const token = JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!).token as string
  const { folio } = await (await fetch(`${API}/folios`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ proceso: 'onboarding' }),
  })).json()
  const formulario = new FormData()
  formulario.append('archivo', new File([readFileSync(join(ORIGINALES, FOTO))], FOTO))
  const { identificador_unico_documento: id } = await (await fetch(`${API}/folios/${folio}/documentos`,
    { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: formulario })).json()
  return { folio, id }
}

describe('progreso del análisis en el expediente', () => {
  it('tarjeta en OCR: icono de la fase, fase corta y "Paso 3 de 5", sin contador', async () => {
    const { folio, id } = await folioConFoto()
    mock.t += MS_HASTA_PROCESANDO + 2_000 // procesando, fase ocr
    montarExpediente(`/folios/${folio}`)
    await esperarExpediente(folio)
    const carta = tarjeta(FOTO)
    await waitFor(() => expect(within(carta).getByTestId(`semaforo-${id}`).textContent).toBe('Leyendo el texto'))
    expect(within(carta).getByTestId(`icono-semaforo-${id}`).getAttribute('class')).toContain('lucide-scan-text')
    const barra = within(carta).getByRole('progressbar', { name: 'Progreso del análisis' })
    expect(barra.getAttribute('aria-valuenow')).toBe('3')
    expect(within(carta).getByText('Paso 3 de 5')).toBeTruthy()
    expect(within(carta).queryByTestId('fase-transcurrido')).toBeNull()
  })

  it('detalle en vision: flujo completo con el desvio y el contador; al terminar, el semaforo', async () => {
    const { folio, id } = await folioConFoto()
    mock.t += MS_HASTA_PROCESANDO + 4_500 // procesando, fase vision (imagen)
    montarExpediente(`/folios/${folio}?doc=${id}`)
    await esperarExpediente(folio)
    await waitFor(() => expect(screen.getByTestId('paso-vision').getAttribute('data-estado')).toBe('actual'))
    expect(screen.getByTestId('paso-clasificando').getAttribute('data-estado')).toBe('hecho') // los saltados, hechos
    expect(screen.getByTestId('paso-en_cola').getAttribute('data-estado')).toBe('hecho')
    expect(screen.getByTestId('paso-extrayendo').getAttribute('data-estado')).toBe('pendiente')
    expect(within(screen.getByTestId('paso-vision')).getByTestId('fase-transcurrido')).toBeTruthy()
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).not.toBe('en_proceso'))
    expect(screen.queryByTestId('flujo-analisis')).toBeNull()
  })

  it('el semaforo aparece con un fundido, salvo con movimiento reducido', async () => {
    const { folio, id } = await folioConFoto()
    mock.t += MS_HASTA_COMPLETADO + MS_HASTA_PROCESANDO
    montarExpediente(`/folios/${folio}`)
    await esperarExpediente(folio)
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).not.toBe('en_proceso'))
    expect(screen.getByTestId(`semaforo-${id}`).getAttribute('class')).toContain('animate-aparecer')
  })

  it('con movimiento reducido no hay animaciones ni en la tarjeta ni en el semaforo', async () => {
    vi.stubGlobal('matchMedia', (consulta: string) => ({
      matches: consulta.includes('prefers-reduced-motion'), media: consulta, addEventListener: () => {}, removeEventListener: () => {},
    }))
    const { folio, id } = await folioConFoto()
    mock.t += MS_HASTA_PROCESANDO + 2_000
    montarExpediente(`/folios/${folio}`)
    await esperarExpediente(folio)
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).textContent).toBe('Leyendo el texto'))
    expect(tarjeta(FOTO).querySelector('[class*="animate-"]')).toBeNull()
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).not.toBe('en_proceso'))
    expect(screen.getByTestId(`semaforo-${id}`).getAttribute('class')).not.toContain('animate-')
  })
})
