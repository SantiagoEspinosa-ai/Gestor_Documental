import { describe, expect, it } from 'vitest'
import { TIPOS_DOCUMENTALES } from '../mocks/datos'
import { TIPO_DESCONOCIDO, type Alerta, type ResultadoDocumento, type ResultadoExpediente } from '../tipos/contrato'
import {
  enumerar, faseExpediente, hayBloqueantesConfirmadas, pendientesDeRevisar, semaforoDocumento, tareasDelRevisor, tiposComparados,
} from './semaforo'

// Credencial de elector ficticia: clave_elector es opcional; el resto, obligatorios
const COMPLETOS = {
  nombre_completo: 'ANA EJEMPLO PRUEBA', curp: '****0101', clave_elector: 'EJPRAN90', fecha_nacimiento: '1990-01-01',
  domicilio: 'CALLE FICTICIA 1', vigencia: 2029,
}
let n = 0
function doc(cambios: Partial<ResultadoDocumento> = {}): ResultadoDocumento {
  n += 1
  return {
    identificador_unico_documento: `doc-${n}`, estado_analisis: 'completado', fase_analisis: null, retirado: null,
    tipo_documental_declarado: 'credencial_elector', tipo_documental_detectado: 'credencial_elector', tipo_documental_confirmado: null,
    datos_extraidos: { ...COMPLETOS }, alertas_encontradas: [], correcciones: [],
    referencia_archivo_original: { nombre_archivo: `f${n}.pdf` },
    ...cambios,
  } as ResultadoDocumento
}
const alerta = (cambios: Partial<Alerta> = {}): Alerta => ({
  id: `a-${++n}`, codigo: 'VAL-002', mensaje: 'Confianza baja', severidad: 'preventiva', confianza: 1, campo: null,
  resuelta_por_revisor: false, aplica: null, comentario_revisor: null, resuelta_por: null, resuelta_en: null, ...cambios,
})
const semaforo = (d: ResultadoDocumento) => semaforoDocumento(d, TIPOS_DOCUMENTALES)

describe('semaforo del documento', () => {
  it('verde: completado y todos los obligatorios con valor', () => {
    expect(semaforo(doc())).toMatchObject({ color: 'verde', etiqueta: 'Todo detectado' })
  })

  it('verde aunque falte un opcional (no cambia el color, como VAL-001)', () => {
    expect(semaforo(doc({ datos_extraidos: { ...COMPLETOS, clave_elector: null } })).color).toBe('verde')
  })

  it('amarillo: falta algun obligatorio; dice cuales', () => {
    const s = semaforo(doc({ datos_extraidos: { ...COMPLETOS, vigencia: null } }))
    expect(s).toMatchObject({ color: 'amarillo', etiqueta: 'Falta un dato' })
    expect(s.explicacion).toContain('Vigencia')
    expect(semaforo(doc({ datos_extraidos: { ...COMPLETOS, vigencia: null, curp: '  ' } })).etiqueta).toBe('Faltan 2 datos')
  })

  it('rojo: error del analisis, o completado con todos los campos sin valor', () => {
    expect(semaforo(doc({ estado_analisis: 'error', datos_extraidos: {} }))).toMatchObject({ color: 'rojo', etiqueta: 'No se pudo leer' })
    const vacios = Object.fromEntries(Object.keys(COMPLETOS).map((c) => [c, null]))
    expect(semaforo(doc({ datos_extraidos: vacios }))).toMatchObject({ color: 'rojo', etiqueta: 'No se pudo leer' })
  })

  it('en proceso: gris con la fase corta (ADR-014), o "Analizando" sin fase', () => {
    expect(semaforo(doc({ estado_analisis: 'procesando', fase_analisis: 'ocr' }))).toMatchObject({ color: 'en_proceso', etiqueta: 'Leyendo el texto' })
    expect(semaforo(doc({ estado_analisis: 'pendiente', fase_analisis: null })).etiqueta).toBe('Analizando')
  })

  it('retirado (ADR-013): gris "Retirado" aunque este analizado', () => {
    expect(semaforo(doc({ retirado: { en: '2026-10-01T10:00:00Z', por: 'revisor.demo', motivo: '****' } })))
      .toMatchObject({ color: 'retirado', etiqueta: 'Retirado' })
  })

  it('desconocido sin ficha ni datos (ADR-009): amarillo "Tipo no reconocido", no rojo', () => {
    const d = doc({ tipo_documental_declarado: null, tipo_documental_detectado: TIPO_DESCONOCIDO, datos_extraidos: {} })
    expect(semaforo(d)).toMatchObject({ color: 'amarillo', etiqueta: 'Tipo no reconocido: confirma el tipo' })
  })
})

