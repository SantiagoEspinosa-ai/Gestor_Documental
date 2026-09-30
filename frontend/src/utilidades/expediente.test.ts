import { describe, expect, it } from 'vitest'
import type { ResultadoDocumento } from '../tipos/contrato'
import { tipoEfectivo, tiposNoPedidos, tiposRequeridosQueFaltan } from './expediente'

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
