import { History } from 'lucide-react'
import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { Link } from 'react-router'
import { obtenerAntecedentes } from '../api/folios'
import type { RespuestaAntecedentes } from '../tipos/contrato'
import { ETIQUETA_DECISION, ETIQUETA_ESTADO_GENERAL, ETIQUETA_MOTIVO_SIN_ANTECEDENTES, fechaHora } from '../utilidades/etiquetas'
import { mensajeDeError } from '../utilidades/mensajes'

interface Props {
  folio: string
}

/**
 * Antecedentes del folio (H16, ADR-010 C): GET /folios/{folio}/antecedentes, solo revisor y admin (lo
 * decide quien lo pinta). Estados: cargando, error, no permitido (con el motivo legible), sin antecedentes
 * y la lista. El fragmento llega ya enmascarado y se pinta como el resumen: react-markdown sin HTML crudo
 * (skipHtml) y sin enlaces ni imagenes.
 */
export function Antecedentes({ folio }: Props) {
  const [estado, setEstado] = useState<{ datos: RespuestaAntecedentes | null; error: string | null }>({ datos: null, error: null })

  useEffect(() => {
    const control = new AbortController()
    obtenerAntecedentes(folio, control.signal)
      .then((datos) => setEstado({ datos, error: null }))
      .catch((causa) => { if (!control.signal.aborted) setEstado({ datos: null, error: mensajeDeError(causa) }) })
    return () => control.abort()
  }, [folio])

  const { datos, error } = estado
  return (
    <section aria-label="Antecedentes" className="space-y-1">
      <h3 className="flex items-center gap-1 text-sm font-semibold"><History className="size-4" aria-hidden /> Antecedentes</h3>
      {!datos && !error && <p role="status" className="text-sm text-slate-500">Cargando los antecedentes…</p>}
      {error && <p role="alert" className="text-sm text-red-700">No se pudieron cargar los antecedentes: {error}</p>}
      {datos && !datos.permitido && (
        <p className="text-sm text-slate-600">{datos.motivo ? ETIQUETA_MOTIVO_SIN_ANTECEDENTES[datos.motivo] : 'No se pueden consultar los antecedentes.'}</p>
      )}
      {datos?.permitido && datos.elementos.length === 0 && (
        <p className="text-sm text-slate-500">Sin antecedentes: no hay folios cerrados de esta referencia dentro del plazo del proceso.</p>
      )}
      {datos?.permitido && datos.elementos.length > 0 && (
        <ul className="space-y-2">
          {datos.elementos.map((a) => (
            <li key={a.folio} aria-label={`Antecedente ${a.folio}`} className="rounded border border-slate-200 bg-white px-2 py-1.5 text-sm">
              <p className="font-medium">
                <Link to={`/folios/${encodeURIComponent(a.folio)}`} className="font-mono text-q-slate underline hover:text-q-orange-700">{a.folio}</Link>
                {' · '}{ETIQUETA_ESTADO_GENERAL[a.estado_general]}
                {a.decision_humana && <> · Decisión: {ETIQUETA_DECISION[a.decision_humana]}</>}
              </p>
              <p className="text-xs text-slate-600">
                Solicitado el {fechaHora(a.fecha_solicitud)} · decidido el {fechaHora(a.fecha_decision)}
              </p>
              {a.fragmento_resumen
                ? (
                  <div className="mt-1 space-y-1 text-xs text-slate-700 [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-medium [&_ul]:list-disc [&_ul]:pl-4">
                    <Markdown skipHtml disallowedElements={['a', 'img']} unwrapDisallowed>{a.fragmento_resumen}</Markdown>
                  </div>
                )
                : <p className="mt-1 text-xs italic text-slate-500">Sin resumen en la memoria de folios.</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
