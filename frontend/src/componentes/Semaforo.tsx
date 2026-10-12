// Semaforo de los documentos: siempre icono + texto (el color nunca va solo). Tokens en index.css (@theme).
import type { FaseAnalisis } from '../tipos/contrato'
import { usePrefiereMenosMovimiento } from '../utilidades/flujoAnalisis'
import { LEYENDA_SEMAFORO, NOMBRE_COLOR, type Semaforo } from '../utilidades/semaforo'
import { ESTILO_SEMAFORO } from './estiloSemaforo'
import { ICONO_FASE } from './iconosFase'

/**
 * Etiqueta del semaforo: icono + texto. En proceso, el icono de la fase (ADR-014) con un pulso suave; al
 * terminar, el color nuevo aparece con un fundido corto. Con movimiento reducido, nada se anima.
 */
export function InsigniaSemaforo({ semaforo, id, fase }: { semaforo: Semaforo; id?: string; fase?: FaseAnalisis | null }) {
  const menosMovimiento = usePrefiereMenosMovimiento()
  const { icono, caja, texto } = ESTILO_SEMAFORO[semaforo.color]
  const enProceso = semaforo.color === 'en_proceso'
  const Icono = enProceso && fase ? ICONO_FASE[fase] : icono
  const animacion = menosMovimiento ? '' : enProceso ? 'animate-pulse' : ''
  return (
    // key: al cambiar de color se vuelve a montar y se ve el fundido
    <span key={semaforo.color} data-testid={id ? `semaforo-${id}` : undefined} data-color={semaforo.color}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${caja} ${texto} ${
        menosMovimiento ? '' : 'animate-aparecer'}`}>
      <Icono className={`size-3.5 ${animacion}`} aria-hidden data-testid={id ? `icono-semaforo-${id}` : undefined} />
      {semaforo.etiqueta}
    </span>
  )
}

/** "Que significan los colores" */
export function LeyendaSemaforo() {
  return (
    <section aria-labelledby="titulo-leyenda" className="rounded-lg border border-q-slate-100 bg-white p-3 text-sm">
      <h2 id="titulo-leyenda" className="font-semibold">Qué significan los colores</h2>
      <ul className="mt-2 grid gap-2 sm:grid-cols-3">
        {LEYENDA_SEMAFORO.map(({ color, texto }) => {
          const { icono: Icono, texto: colorTexto } = ESTILO_SEMAFORO[color]
          return (
            <li key={color} className="flex items-start gap-2">
              <Icono className={`mt-0.5 size-4 shrink-0 ${colorTexto}`} aria-hidden />
              <span><span className={`font-semibold ${colorTexto}`}>{NOMBRE_COLOR[color]}:</span> {texto}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
