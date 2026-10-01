// Sondeo con espera progresiva y limite de tiempo, compartido por la pantalla de carga y el expediente.
// Con la API real un documento puede quedarse mucho tiempo en `procesando` (Ollama lento o caido):
// el sondeo no puede ser infinito.
import { useEffect, useRef, useState } from 'react'

export interface TiemposSondeo {
  /** Espera antes de la primera consulta y tras cada cambio */
  inicialMs: number
  /** Tope de la espera entre consultas */
  maximoMs: number
  /** Cada consulta sin cambios multiplica la espera por este factor (hasta maximoMs) */
  factor: number
  /** Sin cambios durante este tiempo, el sondeo se detiene hasta que se reanude */
  limiteSinCambiosMs: number
}

export const TIEMPOS_SONDEO: TiemposSondeo = { inicialMs: 3_000, maximoMs: 15_000, factor: 1.5, limiteSinCambiosMs: 10 * 60_000 }

interface Opciones {
  /** Hay algo en curso que sondear (documentos pendientes o procesando) */
  activo: boolean
  /** Resumen del estado que se muestra (p. ej. `id:estado` de cada documento): si cambia, cuenta como cambio */
  firma: string
  /** Una consulta; sus errores se ignoran y se reintenta en la siguiente */
  comprobar: (signal: AbortSignal) => Promise<unknown>
  tiempos?: Partial<TiemposSondeo>
}

export interface EstadoSondeo {
  /** Se detuvo por el limite sin cambios: la UI muestra "Sigue en proceso" */
  detenido: boolean
  /** "Comprobar de nuevo": consulta en el momento y vuelve a empezar con la espera inicial */
  reanudar: () => void
}

/**
 * Consulta con `setTimeout` encadenados (nunca dos a la vez): primero a `inicialMs` y despues cada
 * vez mas espaciado, hasta `maximoMs`. Un cambio de `firma` vuelve a la espera inicial y reinicia el
 * limite. Tras `limiteSinCambiosMs` sin cambios se detiene. Se para al desmontar (salir de la pantalla).
 */
export function useSondeo({ activo, firma, comprobar, tiempos }: Opciones): EstadoSondeo {
  const { inicialMs, maximoMs, factor, limiteSinCambiosMs } = { ...TIEMPOS_SONDEO, ...tiempos }
  const comprobarActual = useRef(comprobar)
  useEffect(() => { comprobarActual.current = comprobar })
  // Firma con la que se detuvo: si el estado cambia por otra via (p. ej. una subida), ya no esta detenido
  const [detenidoEn, setDetenidoEn] = useState<string | null>(null)
  const [reanudaciones, setReanudaciones] = useState(0)
  const detenido = activo && detenidoEn === firma
  const ultimaReanudacion = useRef(0)

  useEffect(() => {
    if (!activo || detenido) return
    const control = new AbortController()
    const inicio = Date.now()
    // Tras "Comprobar de nuevo", la primera consulta es inmediata y la siguiente espera es la inicial
    const inmediata = ultimaReanudacion.current !== reanudaciones
    ultimaReanudacion.current = reanudaciones
    let espera = inmediata ? inicialMs / factor : inicialMs
    let temporizador: ReturnType<typeof setTimeout>
    const consultar = async () => {
      try {
        await comprobarActual.current(control.signal)
      } catch {
        // se reintenta en la siguiente consulta
      }
      if (control.signal.aborted) return
      if (Date.now() - inicio >= limiteSinCambiosMs) {
        setDetenidoEn(firma)
        return
      }
      espera = Math.min(maximoMs, espera * factor)
      temporizador = setTimeout(consultar, espera)
    }
    temporizador = setTimeout(consultar, inmediata ? 0 : inicialMs)
    return () => {
      clearTimeout(temporizador)
      control.abort()
    }
  }, [activo, detenido, firma, reanudaciones, inicialMs, maximoMs, factor, limiteSinCambiosMs])

  return {
    detenido,
    reanudar: () => {
      setDetenidoEn(null)
      setReanudaciones((n) => n + 1)
    },
  }
}

/** Firma de los documentos para useSondeo: identificador y estado de cada uno */
export function firmaDocumentos(documentos: { identificador_unico_documento: string; estado_analisis: string }[]): string {
  return documentos.map((d) => `${d.identificador_unico_documento}:${d.estado_analisis}`).join(',')
}
