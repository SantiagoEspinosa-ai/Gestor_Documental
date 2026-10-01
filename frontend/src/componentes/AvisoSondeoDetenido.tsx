import { Clock, RefreshCw } from 'lucide-react'

/** Sondeo detenido por el limite sin cambios (utilidades/sondeo.ts): el analisis sigue en el servidor */
export function AvisoSondeoDetenido({ alReanudar }: { alReanudar: () => void }) {
  return (
    <div role="status" className="mt-3 flex flex-wrap items-center gap-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <p className="flex items-center gap-2">
        <Clock className="size-4" aria-hidden /> <span><strong>Sigue en proceso.</strong> Lleva un rato sin cambios y se ha dejado de comprobar automáticamente.</span>
      </p>
      <button type="button" onClick={alReanudar} className="inline-flex items-center gap-1 rounded border border-amber-700 bg-white px-2 py-0.5 text-amber-900">
        <RefreshCw className="size-3.5" aria-hidden /> Comprobar de nuevo
      </button>
    </div>
  )
}
