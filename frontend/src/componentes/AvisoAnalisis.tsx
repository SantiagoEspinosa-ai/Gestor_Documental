import { Clock } from 'lucide-react'
import type { FaseAnalisis } from '../tipos/contrato'
import { FlujoAnalisis } from './FlujoAnalisis'

/**
 * Aviso del documento que se esta analizando (ADR-014): el flujo de pasos con el actual resaltado y lo que
 * lleva en el (contado en el cliente). El lector de pantalla anuncia el cambio de fase (aria-live), no cada
 * segundo del contador ni cada sondeo. Sin fase (la API no la sabe, p. ej. tras reiniciarse), el texto de siempre.
 */
export function AvisoAnalisis({ fase, documento }: { fase: FaseAnalisis | null; documento: string }) {
  if (fase === null) {
    return (
      <p role="status" aria-live="polite" className="flex items-center gap-2 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
        <Clock className="size-4" aria-hidden />
        El documento se está analizando; la vista se actualiza sola.
      </p>
    )
  }
  return (
    <section aria-label="Análisis en curso" className="rounded border border-q-orange-100 bg-white px-3 py-2">
      <FlujoAnalisis fase={fase} documento={documento} />
    </section>
  )
}
