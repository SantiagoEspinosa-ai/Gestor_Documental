// Comprobacion en TypeScript de los datos de los mocks: valores de los enums y codigos oficiales.
// La validacion completa contra resultado.py esta en backend/tests/test_contrato_frontend.py.
import { describe, expect, it } from 'vitest'
import { esCodigoAlertaPermitido } from '../tipos/codigos'
import {
  DECISIONES_HUMANAS, ESTADOS_ANALISIS, ESTADOS_GENERALES, RECOMENDACIONES, SEVERIDADES, type Alerta,
} from '../tipos/contrato'
import { FOLIOS } from './datos'

const alertas: Alerta[] = FOLIOS.flatMap((f) => [...f.alertas_expediente, ...f.documentos.flatMap((d) => d.alertas_encontradas)])
const incluye = (lista: readonly (string | null)[], valor: string | null) => valor === null || lista.includes(valor)

describe('datos de los mocks', () => {
  it('los enums solo usan valores del contrato', () => {
    for (const f of FOLIOS) {
      expect(ESTADOS_GENERALES).toContain(f.estado_general)
      expect(incluye(RECOMENDACIONES, f.recomendacion_global)).toBe(true)
      expect(incluye(DECISIONES_HUMANAS, f.decision_humana)).toBe(true)
      for (const d of f.documentos) {
        expect(ESTADOS_ANALISIS).toContain(d.estado_analisis)
        expect(incluye(RECOMENDACIONES, d.recomendacion)).toBe(true)
      }
    }
    for (const a of alertas) expect(SEVERIDADES).toContain(a.severidad)
  })

  it('los codigos de alerta son oficiales o pendientes de main', () => {
    const noOficiales = alertas.filter((a) => !esCodigoAlertaPermitido(a.codigo))
    expect(noOficiales.map((a) => [a.codigo, a.severidad])).toEqual([])
  })
})
