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
    expect(de('login', { resultado: 'bloqueado' })).toEqual(['Acceso bloqueado'])
    expect(de('folio_creado', {})).toEqual([])
    expect(de('documento_subido', { hash_sha256: '44a92b42e7d1e55944ea5a7d250abbc49fa0c79792cda02f87c77c3eb8c06d6c',
      tamano_bytes: 5950, duplicado: false })).toEqual(['SHA-256 44a92b42e7d1…', '5,8 KB', 'No duplicado'])
    expect(de('documento_subido', { tamano_bytes: 900, duplicado: true })).toEqual(['900 B', 'Duplicado en el folio (DUP-001)'])
    expect(de('documento_subido', { tamano_bytes: 3 * 1024 * 1024 })).toEqual(['3 MB'])
  })

  it('documento_procesado con la forma del PR #9: proveedor, respaldo, tiempos y tokens; nunca la confianza del modelo', () => {
    expect(de('documento_procesado', { proveedor: 'ollama', respaldo_usado: false })).toEqual(['Proveedor: ollama', 'Sin respaldo'])
    expect(de('documento_procesado', { proveedor: 'openrouter', respaldo_usado: true })).toEqual(['Proveedor: openrouter', 'Con el proveedor de respaldo'])
    expect(de('documento_procesado', {
      proveedor: 'ollama', respaldo_usado: false, confianzas_modelo: { nombre_completo: 0.95 },
      tiempos: { ocr: 1.5, modelo: 108.25 }, tokens: { entrada: 1200, salida: 85 },
    })).toEqual(['Proveedor: ollama', 'Sin respaldo', 'Tiempo: ocr 1,5 s · modelo 108,25 s', 'Tokens: entrada 1200 · salida 85']) // es-ES no agrupa 4 cifras
    expect(de('documento_procesado', { tiempos: 12.5, tokens: 40 })).toEqual(['Tiempo: 12,5 s', 'Tokens: 40'])
    // tiempos o tokens con otra forma: enmascarados
    expect(de('documento_procesado', { tiempos: 'lento', tokens: { entrada: 'x' } })).toEqual(['tiempos: ****ento', 'tokens: (oculto)'])
  })

  it('documento_procesado con la forma del motor real (H10): todo legible, nada enmascarado por error', () => {
    const frases = de('documento_procesado', {
      proveedor: 'ollama', version_prompt_clasificacion: 'clasificacion@v2', respaldo_usado: false,
      confianzas_modelo: { nombre_completo: 0.95 }, tiempos: { segundos_modelo: 37.5 }, tokens: { entrada: 1200, salida: 150 },
      llamadas: [{ proveedor: 'ollama', modelo: 'gemma4:e2b', entrada: 'texto', motivo: null, segundos: 37.5 }],
      modalidad: 'pdf_digital', paginas: 1,
    })
    expect(frases).toEqual(['Proveedor: ollama', 'Sin respaldo', 'Tiempo: segundos modelo 37,5 s',
      'Tokens: entrada 1200 · salida 150', 'Modalidad: pdf digital', 'Páginas: 1',
      'Prompt de clasificación: clasificacion@v2', 'Llamadas al modelo: 1'])
    expect(frases.join(' ')).not.toContain('****')
  })

  it('correccion, clasificacion, alerta, decision y dato revelado con la forma del PR #9', () => {
    expect(de('dato_corregido', { campos: ['nombre_completo'] })).toEqual(['Campo: nombre completo'])
    expect(de('dato_corregido', { campos: ['nacionalidad', 'sexo'] })).toEqual(['Campos: nacionalidad, sexo'])
    expect(de('clasificacion_confirmada', { tipo: 'credencial_elector', reproceso: true }, { credencial_elector: 'Credencial de elector' }))
      .toEqual(['Tipo confirmado: Credencial de elector', 'Se vuelve a analizar'])
    expect(de('clasificacion_confirmada', { tipo: 'pasaporte', reproceso: false })).toEqual(['Tipo confirmado: pasaporte', 'Sin volver a analizar'])
    expect(de('alerta_resuelta', { alerta_id: 'alr-000012', codigo: 'DUP-001', aplica: false })).toEqual(['Alerta DUP-001: falso positivo'])
    expect(de('alerta_resuelta', { alerta_id: '7', codigo: 'EXP-001', aplica: true })).toEqual(['Alerta EXP-001: aplica'])
    expect(de('decision_tomada', { decision: 'rechazar' })).toEqual(['Decisión: Rechazado'])
    expect(de('dato_revelado', { campo: 'curp' })).toEqual(['Campo: curp'])
    expect(de('dato_revelado', { campo: 'clave_elector' })).toEqual(['Campo: clave elector'])
    expect(de('dato_revelado', { campo: 'curp', motivo: 'Lo pide el cliente: ****' })).toEqual(['Campo: curp', 'Motivo: “Lo pide el cliente: ****”'])
    expect(etiquetaAccion('dato_revelado')).toBe('Dato revelado')
    expect(de('documento_retirado', { motivo: 'Subido por error ****' })).toEqual(['Motivo: “Subido por error ****”'])
    expect(de('documento_restaurado', {})).toEqual([])
    expect(etiquetaAccion('documento_retirado')).toBe('Documento retirado')
  })

  it('nunca muestra completos los valores que no son de la forma conocida', () => {
    // Datos inventados: si la API anadiera valores o comentarios, solo se ven los 4 ultimos caracteres
    const frases = de('dato_corregido', { campos: ['curp'], valor_anterior: 'AEPA900101MDFXXX01', valor_nuevo: 'AEPA900101MDFXXX02',
      comentario: 'texto libre', otros: { anidado: 'secreto' }, lista: ['a'] })
    expect(frases).toEqual(['Campo: curp', 'valor anterior: ****XX01', 'valor nuevo: ****XX02', 'comentario: ****ibre',
      'otros: (oculto)', 'lista: (oculto)'])
    expect(frases.join(' ')).not.toContain('AEPA900101')
    // clave conocida con un tipo o una forma inesperada: tambien enmascarada
    expect(de('dato_corregido', { campos: 12345678 })).toEqual(['campos: ****5678'])
    expect(de('dato_corregido', { campos: ['AEPA900101MDFXXX01'] })).toEqual(['campos: (oculto)']) // un valor, no un nombre de campo
    expect(de('clasificacion_confirmada', { tipo: 'Ana Ejemplo' })).toEqual(['tipo: ****mplo'])
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
