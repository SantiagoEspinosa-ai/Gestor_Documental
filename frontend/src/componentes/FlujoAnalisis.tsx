// Flujo animado del analisis (ADR-014): en el aviso y en el detalle, todos los pasos; en la tarjeta, una
// barra "Paso N de 5". Naranja el paso actual, q-slate con check los hechos, gris los pendientes; siempre texto.
import { Check } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FaseAnalisis } from '../tipos/contrato'
import { AYUDA_FASE, ETIQUETA_FASE, ETIQUETA_FASE_CORTA, textoTranscurrido } from '../utilidades/etiquetas'
import { ICONO_FASE } from './iconosFase'
import { PASOS_BASE, anotarFase, numeroDePaso, pasosDelAnalisis, usePrefiereMenosMovimiento } from '../utilidades/flujoAnalisis'

/** Lo que lleva la fase, contado en el cliente cada segundo desde que se monta (una `key` por fase, ADR-014) */
function Transcurrido() {
  const [inicio] = useState(() => Date.now())
  const [ahora, setAhora] = useState(inicio)
  useEffect(() => {
    const id = window.setInterval(() => setAhora(Date.now()), 1_000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span aria-hidden="true" data-testid="fase-transcurrido" className="font-normal text-slate-500">
      · {textoTranscurrido((ahora - inicio) / 1_000)}
    </span>
  )
}

interface Props {
  fase: FaseAnalisis
  documento: string
}

/** Todos los pasos, con el contador del paso actual. El lector de pantalla solo oye el cambio de fase */
export function FlujoAnalisis({ fase, documento }: Props) {
  const menosMovimiento = usePrefiereMenosMovimiento()
  const pasos = pasosDelAnalisis(fase, anotarFase(documento, fase))
  return (
    <div data-testid="flujo-analisis">
      {/* Unico texto vivo: cambia con la fase, no con cada sondeo ni con el contador */}
      <p className="sr-only" aria-live="polite" data-testid="fase-anunciada">{ETIQUETA_FASE[fase]}</p>
      <ol className="space-y-1" aria-label="Progreso del análisis">
        {pasos.map((paso) => {
          const Icono = paso.estado === 'hecho' ? Check : ICONO_FASE[paso.fase]
          const animado = paso.estado === 'actual' && !menosMovimiento
          const color = paso.estado === 'actual' ? 'text-q-orange-700' : paso.estado === 'hecho' ? 'text-q-slate' : 'text-slate-500'
          return (
            <li key={paso.fase} data-testid={`paso-${paso.fase}`} data-estado={paso.estado}
              aria-current={paso.estado === 'actual' ? 'step' : undefined}
              className={`flex items-start gap-2 text-sm ${color} ${paso.desvio ? 'ml-5 border-l-2 border-dashed border-q-orange-300 pl-2' : ''}`}>
              <span className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
                paso.estado === 'actual' ? 'bg-q-orange-50 ring-1 ring-q-orange' : paso.estado === 'hecho' ? 'bg-q-slate-100' : 'bg-slate-100'}`}>
                <Icono data-testid={`icono-${paso.fase}`} aria-hidden
                  className={`size-3.5 ${animado ? 'animate-pulse' : ''}`} />
              </span>
              <span>
                <span className={paso.estado === 'actual' ? 'font-semibold' : ''}>{ETIQUETA_FASE[paso.fase]}</span>
                <span className="sr-only"> ({paso.estado === 'hecho' ? 'hecho' : paso.estado === 'actual' ? 'en curso' : 'pendiente'})</span>
                {paso.estado === 'actual' && <> <Transcurrido key={`${documento}:${paso.fase}`} /></>}
                {AYUDA_FASE[paso.fase] && paso.estado !== 'hecho' && (
                  <span className="block text-xs font-normal text-slate-600">{AYUDA_FASE[paso.fase]}</span>
                )}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/** Version compacta de la tarjeta: barra con el paso N de 5 (sin contador) */
export function BarraAnalisis({ fase, documento }: Props) {
  anotarFase(documento, fase)
  const n = numeroDePaso(fase)
  return (
    <div className="mt-2" data-testid={`barra-analisis-${documento}`}>
      <div role="progressbar" aria-valuemin={1} aria-valuemax={PASOS_BASE.length} aria-valuenow={n}
        aria-valuetext={`Paso ${n} de ${PASOS_BASE.length}: ${ETIQUETA_FASE_CORTA[fase]}`} aria-label="Progreso del análisis"
        className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-q-orange transition-[width] duration-500 motion-reduce:transition-none"
          style={{ width: `${(n / PASOS_BASE.length) * 100}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-600">Paso {n} de {PASOS_BASE.length}</p>
    </div>
  )
}