// Orden validado por PERSONA_1: gana la primera regla que se cumple. EXP-001 se usa como en su caso: una
// bloqueante entre las alertas del documento (el codigo no importa al semaforo, solo severidad y aplica)
describe('semaforo: una regla cada vez (revision de PERSONA_1)', () => {
  const RETIRADO = { en: '2026-10-01T10:00:00Z', por: 'revisor.demo', motivo: '****' }
  const SIN_FICHA = { tipo_documental_declarado: null, tipo_documental_detectado: TIPO_DESCONOCIDO }
  const bloqueante = (aplica: boolean | null) => alerta({ codigo: 'EXP-001', severidad: 'bloqueante', aplica })
  const aviso = (aplica: boolean | null) => alerta({ codigo: 'VAL-002', severidad: 'preventiva', aplica })
  const vacios = () => Object.fromEntries(Object.keys(COMPLETOS).map((c) => [c, null]))

  it('R1 retirado: gris aunque tenga avisos', () => {
    expect(semaforo(doc({ retirado: RETIRADO, alertas_encontradas: [aviso(null), bloqueante(null)] })))
      .toMatchObject({ color: 'retirado', etiqueta: 'Retirado' })
  })

  it('R2 en proceso: gris con la fase', () => {
    expect(semaforo(doc({ estado_analisis: 'procesando', fase_analisis: 'extrayendo', alertas_encontradas: [aviso(null)] })))
      .toMatchObject({ color: 'en_proceso', etiqueta: 'Extrayendo los datos' })
  })

  it('R3 error: rojo; completado con todo vacio: rojo', () => {
    expect(semaforo(doc({ estado_analisis: 'error', datos_extraidos: {} }))).toMatchObject({ color: 'rojo', etiqueta: 'No se pudo leer' })
    expect(semaforo(doc({ datos_extraidos: vacios() }))).toMatchObject({ color: 'rojo', etiqueta: 'No se pudo leer' })
  })

  it('R4 INE con todos los datos y EXP-001 bloqueante confirmada: rojo "Solo se puede rechazar"', () => {
    expect(semaforo(doc({ alertas_encontradas: [bloqueante(true)] }))).toMatchObject({ color: 'rojo', etiqueta: 'Solo se puede rechazar' })
  })

  it('R5 sin ficha, con datos o sin ellos: amarillo "Tipo no reconocido: confirma el tipo"', () => {
    expect(semaforo(doc({ ...SIN_FICHA, datos_extraidos: { nombre_completo: 'ANA EJEMPLO PRUEBA' } })))
      .toMatchObject({ color: 'amarillo', etiqueta: 'Tipo no reconocido: confirma el tipo' })
    expect(semaforo(doc({ ...SIN_FICHA, datos_extraidos: {} })))
      .toMatchObject({ color: 'amarillo', etiqueta: 'Tipo no reconocido: confirma el tipo' })
    // Con avisos de la regla 6, detras
    expect(semaforo(doc({ ...SIN_FICHA, datos_extraidos: {}, alertas_encontradas: [aviso(null)] })).etiqueta)
      .toBe('Tipo no reconocido: confirma el tipo · 1 aviso por revisar')
  })

  it('R6a INE con todos los datos y EXP-001 bloqueante sin revisar: amarillo "1 aviso impide aprobar"', () => {
    expect(semaforo(doc({ alertas_encontradas: [bloqueante(null)] }))).toMatchObject({ color: 'amarillo', etiqueta: '1 aviso impide aprobar' })
    expect(semaforo(doc({ alertas_encontradas: [bloqueante(null), bloqueante(null)] })).etiqueta).toBe('2 avisos impiden aprobar')
  })

  it('R6b aviso no bloqueante sin revisar: amarillo "1 aviso por revisar"', () => {
    expect(semaforo(doc({ alertas_encontradas: [aviso(null)] }))).toMatchObject({ color: 'amarillo', etiqueta: '1 aviso por revisar' })
    expect(semaforo(doc({ alertas_encontradas: [aviso(null), alerta({ severidad: 'critica' })] })).etiqueta).toBe('2 avisos por revisar')
  })

  it('R6c falta un obligatorio: amarillo "Falta un dato"; falta solo un opcional: verde', () => {
    expect(semaforo(doc({ datos_extraidos: { ...COMPLETOS, curp: null } }))).toMatchObject({ color: 'amarillo', etiqueta: 'Falta un dato' })
    expect(semaforo(doc({ datos_extraidos: { ...COMPLETOS, clave_elector: null } })).color).toBe('verde')
  })

  it('R6d aviso no bloqueante confirmado: amarillo "Aviso confirmado · no impide aprobar", sin pendientes', () => {
    const d = doc({ alertas_encontradas: [aviso(true)] })
    expect(semaforo(d)).toMatchObject({ color: 'amarillo', etiqueta: 'Aviso confirmado · no impide aprobar', pendiente: false })
    expect(pendientesDeRevisar({ documentos: [d], alertas_expediente: [] })).toEqual([])
    const expediente = { documentos: [d], alertas_expediente: [], comparaciones: [] } as unknown as ResultadoExpediente
    expect(tareasDelRevisor(expediente, TIPOS_DOCUMENTALES)).toEqual([])
  })

  it('R7 verde: datos completos sin avisos; con EXP-001 como falso aviso; con una informativa sin revisar', () => {
    expect(semaforo(doc()).color).toBe('verde')
    expect(semaforo(doc({ alertas_encontradas: [bloqueante(false)] })).color).toBe('verde')
    expect(semaforo(doc({ alertas_encontradas: [alerta({ severidad: 'informativa', aplica: null })] })).color).toBe('verde')
  })

  it('cruce: sin ficha + bloqueante confirmada -> rojo (gana R4)', () => {
    expect(semaforo(doc({ ...SIN_FICHA, datos_extraidos: {}, alertas_encontradas: [bloqueante(true)] })))
      .toMatchObject({ color: 'rojo', etiqueta: 'Solo se puede rechazar' })
  })

  it('cruce: error + avisos sin revisar -> rojo "No se pudo leer" (gana R3)', () => {
    expect(semaforo(doc({ estado_analisis: 'error', datos_extraidos: {}, alertas_encontradas: [aviso(null), bloqueante(null)] })))
      .toMatchObject({ color: 'rojo', etiqueta: 'No se pudo leer' })
  })

  it('cruce: retirado + bloqueante confirmada -> gris (gana R1)', () => {
    expect(semaforo(doc({ retirado: RETIRADO, alertas_encontradas: [bloqueante(true)] })).color).toBe('retirado')
  })

  it('texto combinado, en orden: bloqueante sin revisar + aviso sin revisar + falta un dato', () => {
    const d = doc({ datos_extraidos: { ...COMPLETOS, vigencia: null }, alertas_encontradas: [aviso(null), bloqueante(null)] })
    expect(semaforo(d)).toMatchObject({ color: 'amarillo', etiqueta: '1 aviso impide aprobar · 1 aviso por revisar · Falta un dato' })
    // Y con un aviso confirmado, al final
    const e = doc({ datos_extraidos: { ...COMPLETOS, vigencia: null }, alertas_encontradas: [aviso(true), bloqueante(null)] })
    expect(semaforo(e).etiqueta).toBe('1 aviso impide aprobar · Falta un dato · Aviso confirmado · no impide aprobar')
  })
})

