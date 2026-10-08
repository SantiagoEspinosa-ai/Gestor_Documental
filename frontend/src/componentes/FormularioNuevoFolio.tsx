import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { crearFolio } from '../api/folios'
import type { Proceso } from '../tipos/contrato'
import { mensajeDeError } from '../utilidades/mensajes'

interface Props {
  procesos: Proceso[]
  onCancelar: () => void
}

/** POST /folios -> 201 y lleva a la carga de documentos del folio nuevo */
export function FormularioNuevoFolio({ procesos, onCancelar }: Props) {
  const navegar = useNavigate()
  const [proceso, setProceso] = useState(procesos.length === 1 ? procesos[0].nombre : '')
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const refProceso = useRef<HTMLSelectElement>(null)

  useEffect(() => refProceso.current?.focus(), [])

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const { folio } = await crearFolio({ proceso, ...(referencia.trim() ? { referencia_externa: referencia.trim() } : {}) })
      navegar(`/folios/${folio}/carga`)
    } catch (causa) {
      setError(mensajeDeError(causa))
      setEnviando(false)
    }
  }

  return (
    <form id="nuevo-folio" onSubmit={enviar} aria-labelledby="titulo-nuevo-folio" aria-busy={enviando}
      className="mt-4 flex flex-wrap items-end gap-3 rounded border border-slate-200 bg-white p-4"
      onKeyDown={(e) => { if (e.key === 'Escape') onCancelar() }}>
      <h2 id="titulo-nuevo-folio" className="w-full text-base font-semibold">Nuevo folio</h2>
      <div>
        <label htmlFor="nuevo-proceso" className="block text-sm text-slate-700">Proceso</label>
        <select id="nuevo-proceso" ref={refProceso} required value={proceso} onChange={(e) => setProceso(e.target.value)}
          className="mt-1 rounded border border-slate-300 px-2 py-1.5">
          <option value="" disabled>Elige un proceso</option>
          {procesos.map((p) => <option key={p.nombre} value={p.nombre}>{p.nombre} ({p.prefijo_folio})</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="nueva-referencia" className="block text-sm text-slate-700">Referencia externa (opcional)</label>
        <input id="nueva-referencia" maxLength={100} value={referencia} onChange={(e) => setReferencia(e.target.value)}
          aria-describedby="ayuda-referencia" className="mt-1 rounded border border-slate-300 px-2 py-1.5" />
        <p id="ayuda-referencia" className="text-xs text-slate-500">Identificador del sistema integrador, nunca un nombre.</p>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={!proceso || enviando} className="rounded bg-q-slate px-3 py-1.5 text-white disabled:opacity-60">
          {enviando ? 'Creando…' : 'Crear folio'}
        </button>
        <button type="button" onClick={onCancelar} className="rounded border border-slate-300 px-3 py-1.5">Cancelar</button>
      </div>
      {error && <p role="alert" className="w-full text-sm text-red-700">{error}</p>}
    </form>
  )
}
