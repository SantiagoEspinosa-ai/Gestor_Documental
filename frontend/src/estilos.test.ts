// Contraste AA (>= 4,5:1) de los tokens de color del semaforo, leidos del propio index.css
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(process.cwd(), 'src', 'index.css'), 'utf-8')
const token = (nombre: string) => {
  const m = new RegExp(`--color-${nombre}:\\s*(#[0-9A-Fa-f]{6});`).exec(css)
  if (!m) throw new Error(`falta el token --color-${nombre}`)
  return m[1]
}
function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

describe('tokens del semaforo', () => {
  it.each(['verde', 'ambar', 'rojo', 'gris'])('%s: texto sobre su fondo y sobre blanco >= 4,5:1', (color) => {
    expect(contraste(token(`semaforo-${color}`), token(`semaforo-${color}-fondo`))).toBeGreaterThanOrEqual(4.5)
    expect(contraste(token(`semaforo-${color}`), '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
  })

  it('la formula de contraste es la de WCAG', () => {
    expect(contraste('#000000', '#FFFFFF')).toBeCloseTo(21, 5)
    expect(contraste('#777777', '#FFFFFF')).toBeCloseTo(4.48, 2)
  })
})
