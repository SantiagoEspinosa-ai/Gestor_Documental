import { describe, expect, it } from 'vitest'
import type { FaseAnalisis } from '../tipos/contrato'
import { numeroDePaso, pasosDelAnalisis } from './flujoAnalisis'

const resumen = (fase: FaseAnalisis | null, vistas: FaseAnalisis[] = []) =>
  pasosDelAnalisis(fase, new Set(vistas)).map((p) => `${p.fase}:${p.estado}`)

describe('pasos del analisis (ADR-014)', () => {
  it('sin vision: 5 pasos con el actual y los anteriores hechos', () => {
    expect(resumen('ocr')).toEqual(['en_cola:hecho', 'preparando:hecho', 'ocr:actual', 'clasificando:pendiente', 'extrayendo:pendiente'])
  })

  it('un salto de en_cola a extrayendo no deja pasos vacios', () => {
    expect(resumen('extrayendo', ['en_cola'])).toEqual(
      ['en_cola:hecho', 'preparando:hecho', 'ocr:hecho', 'clasificando:hecho', 'extrayendo:actual'])
  })

  it('la vision aparece como desvio solo si es la fase o ya se vio', () => {
    expect(resumen('vision')).toContain('vision:actual')
    expect(pasosDelAnalisis('vision').find((p) => p.fase === 'vision')!.desvio).toBe(true)
    expect(resumen('extrayendo', ['vision'])).toEqual(
      ['en_cola:hecho', 'preparando:hecho', 'ocr:hecho', 'clasificando:hecho', 'vision:hecho', 'extrayendo:actual'])
    expect(resumen('extrayendo')).not.toContain('vision:hecho')
  })

  it('una fase ya vista sigue hecha aunque la actual vaya antes (reintento con vision)', () => {
    expect(resumen('vision', ['extrayendo'])).toContain('extrayendo:hecho')
  })

  it('sin fase: todo pendiente', () => {
    expect(resumen(null).every((p) => p.endsWith(':pendiente'))).toBe(true)
  })

  it('paso N de 5: la vision cuenta como el 4', () => {
    expect((['en_cola', 'preparando', 'ocr', 'clasificando', 'vision', 'extrayendo'] as const).map(numeroDePaso)).toEqual([1, 2, 3, 4, 4, 5])
  })
})
