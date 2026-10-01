import { AlertCircle, AlertOctagon, AlertTriangle, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Alerta, Severidad } from '../tipos/contrato'
import { ETIQUETA_SEVERIDAD, etiquetaRevision, fechaHora } from '../utilidades/etiquetas'
import { nombreCampo } from '../utilidades/valores'

/** De la mas grave a la menos grave */
const ORDEN: Severidad[] = ['bloqueante', 'critica', 'preventiva', 'informativa']

// Cada severidad con su color, pero siempre tambien con icono y texto (el color no basta)
const ESTILO: Record<Severidad, { icono: typeof Info; caja: string; texto: string }> = {
  bloqueante: { icono: AlertOctagon, caja: 'border-red-300 bg-red-50', texto: 'text-red-900' },
  critica: { icono: AlertCircle, caja: 'border-orange-300 bg-orange-50', texto: 'text-orange-900' },
  preventiva: { icono: AlertTriangle, caja: 'border-yellow-300 bg-yellow-50', texto: 'text-yellow-900' },
  informativa: { icono: Info, caja: 'border-blue-300 bg-blue-50', texto: 'text-blue-900' },
}

interface Props {
  titulo: string
  alertas: Alerta[]
  /** Texto si no hay alertas */
  vacio?: string
  /** Controles por alerta (acciones del revisor); sin ellos la lista es de solo lectura */
  acciones?: (alerta: Alerta) => ReactNode
}

/** Alertas agrupadas por severidad con su estado de revision (ADR-006 2.2) */
export function ListaAlertas({ titulo, alertas, vacio = 'Sin alertas.', acciones }: Props) {
  const grupos = ORDEN.map((s) => ({ severidad: s, alertas: alertas.filter((a) => a.severidad === s) })).filter((g) => g.alertas.length)
  return (
    <section aria-label={titulo}>
      <h3 className="text-sm font-semibold">{titulo}</h3>
      {grupos.length === 0 && <p className="mt-1 text-sm text-slate-500">{vacio}</p>}
      {grupos.map(({ severidad, alertas: delGrupo }) => {
        const { icono: Icono, caja, texto } = ESTILO[severidad]
        return (
          <div key={severidad} className="mt-2">
            <h4 className={`flex items-center gap-1 text-xs font-semibold uppercase ${texto}`}>
              <Icono className="size-4" aria-hidden /> {ETIQUETA_SEVERIDAD[severidad]} ({delGrupo.length})
            </h4>
            <ul className="mt-1 space-y-1">
              {delGrupo.map((a, i) => (
                <li key={a.id ?? `${a.codigo}-${i}`} className={`rounded border px-2 py-1.5 text-sm ${caja}`}
                  data-testid={`alerta-${a.id ?? a.codigo}`}>
                  <p className={texto}>
                    <Icono className="mr-1 inline size-3.5 align-[-2px]" aria-hidden />
                    <span className="sr-only">{ETIQUETA_SEVERIDAD[severidad]}: </span>
                    <span className="font-mono font-semibold">{a.codigo}</span>
                    {a.campo && <span> · {nombreCampo(a.campo)}</span>} — {a.mensaje}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-700">
                    <span className="font-medium">{etiquetaRevision(a)}</span>
                    {a.comentario_revisor && <span> · “{a.comentario_revisor}”</span>}
                    {a.resuelta_por && <span> · {a.resuelta_por}</span>}
                    {a.resuelta_en && <span> · {fechaHora(a.resuelta_en)}</span>}
                  </p>
                  {acciones?.(a)}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </section>
  )
}