describe('fase del expediente', () => {
  const exp = (estado: ResultadoExpediente['estado_general'], documentos: ResultadoDocumento[]) => ({ estado_general: estado, documentos })

  it('carga: sin documentos (o solo retirados)', () => {
    expect(faseExpediente(exp('en_revision', []))).toBe('carga')
    expect(faseExpediente(exp('en_revision', [doc({ retirado: { en: 'x', por: 'y', motivo: 'z' } })]))).toBe('carga')
  })
  it('analisis: alguno pendiente o procesando', () => {
    expect(faseExpediente(exp('en_revision', [doc(), doc({ estado_analisis: 'pendiente' })]))).toBe('analisis')
  })
  it('revision: en revision y nada en proceso', () => {
    expect(faseExpediente(exp('en_revision', [doc(), doc({ estado_analisis: 'error' })]))).toBe('revision')
  })
  it('decision: aprobado o rechazado', () => {
    expect(faseExpediente(exp('aprobado', [doc()]))).toBe('decision')
    expect(faseExpediente(exp('rechazado', []))).toBe('decision')
  })
})

describe('lo que queda por revisar', () => {
  it('solo alertas sin revisar y no informativas, sin las de documentos retirados', () => {
    const sinRevisar = alerta()
    const expediente = {
      alertas_expediente: [alerta({ codigo: 'EXP-001', severidad: 'bloqueante' }), alerta({ aplica: false })],
      documentos: [
        doc({ alertas_encontradas: [sinRevisar, alerta({ severidad: 'informativa' }), alerta({ aplica: true })] }),
        doc({ retirado: { en: 'x', por: 'y', motivo: 'z' }, alertas_encontradas: [alerta()] }),
      ],
    }
    expect(pendientesDeRevisar(expediente).map((a) => a.codigo)).toEqual(['EXP-001', 'VAL-002'])
    expect(hayBloqueantesConfirmadas(expediente)).toBe(false)
    expediente.alertas_expediente[0].aplica = true
    expect(hayBloqueantesConfirmadas(expediente)).toBe(true)
  })

  it('tareas: documentos en amarillo o rojo, avisos sin revisar y comparaciones que no coinciden, con su documento', () => {
    const amarillo = doc({ datos_extraidos: { ...COMPLETOS, vigencia: null }, alertas_encontradas: [alerta()] })
    const verde = doc({ tipo_documental_detectado: 'comprobante_domicilio', tipo_documental_declarado: 'comprobante_domicilio',
      datos_extraidos: { nombre_titular: 'X', domicilio: 'Y', proveedor: 'Z', fecha_emision: '2026-09-15' } })
    const expediente = {
      documentos: [amarillo, verde], alertas_expediente: [alerta({ codigo: 'CMP-001', severidad: 'critica' })],
      comparaciones: [
        { campo: 'domicilio', coincide: false, valores: { [amarillo.identificador_unico_documento]: 'A', [verde.identificador_unico_documento]: 'B' } },
        { campo: 'nombre_completo', coincide: true, valores: {} },
      ],
    } as unknown as ResultadoExpediente
    const tareas = tareasDelRevisor(expediente, TIPOS_DOCUMENTALES)
    expect(tareas.map((t) => [t.texto.split(':')[0], t.documento])).toEqual([
      ['Credencial de elector', amarillo.identificador_unico_documento],
      ['Credencial de elector', amarillo.identificador_unico_documento],
      ['Expediente', null],
      ['Domicilio', amarillo.identificador_unico_documento],
    ])
    expect(tareas[3].texto).toBe('Domicilio: no coincide entre Credencial de elector y Comprobante de domicilio')
  })

  it('nombres de tipo de una comparacion y enumeracion', () => {
    const a = doc()
    expect(tiposComparados({ [a.identificador_unico_documento]: 1, otro: 2 }, [a], TIPOS_DOCUMENTALES)).toEqual(['Credencial de elector', 'Documento'])
    expect([enumerar(['A']), enumerar(['A', 'B']), enumerar(['A', 'B', 'C'])]).toEqual(['A', 'A y B', 'A, B y C'])
  })
})
