import { describe, expect, it } from 'vitest'
import { ACCIONES_AUDITORIA, type EntradaAuditoria } from '../tipos/contrato'
import { describirDetalle, enmascarar, etiquetaAccion } from './auditoria'
import { ETIQUETA_ACCION } from './etiquetas'

const de = (accion: string, detalle: Record<string, unknown>, tipos = {}) =>
  describirDetalle({ accion: accion as EntradaAuditoria['accion'], detalle }, tipos)

describe('detalle de la auditoria legible por accion', () => {
  it('tiene un texto por cada accion de la lista cerrada (ADR-006 1.5)', () => {
    for (const accion of ACCIONES_AUDITORIA) expect(etiquetaAccion(accion)).toBe(ETIQUETA_ACCION[accion])
    expect(new Set(Object.values(ETIQUETA_ACCION)).size).toBe(ACCIONES_AUDITORIA.length)
    expect(etiquetaAccion('accion_nueva')).toBe('accion_nueva') // si la API anade una, se ve su codigo
  })

  it('login, folio creado y documento subido', () => {
    expect(de('login', { resultado: 'ok' })).toEqual(['Acceso correcto'])
    expect(de('login', { resultado: 'fallido' })).toEqual(['Intento fallido'])
    expect(de('folio_creado', {})).toEqual([])
    expect(de('documento_subido', { hash_sha256: '44a92b42e7d1e55944ea5a7d250abbc49fa0c79792cda02f87c77c3eb8c06d6c',
      tamano_bytes: 5950, duplicado: false })).toEqual(['SHA-256 44a92b42e7d1…', '5,8 KB', 'No duplicado'])
    expect(de('documento_subido', { tamano_bytes: 900, duplicado: true })).toEqual(['900 B', 'Duplicado en el folio (DUP-001)'])
    expect(de('documento_subido', { tamano_bytes: 3 * 1024 * 1024 })).toEqual(['3 MB'])
  })

  it('procesado, correccion, clasificacion, alerta, decision y dato revelado', () => {
    expect(de('documento_procesado', { estado_analisis: 'error' })).toEqual(['Resultado: Error'])
    expect(de('dato_corregido', { campo: 'nombre_completo' })).toEqual(['Campo: nombre completo'])
    expect(de('clasificacion_confirmada', { tipo_documental: 'credencial_elector' }, { credencial_elector: 'Credencial de elector' }))
      .toEqual(['Tipo confirmado: Credencial de elector'])
    expect(de('clasificacion_confirmada', { tipo_documental: 'pasaporte' })).toEqual(['Tipo confirmado: pasaporte'])
    expect(de('alerta_resuelta', { codigo: 'DUP-001', aplica: false })).toEqual(['Alerta DUP-001: falso positivo'])
    expect(de('alerta_resuelta', { codigo: 'EXP-001', aplica: true })).toEqual(['Alerta EXP-001: aplica'])
    expect(de('decision_tomada', { decision: 'rechazar' })).toEqual(['Decisión: Rechazado'])
    expect(de('dato_revelado', { campo: 'curp' })).toEqual(['Campo mostrado: curp'])
  })

  it('nunca muestra completos los valores que no son de la forma conocida', () => {
    // Datos inventados: si la API anadiera valores o comentarios, solo se ven los 4 ultimos caracteres
    const frases = de('dato_corregido', { campo: 'curp', valor_anterior: 'AEPA900101MDFXXX01', valor_nuevo: 'AEPA900101MDFXXX02',
      comentario: 'texto libre', otros: { anidado: 'secreto' }, lista: ['a'] })
    expect(frases).toEqual(['Campo: curp', 'valor anterior: ****XX01', 'valor nuevo: ****XX02', 'comentario: ****ibre',
      'otros: (oculto)', 'lista: (oculto)'])
    expect(frases.join(' ')).not.toContain('AEPA900101')
    // clave conocida con un tipo inesperado: tambien enmascarada
    expect(de('dato_corregido', { campo: 12345678 })).toEqual(['campo: ****5678'])
    expect(de('decision_tomada', { decision: 'quizas' })).toEqual(['decision: ****izas'])
    expect(de('login', { resultado: 'ok', ip: '192.0.2.10' })).toEqual(['Acceso correcto', 'ip: ****2.10'])
  })

  it('nunca devuelve JSON en bruto', () => {
    for (const accion of ACCIONES_AUDITORIA) {
      const frases = de(accion, { a: { b: 1 }, c: [1, 2], d: null, e: true })
      expect(frases.join(' ')).not.toMatch(/[{}[\]"]/)
    }
  })

  it('enmascarar', () => {
    expect(enmascarar('1234')).toBe('****')
    expect(enmascarar('ZX0000001')).toBe('****0001')
    expect(enmascarar(null)).toBe('—')
    expect(enmascarar(false)).toBe('no')
    expect(enmascarar({ x: 1 })).toBe('(oculto)')
  })
})
