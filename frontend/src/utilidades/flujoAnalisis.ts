// Flujo del analisis de un documento (ADR-014): que pasos estan hechos, cual es el actual y cuales faltan.
// La API solo da la fase actual; las fases ya vistas las recuerda el cliente (memoria de la pagina).
import { useEffect, useState } from 'react'
import type { FaseAnalisis } from '../tipos/contrato'

/** Los 5 pasos de siempre; `vision` es un desvio entre clasificando y extrayendo, solo si ocurre */
export const PASOS_BASE: readonly FaseAnalisis[] = ['en_cola', 'preparando', 'ocr', 'clasificando', 'extrayendo']
const ORDEN: readonly FaseAnalisis[] = ['en_cola', 'preparando', 'ocr', 'clasificando', 'vision', 'extrayendo']

export type EstadoPaso = 'hecho' | 'actual' | 'pendiente'

export interface PasoAnalisis {
  fase: FaseAnalisis
  estado: EstadoPaso
  /** El desvio de vision (se pinta aparte, con su icono) */
  desvio: boolean
}

/**
 * Pasos del flujo para la fase actual. Un paso esta hecho si va antes del actual (el sondeo puede saltarse
 * fases rapidas: nunca se quedan vacias) o si ya se vio (p. ej. "extrayendo" antes de un reintento con
 * vision). La vision solo aparece si es la fase actual o ya se vio. Sin fase (la API no la sabe): todos
 * pendientes.
 */
export function pasosDelAnalisis(fase: FaseAnalisis | null, vistas: ReadonlySet<FaseAnalisis> = new Set()): PasoAnalisis[] {
  const actual = fase ? ORDEN.indexOf(fase) : -1
  return ORDEN
    .filter((f) => f !== 'vision' || fase === 'vision' || vistas.has('vision'))
    .map((f) => ({
      fase: f,
      desvio: f === 'vision',
      estado: f === fase ? 'actual' : (ORDEN.indexOf(f) < actual || vistas.has(f)) ? 'hecho' : 'pendiente',
    }))
}

/** "Paso N de 5" de la version compacta: la vision cuenta como el paso 4 (va entre el 4 y el 5) */
export function numeroDePaso(fase: FaseAnalisis): number {
  return fase === 'vision' ? 4 : PASOS_BASE.indexOf(fase) + 1
}

// ------------------------------------------------------------------ fases vistas por documento

const vistasPorDocumento = new Map<string, Set<FaseAnalisis>>()

/** Anota la fase actual del documento y devuelve las vistas hasta ahora (incluida esta) */
export function anotarFase(documento: string, fase: FaseAnalisis | null): ReadonlySet<FaseAnalisis> {
  let vistas = vistasPorDocumento.get(documento)
  if (!vistas) {
    vistas = new Set()
    vistasPorDocumento.set(documento, vistas)
  }
  if (fase) vistas.add(fase)
  return vistas
}

/** Solo para los tests: olvida las fases vistas */
export function olvidarFasesVistas(): void {
  vistasPorDocumento.clear()
}

// ------------------------------------------------------------------ movimiento reducido

const CONSULTA_MENOS_MOVIMIENTO = '(prefers-reduced-motion: reduce)'

const prefiereMenosMovimientoAhora = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(CONSULTA_MENOS_MOVIMIENTO).matches

/** true si el sistema pide menos movimiento: entonces no se anima nada (solo cambia el icono) */
export function usePrefiereMenosMovimiento(): boolean {
  const [menos, setMenos] = useState(prefiereMenosMovimientoAhora)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const consulta = window.matchMedia(CONSULTA_MENOS_MOVIMIENTO)
    const alCambiar = () => setMenos(consulta.matches)
    consulta.addEventListener?.('change', alCambiar)
    return () => consulta.removeEventListener?.('change', alCambiar)
  }, [])
  return menos
}
