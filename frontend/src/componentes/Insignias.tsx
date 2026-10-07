import { AlertOctagon } from 'lucide-react'
import type { EstadoGeneral, Recomendacion } from '../tipos/contrato'
import { ETIQUETA_ESTADO_GENERAL, ETIQUETA_RECOMENDACION } from '../utilidades/etiquetas'

const COLOR_ESTADO: Record<EstadoGeneral, string> = {
  en_revision: 'bg-q-slate-100 text-q-slate', aprobado: 'bg-q-slate text-white', rechazado: 'bg-red-100 text-red-900',
}
const COLOR_RECOMENDACION: Record<Recomendacion, string> = {
  aprobar: 'text-q-slate', revision_manual: 'text-q-orange-700', rechazar: 'text-red-800',
}

export function InsigniaEstado({ estado }: { estado: EstadoGeneral }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${COLOR_ESTADO[estado]}`}>{ETIQUETA_ESTADO_GENERAL[estado]}</span>
}

export function TextoRecomendacion({ valor }: { valor: Recomendacion | null }) {
  return valor ? <span className={COLOR_RECOMENDACION[valor]}>{ETIQUETA_RECOMENDACION[valor]}</span> : <span className="text-slate-400">—</span>
}

/** Indicador de alertas bloqueantes sin resolver (regla 2.2) */
export function IndicadorBloqueantes({ n }: { n: number }) {
  if (n === 0) return <span className="text-slate-400" aria-label="Sin alertas bloqueantes">0</span>
  const texto = `${n} ${n === 1 ? 'alerta bloqueante sin resolver' : 'alertas bloqueantes sin resolver'}`
  return (
    <span className="inline-flex items-center gap-1 rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800" title={texto}>
      <AlertOctagon className="size-3.5" aria-hidden /> {n}<span className="sr-only"> {texto}</span>
    </span>
  )
}
