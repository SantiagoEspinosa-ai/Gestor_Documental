import { Clock } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FaseAnalisis } from '../tipos/contrato'
import { ETIQUETA_FASE, textoTranscurrido } from '../utilidades/etiquetas'

/** Lo que lleva la fase, contado en el cliente cada segundo desde que se monta (una `key` por fase) */
function Transcurrido() {
  const [inicio] = useState(() => Date.now())
  const [ahora, setAhora] = useState(inicio)
  useEffect(() => {
    const id = window.setInterval(() => setAhora(Date.now()), 1_000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span aria-hidden="true" data-testid="fase-transcurrido" className="text-slate-500">
      · {textoTranscurrido((ahora - inicio) / 1_000)}
    </span>
  )
}

/**
 * Aviso del documento que se esta analizando (ADR-014): la frase de la fase y lo que lleva en ella. El lector
 * de pantalla anuncia el cambio de fase (aria-live), no cada segundo del contador (aria-hidden). Sin fase
 * (la API no la sabe, p. ej. tras reiniciarse), el texto de siempre.
 */
export function AvisoAnalisis({ fase, documento }: { fase: FaseAnalisis | null; documento: string }) {
  return (
    <p role="status" aria-live="polite" className="flex flex-wrap items-center gap-2 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
      <Clock className="size-4" aria-hidden />
      {fase === null ? 'El documento se está analizando; la vista se actualiza sola.' : (
        <>
          <span data-testid="fase-analisis">{ETIQUETA_FASE[fase]}</span>
          {/* Otra fase u otro documento: se monta de nuevo y empieza de cero */}
          <Transcurrido key={`${documento}:${fase}`} />
        </>
      )}
    </p>
  )
}
