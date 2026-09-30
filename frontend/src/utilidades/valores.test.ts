import { describe, expect, it } from 'vitest'
import { formatearValor, nombreCampo, porcentaje, sinValor, TEXTO_NO_DETECTADO } from './valores'

describe('formato de valores', () => {
  it('null, "" y solo espacios se muestran como "no detectado"', () => {
    for (const v of [null, undefined, '', '   ']) {
      expect(sinValor(v)).toBe(true)
      expect(formatearValor(v, 'texto')).toBe(TEXTO_NO_DETECTADO)
    }
    expect(sinValor(0)).toBe(false)
  })

  it('segun el tipo del campo: fecha ISO -> DD/MM/AAAA; anio y texto tal cual', () => {
    expect(formatearValor('1990-01-31', 'fecha')).toBe('31/01/1990')
    expect(formatearValor('no es fecha', 'fecha')).toBe('no es fecha')
    expect(formatearValor(2029, 'anio')).toBe('2029')
    expect(formatearValor('1990-01-31', 'texto')).toBe('1990-01-31')
  })

  it('nombre del campo y porcentaje', () => {
    expect(nombreCampo('fecha_nacimiento')).toBe('Fecha nacimiento')
    expect(porcentaje(0.856)).toBe('86 %')
  })
})
