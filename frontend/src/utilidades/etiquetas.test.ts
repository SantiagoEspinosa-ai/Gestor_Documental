import { describe, expect, it } from 'vitest'
import { FASES_ANALISIS } from '../tipos/contrato'
import { ETIQUETA_FASE, ETIQUETA_FASE_CORTA, textoTranscurrido } from './etiquetas'

describe('fase del analisis (ADR-014)', () => {
  it('frases exactas de cada fase', () => {
    expect(ETIQUETA_FASE).toEqual({
      en_cola: 'En espera: se analiza un documento cada vez',
      preparando: 'Preparando el documento',
      ocr: 'Leyendo el texto (OCR)',
      clasificando: 'Identificando el tipo de documento',
      vision: 'La foto es difícil: la estamos leyendo como imagen, puede tardar unos minutos',
      extrayendo: 'Extrayendo los datos',
    })
  })

  it('todas las fases del contrato tienen frase larga y corta', () => {
    for (const fase of FASES_ANALISIS) {
      expect(ETIQUETA_FASE[fase]).toBeTruthy()
      expect(ETIQUETA_FASE_CORTA[fase]).toBeTruthy()
      expect(ETIQUETA_FASE_CORTA[fase].length).toBeLessThan(ETIQUETA_FASE[fase].length + 1)
    }
  })

  it('tiempo transcurrido', () => {
    expect(textoTranscurrido(0)).toBe('lleva 0 s')
    expect(textoTranscurrido(45)).toBe('lleva 45 s')
    expect(textoTranscurrido(60)).toBe('lleva 1 min')
    expect(textoTranscurrido(80)).toBe('lleva 1 min 20 s')
    expect(textoTranscurrido(125.9)).toBe('lleva 2 min 5 s')
    expect(textoTranscurrido(-3)).toBe('lleva 0 s')
  })
})
