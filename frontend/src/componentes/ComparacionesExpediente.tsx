import { CheckCircle2, XCircle } from 'lucide-react'
import type { ResultadoDocumento, ResultadoExpediente, TipoDocumental } from '../tipos/contrato'
import { nombreTipo, tipoEfectivo } from '../utilidades/expediente'
import { enumerar, tiposComparados } from '../utilidades/semaforo'
import { formatearValor, nombreCampo } from '../utilidades/valores'

interface Props {
  expediente: ResultadoExpediente
  fichas: readonly TipoDocumental[]
}

/**
 * Comparaciones entre documentos. Si coincide, solo el campo y "Coincide" (sin valores). Si no, entre que
 * tipos no coincide y el valor de cada documento, tal como llega de la API (los sensibles, enmascarados).
 */
export function ComparacionesExpediente({ expediente, fichas }: Props) {
  const { comparaciones, documentos } = expediente
  const coinciden = comparaciones.filter((c) => c.coincide).length
  const documento = (id: string): ResultadoDocumento | undefined => documentos.find((d) => d.identificador_unico_documento === id)
  return (
    <section aria-labelledby="titulo-comparaciones" className="rounded-lg border border-q-slate-100 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-comparaciones" className="font-semibold">Comparaciones entre documentos</h2>
        {comparaciones.length > 0 && <p className="text-sm text-slate-700" data-testid="resumen-comparaciones">{coinciden} de {comparaciones.length} coinciden</p>}
      </div>
      {comparaciones.length === 0 && <p className="mt-1 text-sm text-slate-600">Sin comparaciones: hacen falta al menos dos documentos con el mismo dato.</p>}
      <ul className="mt-2 space-y-2">
        {comparaciones.map((c) => (
          <li key={c.campo} className="rounded border border-slate-200 px-3 py-2 text-sm" data-testid={`comparacion-${c.campo}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{nombreCampo(c.campo)}</span>
              {c.coincide ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-semaforo-verde-borde bg-semaforo-verde-fondo px-2 py-0.5 text-xs font-semibold text-semaforo-verde">
                  <CheckCircle2 className="size-3.5" aria-hidden /> Coincide
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full border border-semaforo-rojo-borde bg-semaforo-rojo-fondo px-2 py-0.5 text-xs font-semibold text-semaforo-rojo">
                  <XCircle className="size-3.5" aria-hidden /> No coincide
                </span>
              )}
            </div>
            {!c.coincide && (
              <>
                <p className="mt-1">No coincide entre {enumerar(tiposComparados(c.valores, documentos, fichas))}</p>
                <dl className="mt-1 space-y-0.5 text-xs">
                  {Object.entries(c.valores).map(([id, valor]) => {
                    const d = documento(id)
                    return (
                      <div key={id} className="flex flex-wrap gap-x-2">
                        <dt className="text-slate-600">
                          {d ? `${nombreTipo(tipoEfectivo(d), fichas, 'Sin tipo')} (${d.referencia_archivo_original.nombre_archivo})` : id}:
                        </dt>
                        <dd className="font-mono">{formatearValor(valor)}</dd>
                      </div>
                    )
                  })}
                </dl>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
