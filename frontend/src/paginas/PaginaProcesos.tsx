import { Info } from 'lucide-react'
import { useEffect, useState } from 'react'
import { listarProcesos, listarTiposDocumentales } from '../api/folios'
import type { Proceso } from '../tipos/contrato'
import { mensajeDeError } from '../utilidades/mensajes'
import { describirWebhook } from '../utilidades/procesos'

// GET /procesos (admin), en solo lectura (H8, recorte R3): la edicion queda fuera del MVP (ADR-006, bloque 4)
type NombresTipos = Record<string, string>

export function PaginaProcesos() {
  const [procesos, setProcesos] = useState<Proceso[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tipos, setTipos] = useState<NombresTipos>({})

  useEffect(() => {
    const control = new AbortController()
    listarTiposDocumentales(control.signal)
      .then((lista) => setTipos(Object.fromEntries(lista.map((t) => [t.nombre, t.nombre_visible]))))
      .catch(() => { /* sin nombres visibles: se muestra el nombre tecnico */ })
    listarProcesos(control.signal)
      .then(setProcesos)
      .catch((causa) => {
        if (!control.signal.aborted) setError(mensajeDeError(causa))
      })
    return () => control.abort()
  }, [])

  const nombreTipo = (tipo: string) => tipos[tipo] ?? tipo
  const listaTipos = (lista: string[]) => (lista.length ? lista.map(nombreTipo).join(', ') : '—')

  return (
    <section aria-labelledby="titulo-procesos">
      <h1 id="titulo-procesos" className="text-xl font-semibold">Procesos</h1>
      <p className="mt-1 flex items-center gap-1 text-sm text-slate-600">
        <Info className="size-4" aria-hidden />
        Solo lectura: los procesos se cambian en config/procesos.yaml y se cargan al arrancar la API.
      </p>

      {error && <p role="alert" className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-red-800">{error}</p>}
      {!error && procesos === null && <p role="status" className="mt-4 text-sm text-slate-600">Cargando procesos…</p>}
      {!error && procesos?.length === 0 && <p className="mt-4 text-slate-600">No hay procesos configurados.</p>}
      {!error && procesos && procesos.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse bg-white text-sm">
            <caption className="sr-only">Procesos configurados</caption>
            <thead className="bg-slate-100 text-left">
              <tr>
                {['Proceso', 'Prefijo de folio', 'Tipos requeridos', 'Tipos opcionales', 'Antecedentes',
                  'Caducidad de antecedentes', 'Modelos', 'Webhook'].map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {procesos.map((p) => (
                <tr key={p.nombre} className="border-t border-slate-200 align-top">
                  <th scope="row" className="px-3 py-2 text-left font-medium">{p.nombre}</th>
                  <td className="px-3 py-2 font-mono">{p.prefijo_folio}</td>
                  <td className="px-3 py-2">{listaTipos(p.tipos_requeridos)}</td>
                  <td className="px-3 py-2">{listaTipos(p.tipos_opcionales)}</td>
                  <td className="px-3 py-2">{p.permitir_antecedentes ? 'Sí' : 'No'}</td>
                  <td className="px-3 py-2">
                    {p.caducidad_antecedentes_dias == null ? '—' : `${p.caducidad_antecedentes_dias} días`}
                  </td>
                  <td className="px-3 py-2">{('modelos' in p && p.modelos) || 'Por defecto'}</td>
                  <td className="px-3 py-2">{describirWebhook('webhook_url' in p ? p.webhook_url : null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
