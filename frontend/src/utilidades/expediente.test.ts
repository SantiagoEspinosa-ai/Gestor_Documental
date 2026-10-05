import { describe, expect, it } from 'vitest'
import { TIPO_DESCONOCIDO, type Alerta, type ResultadoDocumento, type Severidad } from '../tipos/contrato'
import {
  alertasQueBloquean, bloquea, fichaDeTipo, nombreTipo, tipoEfectivo, tipoExtraccion, tipoNoPrevisto, tiposRequeridosQueFaltan,
} from './expediente'

const doc = (declarado: string | null, detectado: string | null = null, confirmado: string | null = null) =>
  ({ tipo_documental_declarado: declarado, tipo_documental_detectado: detectado, tipo_documental_confirmado: confirmado }) as ResultadoDocumento
const proceso = { tipos_requeridos: ['credencial_elector', 'comprobante_domicilio'], tipos_opcionales: ['pasaporte'] }

describe('tipo efectivo', () => {
  it('confirmado > detectado > declarado', () => {
    expect(tipoEfectivo(doc('pasaporte', 'credencial_elector', 'comprobante_domicilio'))).toBe('comprobante_domicilio')
    expect(tipoEfectivo(doc('pasaporte', 'credencial_elector'))).toBe('credencial_elector')
    expect(tipoEfectivo(doc('pasaporte'))).toBe('pasaporte')
    expect(tipoEfectivo(doc(null))).toBeNull()
  })

  it('tipos requeridos que faltan segun el tipo efectivo (aviso de la pantalla de carga)', () => {
    expect(tiposRequeridosQueFaltan({ documentos: [] }, proceso)).toEqual(['credencial_elector', 'comprobante_domicilio'])
    // Declarado como comprobante pero detectado como credencial: cuenta la credencial
    expect(tiposRequeridosQueFaltan({ documentos: [doc('comprobante_domicilio', 'credencial_elector')] }, proceso))
      .toEqual(['comprobante_domicilio'])
    expect(tiposRequeridosQueFaltan({ documentos: [doc('credencial_elector'), doc('comprobante_domicilio')] }, proceso)).toEqual([])
  })

  it('tipo no previsto por el proceso, por documento y con el tipo efectivo (EXP-002)', () => {
    expect(tipoNoPrevisto(doc('factura'), proceso)).toBe('factura')
    expect(tipoNoPrevisto(doc('pasaporte'), proceso)).toBeNull() // opcional: previsto
    expect(tipoNoPrevisto(doc('credencial_elector'), proceso)).toBeNull() // requerido: previsto
    expect(tipoNoPrevisto(doc('factura', 'pasaporte'), proceso)).toBeNull() // cuenta el detectado
    expect(tipoNoPrevisto(doc('pasaporte', null, 'factura'), proceso)).toBe('factura') // y el confirmado
    expect(tipoNoPrevisto(doc(null), proceso)).toBeNull()
  })
})

describe('tipo desconocido (ADR-009)', () => {
  it('no cubre ningun requerido aunque se declarara uno, y da EXP-002 con campo desconocido (como el backend)', () => {
    expect(tiposRequeridosQueFaltan({ documentos: [doc('credencial_elector', TIPO_DESCONOCIDO), doc('comprobante_domicilio')] }, proceso))
      .toEqual(['credencial_elector'])
    expect(tipoNoPrevisto(doc(null, TIPO_DESCONOCIDO), proceso)).toBe(TIPO_DESCONOCIDO)
    // Al confirmar un tipo previsto, cubre su requerido y deja de ser no previsto
    expect(tiposRequeridosQueFaltan({ documentos: [doc(null, TIPO_DESCONOCIDO, 'credencial_elector')] }, proceso))
      .toEqual(['comprobante_domicilio'])
    expect(tipoNoPrevisto(doc(null, TIPO_DESCONOCIDO, 'credencial_elector'), proceso)).toBeNull()
  })

  it('nombre "Tipo no reconocido" y nunca se busca su ficha', () => {
    const fichas = [{ nombre: 'pasaporte', nombre_visible: 'Pasaporte' }, { nombre: TIPO_DESCONOCIDO, nombre_visible: 'No usar' }]
    expect(fichaDeTipo(fichas, TIPO_DESCONOCIDO)).toBeUndefined()
    expect(fichaDeTipo(fichas, 'pasaporte')?.nombre_visible).toBe('Pasaporte')
    expect(nombreTipo(TIPO_DESCONOCIDO, fichas, 'Sin tipo')).toBe('Tipo no reconocido')
    expect(nombreTipo('pasaporte', fichas, 'Sin tipo')).toBe('Pasaporte')
    expect(nombreTipo('tipo_sin_ficha', fichas, 'Sin tipo')).toBe('tipo_sin_ficha')
    expect(nombreTipo(null, fichas, 'Sin tipo')).toBe('Sin tipo')
  })
})

describe('tipo de extraccion (regla 2.5)', () => {
  it('confirmado > declarado > detectado', () => {
    expect(tipoExtraccion(doc('pasaporte', 'credencial_elector'))).toBe('pasaporte')
    expect(tipoExtraccion(doc(null, 'credencial_elector'))).toBe('credencial_elector')
    expect(tipoExtraccion(doc('pasaporte', 'credencial_elector', 'comprobante_domicilio'))).toBe('comprobante_domicilio')
  })
})

describe('regla de bloqueo de la aprobacion (ADR-006 2.2)', () => {
  const alerta = (id: string, severidad: Severidad, aplica: boolean | null) => ({ id, severidad, aplica }) as Alerta
  it('una bloqueante bloquea sin revisar y confirmada (aplica=true); solo un falso positivo la desbloquea', () => {
    expect(bloquea(alerta('a', 'bloqueante', null))).toBe(true)
    expect(bloquea(alerta('a', 'bloqueante', true))).toBe(true)
    expect(bloquea(alerta('a', 'bloqueante', false))).toBe(false)
    expect(bloquea(alerta('a', 'critica', null))).toBe(false) // las criticas no impiden aprobar
  })

  it('cuenta las alertas de documento y de expediente', () => {
    const expediente = {
      alertas_expediente: [alerta('exp', 'bloqueante', null), alerta('cmp', 'critica', null)],
      documentos: [{ alertas_encontradas: [alerta('reg', 'bloqueante', true), alerta('fp', 'bloqueante', false)] } as ResultadoDocumento],
    }
    expect(alertasQueBloquean(expediente).map((a) => a.id)).toEqual(['exp', 'reg'])
    expect(alertasQueBloquean({ alertas_expediente: [], documentos: [] })).toEqual([])
  })
})
