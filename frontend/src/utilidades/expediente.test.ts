import { describe, expect, it } from 'vitest'
import type { Alerta, ResultadoDocumento, Severidad } from '../tipos/contrato'
import { alertasQueBloquean, bloquea, tipoEfectivo, tipoExtraccion, tiposNoPedidos, tiposRequeridosQueFaltan } from './expediente'

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

  it('tipos que el proceso no pide (EXP-002)', () => {
    expect(tiposNoPedidos({ documentos: [doc('pasaporte'), doc('factura'), doc('factura')] }, proceso)).toEqual(['factura'])
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
