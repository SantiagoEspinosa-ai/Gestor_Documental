import { describe, expect, it } from 'vitest'
import {
  formatearValor, MOTIVO_ANIO, MOTIVO_OBLIGATORIO, nombreCampo, porcentaje, prepararCorreccion, sinValor, TEXTO_NO_DETECTADO,
} from './valores'

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

  it('correccion de un campo opcional: vacio -> null, nunca ""', () => {
    expect(prepararCorreccion('   ', { tipo: 'texto', obligatorio: false })).toEqual({ valida: true, valor: null })
    expect(prepararCorreccion('', { tipo: 'fecha' })).toEqual({ valida: true, valor: null }) // sin ficha: opcional
    expect(prepararCorreccion(' ANA ', { tipo: 'texto' })).toEqual({ valida: true, valor: 'ANA' })
  })

  it('correccion de un campo obligatorio: no se puede dejar vacio', () => {
    for (const vacio of ['', '   ', '\t']) {
      expect(prepararCorreccion(vacio, { tipo: 'texto', obligatorio: true })).toEqual({ valida: false, motivo: MOTIVO_OBLIGATORIO })
    }
    expect(prepararCorreccion('ANA EJEMPLO PRUEBA', { tipo: 'texto', obligatorio: true }))
      .toEqual({ valida: true, valor: 'ANA EJEMPLO PRUEBA' })
  })

  it('anio: entero de 4 cifras; otro formato no se puede enviar', () => {
    expect(prepararCorreccion('2029', { tipo: 'anio', obligatorio: true })).toEqual({ valida: true, valor: 2029 })
    expect(prepararCorreccion(' 2030 ', { tipo: 'anio' })).toEqual({ valida: true, valor: 2030 })
    for (const malo of ['29', '20299', '0999', '2029.5', '20a9', '-202', '2 029']) {
      expect(prepararCorreccion(malo, { tipo: 'anio', obligatorio: true })).toEqual({ valida: false, motivo: MOTIVO_ANIO })
    }
    // vacio en un anio: manda la regla de obligatorio
    expect(prepararCorreccion('', { tipo: 'anio', obligatorio: true })).toEqual({ valida: false, motivo: MOTIVO_OBLIGATORIO })
    expect(prepararCorreccion('', { tipo: 'anio', obligatorio: false })).toEqual({ valida: true, valor: null })
  })

  it('nombre del campo y porcentaje', () => {
    expect(nombreCampo('fecha_nacimiento')).toBe('Fecha nacimiento')
    expect(porcentaje(0.856)).toBe('86 %')
  })
})
