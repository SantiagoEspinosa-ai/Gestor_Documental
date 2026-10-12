// Semaforo de los documentos: siempre icono + texto (el color nunca va solo). Tokens en index.css (@theme).
import { LEYENDA_SEMAFORO, NOMBRE_COLOR, type Semaforo } from '../utilidades/semaforo'
import { ESTILO_SEMAFORO } from './estiloSemaforo'

/** Etiqueta del semaforo: icono + texto */
export function InsigniaSemaforo({ semaforo, id }: { semaforo: Semaforo; id?: string }) {
  const { icono: Icono, caja, texto } = ESTILO_SEMAFORO[semaforo.color]
  return (
    <span data-testid={id ? `semaforo-${id}` : undefined} data-color={semaforo.color}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${caja} ${texto}`}>
      <Icono className={`size-3.5 ${semaforo.color === 'en_proceso' ? 'animate-spin' : ''}`} aria-hidden />
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
