import { AlertTriangle } from 'lucide-react'
import { useId } from 'react'
import { AYUDA_CONFIANZA, ETIQUETA_CONFIANZA } from '../utilidades/etiquetas'
import { porcentaje } from '../utilidades/valores'

interface Props {
  /** 0..1; null si no hay confianza (p. ej. documento sin analizar) */
  valor: number | null
  /** Umbral de la ficha (confianza_minima_campo o confianza_minima_clasificacion); null = sin umbral */
  minimo: number | null
  /** Que se mide, para lectores de pantalla (p. ej. el nombre del campo) */
  de: string
}

/**
 * Confianza verificada (ADR-007): la calcula el codigo comprobando el dato, no el modelo. Por debajo del
 * umbral de la ficha se marca con icono y texto, no solo con color.
 */
export function BarraConfianza({ valor, minimo, de }: Props) {
  const ayuda = useId()
  if (valor === null) return <span className="text-sm text-slate-400">—</span>
  const bajo = minimo !== null && valor < minimo
  const ancho = `${Math.max(0, Math.min(1, valor)) * 100}%`
  return (
    <div className="flex min-w-32 items-center gap-2" title={AYUDA_CONFIANZA}>
      <div role="meter" aria-label={`${ETIQUETA_CONFIANZA} de ${de}`} aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={Math.round(valor * 100)} aria-valuetext={`${porcentaje(valor)}${bajo ? ', bajo el mínimo' : ''}`}
        aria-describedby={ayuda} className="h-2 w-20 shrink-0 overflow-hidden rounded bg-slate-200">
        <div className={`h-full ${bajo ? 'bg-amber-500' : 'bg-green-600'}`} style={{ width: ancho }} />
      </div>
      <span className="text-sm tabular-nums">{porcentaje(valor)}</span>
      {bajo && (
        <span className="inline-flex items-center gap-1 text-xs text-amber-800">
          <AlertTriangle className="size-3.5" aria-hidden /> bajo el mínimo ({porcentaje(minimo ?? 0)})
        </span>
      )}
      <span id={ayuda} className="sr-only">{AYUDA_CONFIANZA}</span>
    </div>
  )
}
