// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Alerta, Severidad } from '../tipos/contrato'
import { ListaAlertas } from './ListaAlertas'

const alerta = (id: string, codigo: string, severidad: Severidad, extra: Partial<Alerta> = {}): Alerta => ({
  id, codigo, severidad, mensaje: `Mensaje de ${codigo}`, confianza: 1, campo: null, resuelta_por_revisor: false,
  aplica: null, comentario_revisor: null, resuelta_por: null, resuelta_en: null, ...extra,
})

describe('ListaAlertas', () => {
  it('agrupa por severidad de la mas grave a la menos grave, con icono y texto en cada grupo', () => {
    render(<ListaAlertas titulo="Alertas" alertas={[
      alerta('a1', 'VAL-004', 'informativa', { campo: 'proveedor' }), alerta('a2', 'VAL-002', 'preventiva'),
      alerta('a3', 'EXP-001', 'bloqueante'), alerta('a4', 'CMP-001', 'critica'), alerta('a5', 'SYS-005', 'informativa'),
    ]} />)
    const grupos = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent?.trim())
    expect(grupos).toEqual(['Bloqueante (1)', 'Crítica (1)', 'Preventiva (1)', 'Informativa (2)'])
    const informativa = screen.getByTestId('alerta-a1')
    expect(informativa.textContent).toContain('Informativa: VAL-004 · Proveedor — Mensaje de VAL-004')
    expect(informativa.className).toContain('bg-blue-50')
    expect(screen.getByTestId('alerta-a3').className).toContain('bg-red-50')
    expect(screen.getByTestId('alerta-a4').className).toContain('bg-orange-50')
    expect(screen.getByTestId('alerta-a2').className).toContain('bg-yellow-50')
  })

  it('muestra el estado de revision: sin revisar, aplica o falso positivo con comentario, autor y fecha', () => {
    render(<ListaAlertas titulo="Alertas" alertas={[
      alerta('s', 'CLS-001', 'critica'),
      alerta('f', 'EXP-001', 'bloqueante', { aplica: false, resuelta_por_revisor: true, comentario_revisor: 'Llega por otra via',
        resuelta_por: 'revisor.demo', resuelta_en: '2026-09-30T10:00:00Z' }),
      alerta('c', 'DUP-001', 'critica', { aplica: true, resuelta_por_revisor: true, resuelta_por: 'revisor.demo', resuelta_en: '2026-09-30T11:00:00Z' }),
    ]} />)
    expect(within(screen.getByTestId('alerta-s')).getByText('Sin revisar')).toBeTruthy()
    const falso = screen.getByTestId('alerta-f').textContent!
    expect(falso).toContain('Falso positivo')
    expect(falso).toContain('“Llega por otra via”')
    expect(falso).toContain('revisor.demo')
    expect(falso).toContain('30/09/2026')
    expect(screen.getByTestId('alerta-c').textContent).toContain('Aplica (confirmada por el revisor)')
  })

  it('sin alertas muestra el texto vacio', () => {
    render(<ListaAlertas titulo="Alertas del expediente" alertas={[]} vacio="Nada que revisar." />)
    expect(screen.getByText('Nada que revisar.')).toBeTruthy()
  })
})
