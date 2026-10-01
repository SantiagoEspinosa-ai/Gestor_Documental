// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AYUDA_CONFIANZA } from '../utilidades/etiquetas'
import { BarraConfianza } from './BarraConfianza'

describe('BarraConfianza', () => {
  it('muestra la confianza verificada (ADR-007) con porcentaje y ayuda', () => {
    render(<BarraConfianza valor={0.92} minimo={0.8} de="CURP" />)
    const barra = screen.getByRole('meter', { name: 'Confianza verificada de CURP' })
    expect(barra.getAttribute('aria-valuenow')).toBe('92')
    expect(screen.getByText('92 %')).toBeTruthy()
    expect(screen.queryByText(/bajo el mínimo/)).toBeNull()
    expect(screen.getByText(AYUDA_CONFIANZA)).toBeTruthy() // ayuda para lectores de pantalla
  })

  it('por debajo del umbral de la ficha lo dice con texto e icono, no solo con color', () => {
    render(<BarraConfianza valor={0.62} minimo={0.8} de="Clave de elector" />)
    expect(screen.getByText(/bajo el mínimo \(80 %\)/)).toBeTruthy()
    expect(screen.getByRole('meter').getAttribute('aria-valuetext')).toBe('62 %, bajo el mínimo')
  })

  it('un campo sin valor tiene confianza 0 y queda bajo el mínimo; sin confianza, un guion', () => {
    const { rerender } = render(<BarraConfianza valor={0} minimo={0.75} de="Proveedor" />)
    expect(screen.getByText('0 %')).toBeTruthy()
    expect(screen.getByText(/bajo el mínimo \(75 %\)/)).toBeTruthy()
    rerender(<BarraConfianza valor={null} minimo={0.75} de="Proveedor" />)
    expect(screen.queryByRole('meter')).toBeNull()
    expect(screen.getByText('—')).toBeTruthy()
  })
})
