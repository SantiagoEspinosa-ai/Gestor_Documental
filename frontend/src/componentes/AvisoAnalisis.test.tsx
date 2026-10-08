// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AvisoAnalisis } from './AvisoAnalisis'

beforeEach(() => vi.useFakeTimers())
afterEach(() => { cleanup(); vi.useRealTimers() })

describe('AvisoAnalisis (ADR-014)', () => {
  it('dice la fase en una region que el lector de pantalla anuncia, con el contador oculto para el', () => {
    render(<AvisoAnalisis fase="ocr" documento="doc-1" />)
    const aviso = screen.getByRole('status')
    expect(aviso.getAttribute('aria-live')).toBe('polite')
    expect(screen.getByTestId('fase-analisis').textContent).toBe('Leyendo el texto (OCR)')
    const contador = screen.getByTestId('fase-transcurrido')
    expect(contador.getAttribute('aria-hidden')).toBe('true')
    expect(contador.textContent).toBe('· lleva 0 s')
  })

  it('cuenta en el cliente desde que ve la fase y vuelve a cero al cambiar de fase', () => {
    const { rerender } = render(<AvisoAnalisis fase="vision" documento="doc-1" />)
    act(() => { vi.advanceTimersByTime(80_000) })
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 1 min 20 s')
    expect(screen.getByTestId('fase-analisis').textContent).toBe('La foto es difícil: leyéndola como imagen, tardará 2-3 min')
    rerender(<AvisoAnalisis fase="extrayendo" documento="doc-1" />)
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 0 s')
    act(() => { vi.advanceTimersByTime(5_000) })
    expect(screen.getByTestId('fase-transcurrido').textContent).toBe('· lleva 5 s')
  })

  it('el mismo texto de la fase en otro documento tambien empieza de cero', () => {
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
