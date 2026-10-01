// @vitest-environment jsdom
// useSondeo con temporizadores falsos de Vitest (setTimeout y Date).
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { firmaDocumentos, TIEMPOS_SONDEO, useSondeo } from './sondeo'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const avanzar = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))

function preparar(props: { activo?: boolean; firma?: string } = {}) {
  const inicio = Date.now()
  const momentos: number[] = []
  const senales: AbortSignal[] = []
  const comprobar = vi.fn(async (signal: AbortSignal) => {
    momentos.push(Date.now() - inicio)
    senales.push(signal)
  })
  const vista = renderHook((p: { activo: boolean; firma: string }) => useSondeo({ ...p, comprobar }),
    { initialProps: { activo: true, firma: 'a', ...props } })
  const esperas = () => momentos.map((m, i) => m - (momentos[i - 1] ?? 0))
  return { ...vista, comprobar, momentos, senales, esperas }
}

describe('useSondeo', () => {
  it('por defecto: 3 s iniciales que crecen hasta 15 s y 10 minutos sin cambios', () => {
    expect(TIEMPOS_SONDEO).toEqual({ inicialMs: 3000, maximoMs: 15000, factor: 1.5, limiteSinCambiosMs: 600000 })
  })

  it('la espera empieza en 3 s y crece de forma progresiva hasta 15 s', async () => {
    const s = preparar()
    await avanzar(2999)
    expect(s.comprobar).not.toHaveBeenCalled()
    await avanzar(70_000)
    expect(s.esperas().slice(0, 7)).toEqual([3000, 4500, 6750, 10125, 15000, 15000, 15000])
  })

  it('tras 10 minutos sin cambios se detiene y no vuelve a consultar', async () => {
    const s = preparar()
    await avanzar(10 * 60_000 - 1000)
    expect(s.result.current.detenido).toBe(false)
    await avanzar(20_000)
    expect(s.result.current.detenido).toBe(true)
    expect(s.momentos.at(-1)).toBeGreaterThanOrEqual(10 * 60_000)
    const llamadas = s.comprobar.mock.calls.length
    await avanzar(60 * 60_000)
    expect(s.comprobar).toHaveBeenCalledTimes(llamadas)
  })

  it('un cambio de firma vuelve a la espera inicial y reinicia el limite', async () => {
    const s = preparar()
    await avanzar(9 * 60_000) // espera ya en 15 s
    s.rerender({ activo: true, firma: 'b' })
    const antes = s.comprobar.mock.calls.length
    await avanzar(3000)
    expect(s.comprobar).toHaveBeenCalledTimes(antes + 1)
    await avanzar(5 * 60_000) // 14 minutos desde el principio, 5 desde el cambio
    expect(s.result.current.detenido).toBe(false)
  })

  it('"Comprobar de nuevo" (reanudar) consulta en el momento y vuelve a empezar', async () => {
    const s = preparar()
    await avanzar(11 * 60_000)
    expect(s.result.current.detenido).toBe(true)
    const antes = s.comprobar.mock.calls.length
    act(() => s.result.current.reanudar())
    expect(s.result.current.detenido).toBe(false)
    await avanzar(0)
    expect(s.comprobar).toHaveBeenCalledTimes(antes + 1)
    await avanzar(3000)
    expect(s.comprobar).toHaveBeenCalledTimes(antes + 2) // de nuevo con la espera inicial
  })

  it('detenido, si el estado cambia por otra via deja de estarlo y sigue sondeando', async () => {
    const s = preparar()
    await avanzar(11 * 60_000)
    expect(s.result.current.detenido).toBe(true)
    s.rerender({ activo: true, firma: 'c' }) // p. ej. se subio otro documento
    expect(s.result.current.detenido).toBe(false)
    const antes = s.comprobar.mock.calls.length
    await avanzar(3000)
    expect(s.comprobar).toHaveBeenCalledTimes(antes + 1)
  })

  it('se detiene al salir de la pantalla (desmontar) y cancela la consulta en curso', async () => {
    const s = preparar()
    await avanzar(3000)
    s.unmount()
    expect(s.senales[0].aborted).toBe(true)
    await avanzar(60_000)
    expect(s.comprobar).toHaveBeenCalledTimes(1)
  })

  it('sin nada en curso no consulta ni muestra "detenido"', async () => {
    const s = preparar({ activo: false })
    await avanzar(20 * 60_000)
    expect(s.comprobar).not.toHaveBeenCalled()
    expect(s.result.current.detenido).toBe(false)
  })

  it('un error en la consulta no para el sondeo', async () => {
    const comprobar = vi.fn(async () => { throw new Error('sin conexion') })
    renderHook(() => useSondeo({ activo: true, firma: 'a', comprobar }))
    await avanzar(3000 + 4500)
    expect(comprobar).toHaveBeenCalledTimes(2)
  })

  it('firma de los documentos: identificador y estado', () => {
    expect(firmaDocumentos([{ identificador_unico_documento: 'd1', estado_analisis: 'pendiente' },
      { identificador_unico_documento: 'd2', estado_analisis: 'completado' }])).toBe('d1:pendiente,d2:completado')
  })
})
