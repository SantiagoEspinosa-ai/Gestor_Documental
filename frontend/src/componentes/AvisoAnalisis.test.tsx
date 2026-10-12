// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FaseAnalisis } from '../tipos/contrato'
import { olvidarFasesVistas } from '../utilidades/flujoAnalisis'
import { AvisoAnalisis } from './AvisoAnalisis'

/** jsdom no trae matchMedia: se simula "prefers-reduced-motion" */
function simularMovimientoReducido(reducido: boolean) {
  vi.stubGlobal('matchMedia', (consulta: string) => ({
    matches: reducido && consulta.includes('prefers-reduced-motion'), media: consulta,
    addEventListener: () => {}, removeEventListener: () => {},
  }))
}

beforeEach(() => { vi.useFakeTimers(); olvidarFasesVistas(); simularMovimientoReducido(false) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })

const estado = (fase: FaseAnalisis) => screen.queryByTestId(`paso-${fase}`)?.getAttribute('data-estado') ?? 'no sale'
const estados = () => (['en_cola', 'preparando', 'ocr', 'clasificando', 'vision', 'extrayendo'] as const).map(estado)

describe('AvisoAnalisis (ADR-014): flujo de pasos', () => {
  it.each([
    ['en_cola', ['actual', 'pendiente', 'pendiente', 'pendiente', 'no sale', 'pendiente']],
    ['preparando', ['hecho', 'actual', 'pendiente', 'pendiente', 'no sale', 'pendiente']],
    ['ocr', ['hecho', 'hecho', 'actual', 'pendiente', 'no sale', 'pendiente']],
    ['clasificando', ['hecho', 'hecho', 'hecho', 'actual', 'no sale', 'pendiente']],
    ['vision', ['hecho', 'hecho', 'hecho', 'hecho', 'actual', 'pendiente']],
    ['extrayendo', ['hecho', 'hecho', 'hecho', 'hecho', 'no sale', 'actual']],
  ] as const)('%s: hechos, actual y pendientes', (fase, esperado) => {
    render(<AvisoAnalisis fase={fase} documento={`doc-${fase}`} />)
    expect(estados()).toEqual(esperado)
    expect(screen.getByTestId(`paso-${fase}`).getAttribute('aria-current')).toBe('step')
  })

  it('el paso actual en negrita y con icono animado; los hechos con check; siempre con texto', () => {
    render(<AvisoAnalisis fase="ocr" documento="doc-1" />)
    const actual = screen.getByTestId('paso-ocr')
    expect(actual.querySelector('.font-semibold')!.textContent).toBe('Leyendo el texto · OCR')
    expect(screen.getByTestId('icono-ocr').getAttribute('class')).toContain('animate-pulse')
    expect(screen.getByTestId('paso-en_cola').querySelector('svg')!.getAttribute('class')).toContain('lucide-check')
    expect(screen.getByTestId('paso-en_cola').textContent).toContain('En espera')
    expect(screen.getByTestId('paso-extrayendo').textContent).toContain('Extrayendo los datos')
  })

  it('en espera explica que se analiza un documento cada vez', () => {
    render(<AvisoAnalisis fase="en_cola" documento="doc-1" />)
    expect(screen.getByTestId('paso-en_cola').textContent).toContain('Se analiza un documento cada vez')
  })

  it('un salto de en_cola a extrayendo marca los intermedios como hechos', () => {
    const { rerender } = render(<AvisoAnalisis fase="en_cola" documento="doc-1" />)
    rerender(<AvisoAnalisis fase="extrayendo" documento="doc-1" />)
    expect(estados()).toEqual(['hecho', 'hecho', 'hecho', 'hecho', 'no sale', 'actual'])
  })

  it('la vision solo sale si es la fase o ya paso por ella, como desvio con su icono', () => {
    const { rerender } = render(<AvisoAnalisis fase="clasificando" documento="doc-1" />)
    expect(screen.queryByTestId('paso-vision')).toBeNull()
    rerender(<AvisoAnalisis fase="vision" documento="doc-1" />)
    expect(screen.getByTestId('paso-vision').textContent).toContain('La foto es difícil: pasamos a leerla como imagen')
    expect(screen.getByTestId('icono-vision').getAttribute('class')).toContain('lucide-eye')
    rerender(<AvisoAnalisis fase="extrayendo" documento="doc-1" />)
    expect(estado('vision')).toBe('hecho') // ya paso por ella: sigue a la vista, como hecha
    // Otro documento que no pasa por vision no la ve
    rerender(<AvisoAnalisis fase="extrayendo" documento="doc-2" />)
    expect(screen.queryByTestId('paso-vision')).toBeNull()
  })

  it('un reintento con vision despues de extrayendo no vuelve a poner extrayendo en gris', () => {
    const { rerender } = render(<AvisoAnalisis fase="extrayendo" documento="doc-1" />)
    rerender(<AvisoAnalisis fase="vision" documento="doc-1" />)
    expect(estado('extrayendo')).toBe('hecho')
    expect(estado('vision')).toBe('actual')
  })

  it('con prefers-reduced-motion no hay clase de animacion (solo cambia el icono)', () => {
    simularMovimientoReducido(true)
    render(<AvisoAnalisis fase="ocr" documento="doc-1" />)
    expect(screen.getByTestId('flujo-analisis').querySelector('[class*="animate-"]')).toBeNull()
    expect(screen.getByTestId('icono-ocr').getAttribute('class')).toContain('lucide-scan-text')
  })

  it('aria-live solo cambia al cambiar la fase, no con cada sondeo ni con el contador', () => {
    const { rerender } = render(<AvisoAnalisis fase="ocr" documento="doc-1" />)
    const vivo = screen.getByTestId('fase-anunciada')
    expect(vivo.getAttribute('aria-live')).toBe('polite')
    expect(vivo.textContent).toBe('Leyendo el texto · OCR')
    const observador = new MutationObserver(() => {})
    observador.observe(vivo, { childList: true, characterData: true, subtree: true })
    rerender(<AvisoAnalisis fase="ocr" documento="doc-1" />) // otro sondeo con la misma fase
    act(() => { vi.advanceTimersByTime(5_000) }) // el contador avanza
    expect(observador.takeRecords()).toHaveLength(0) // nada que anunciar
    rerender(<AvisoAnalisis fase="clasificando" documento="doc-1" />)
    expect(observador.takeRecords().length).toBeGreaterThan(0)
    observador.disconnect()
    expect(vivo.textContent).toBe('Identificando el tipo de documento')
    // Solo hay una region viva: el contador queda fuera del lector de pantalla
    expect(screen.getByTestId('fase-transcurrido').getAttribute('aria-hidden')).toBe('true')
  })
})

describe('AvisoAnalisis (ADR-014): contador', () => {
  it('cuenta en el cliente desde que ve la fase y vuelve a cero al cambiar de fase', () => {
    const { rerender } = render(<AvisoAnalisis fase="vision" documento="doc-1" />)
    act(() => { vi.advanceTimersByTime(80_000) })
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 1 min 20 s')
    rerender(<AvisoAnalisis fase="extrayendo" documento="doc-1" />)
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 0 s')
    act(() => { vi.advanceTimersByTime(5_000) })
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 5 s')
  })

  it('la misma fase en otro documento tambien empieza de cero', () => {
    const { rerender } = render(<AvisoAnalisis fase="ocr" documento="doc-1" />)
    act(() => { vi.advanceTimersByTime(30_000) })
    rerender(<AvisoAnalisis fase="ocr" documento="doc-2" />)
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 0 s')
  })

  it('sin fase, el texto de siempre y sin contador', () => {
    render(<AvisoAnalisis fase={null} documento="doc-1" />)
    expect(screen.getByRole('status').textContent).toBe('El documento se está analizando; la vista se actualiza sola.')
    expect(screen.queryByTestId('fase-transcurrido')).toBeNull()
  })
})
