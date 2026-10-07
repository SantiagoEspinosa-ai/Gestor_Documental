import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listarAuditoria } from '../api/auditoria'
import { listarTiposDocumentales } from '../api/folios'
import type { EntradaAuditoria, PaginaAuditoria as Pagina } from '../tipos/contrato'
import { describirDetalle, etiquetaAccion, type NombresTipos } from '../utilidades/auditoria'
import { fechaHoraCompleta } from '../utilidades/etiquetas'
import { mensajeDeError } from '../utilidades/mensajes'

// GET /auditoria (ADR-008): 50 por defecto, 1..100. Filtros y pagina en la URL (?folio=&pagina=&tamano_pagina=)
const TAMANO_POR_DEFECTO = 50
const TAMANOS = [20, 50, 100]

export function PaginaAuditoria() {
  const [parametros, setParametros] = useSearchParams()
  const folio = parametros.get('folio') ?? ''
  const pagina = parametros.get('pagina') ?? '1'
  const tamano = parametros.get('tamano_pagina') ?? String(TAMANO_POR_DEFECTO)
  const clave = JSON.stringify({ folio, pagina, tamano })
  const [resultado, setResultado] = useState<{ clave: string; datos?: Pagina; error?: string } | null>(null)
  const [tipos, setTipos] = useState<NombresTipos>({})
  const [folioEscrito, setFolioEscrito] = useState(folio)
  const cargando = resultado?.clave !== clave
  const datos = resultado?.datos ?? null
  const error = resultado?.clave === clave ? resultado.error ?? null : null

  useEffect(() => {
    const control = new AbortController()
    listarTiposDocumentales(control.signal)
      .then((lista) => setTipos(Object.fromEntries(lista.map((t) => [t.nombre, t.nombre_visible]))))
      .catch(() => { /* sin nombres visibles: se muestra el nombre tecnico legible */ })
    return () => control.abort()
  }, [])

  useEffect(() => {
    const control = new AbortController()
    const { folio: f, pagina: p, tamano: t } = JSON.parse(clave) as { folio: string; pagina: string; tamano: string }
    // Se envian tal cual: si la URL trae un valor fuera de rango, la API responde 422 y se muestra
    listarAuditoria({ folio: f || undefined, pagina: Number(p), tamano_pagina: Number(t) }, control.signal)
      .then((datosNuevos) => setResultado({ clave, datos: datosNuevos }))
      .catch((causa) => {
        if (!control.signal.aborted) setResultado({ clave, error: mensajeDeError(causa) })
      })
    return () => control.abort()
  }, [clave])

  const cambiar = (cambios: Record<string, string | null>) => {
    const nuevos = new URLSearchParams(parametros)
    for (const [k, v] of Object.entries(cambios)) {
      if (v === null || v === '') nuevos.delete(k)
      else nuevos.set(k, v)
    }
    setParametros(nuevos)
  }
  const filtrar = (e: FormEvent) => {
    e.preventDefault()
    cambiar({ folio: folioEscrito.trim().toUpperCase(), pagina: null })
  }
  const quitarFiltro = () => {
    setFolioEscrito('')
    cambiar({ folio: null, pagina: null })
  }

  const paginas = datos ? Math.max(1, Math.ceil(datos.total / datos.tamano_pagina)) : 1
  const paginaActual = datos?.pagina ?? Number(pagina)

  return (
    <section aria-labelledby="titulo-auditoria">
      <h1 id="titulo-auditoria" className="text-xl font-semibold">Auditoría</h1>
      <p className="text-sm text-slate-600">Registro de acciones, del más reciente al más antiguo.</p>

      <div className="mt-4 flex flex-wrap items-end gap-4">
        <form onSubmit={filtrar} role="search" aria-label="Filtrar la auditoría por folio" className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="filtro-folio-auditoria" className="block text-sm text-slate-700">Folio</label>
            <input id="filtro-folio-auditoria" value={folioEscrito} onChange={(e) => setFolioEscrito(e.target.value)}
              placeholder="PREFIJO-AAAA-NNNNNN" className="mt-1 rounded border border-slate-300 px-2 py-1.5 font-mono" />
          </div>
          <button type="submit" className="flex items-center gap-1 rounded bg-q-slate px-3 py-1.5 text-white">
            <Search className="size-4" aria-hidden /> Filtrar
          </button>
          {folio && (
            <button type="button" onClick={quitarFiltro} className="flex items-center gap-1 rounded border border-slate-300 px-3 py-1.5">
              <X className="size-4" aria-hidden /> Quitar filtro
            </button>
          )}
        </form>
        <div>
          <label htmlFor="tamano-auditoria" className="block text-sm text-slate-700">Entradas por página</label>
          <select id="tamano-auditoria" value={tamano} onChange={(e) => cambiar({ tamano_pagina: e.target.value, pagina: null })}
            className="mt-1 rounded border border-slate-300 px-2 py-1.5">
            {(TAMANOS.includes(Number(tamano)) ? TAMANOS : [...TAMANOS, Number(tamano)]).map((t) => (
              <option key={t} value={String(t)}>{t}</option>
            ))}
          </select>
        </div>
      </div>
      {folio && <p className="mt-2 text-sm text-slate-600">Mostrando solo el folio <span className="font-mono">{folio}</span>.</p>}

      {error && (
        <div role="alert" className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-red-800">
          <p>{error}</p>
          <Link to="/auditoria" onClick={() => setFolioEscrito('')} className="mt-1 inline-block text-q-slate underline hover:text-q-orange-700">
            Volver a la auditoría sin filtros
          </Link>
        </div>
      )}
      {!error && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse bg-white text-sm" aria-busy={cargando}>
            <caption className="sr-only">Registro de auditoría, del más reciente al más antiguo</caption>
            <thead className="bg-slate-100 text-left">
              <tr>
                {['Fecha', 'Usuario', 'Acción', 'Folio', 'Documento', 'Detalle', 'Modelo'].map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {datos?.elementos.map((e) => <FilaAuditoria key={e.id} entrada={e} tipos={tipos} />)}
              {datos && datos.elementos.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                  {folio ? `No hay entradas de auditoría del folio ${folio}.` : 'No hay entradas de auditoría.'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {cargando && <p role="status" className="mt-2 text-sm text-slate-600">Cargando auditoría…</p>}
      {datos && !error && (
        <nav aria-label="Paginación" className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <button type="button" disabled={paginaActual <= 1} onClick={() => cambiar({ pagina: String(paginaActual - 1) })}
            className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 disabled:opacity-50">
            <ChevronLeft className="size-4" aria-hidden /> Anterior
          </button>
          <span aria-live="polite">Página {paginaActual} de {paginas} ({datos.total} {datos.total === 1 ? 'entrada' : 'entradas'})</span>
          <button type="button" disabled={paginaActual >= paginas} onClick={() => cambiar({ pagina: String(paginaActual + 1) })}
            className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 disabled:opacity-50">
            Siguiente <ChevronRight className="size-4" aria-hidden />
          </button>
        </nav>
      )}
    </section>
  )
}

function FilaAuditoria({ entrada: e, tipos }: { entrada: EntradaAuditoria; tipos: NombresTipos }) {
  const detalle = describirDetalle(e, tipos)
  return (
    <tr className="border-t border-slate-200 align-top">
      <td className="whitespace-nowrap px-3 py-2"><time dateTime={e.creado_en}>{fechaHoraCompleta(e.creado_en)}</time></td>
      <td className="px-3 py-2">{e.usuario ?? <span className="text-slate-500">Sistema</span>}</td>
      <th scope="row" className="px-3 py-2 text-left font-normal">{etiquetaAccion(e.accion)}</th>
      <td className="whitespace-nowrap px-3 py-2 font-mono">
        {e.folio ? <Link to={`/folios/${e.folio}`} className="text-q-slate underline hover:text-q-orange-700">{e.folio}</Link> : '—'}
      </td>
      <td className="px-3 py-2 font-mono text-xs">
        {e.documento_id ? <span title={e.documento_id}>{e.documento_id.slice(0, 8)}…</span> : '—'}
      </td>
      <td className="px-3 py-2">
        {detalle.length === 0 ? '—' : detalle.length === 1 ? detalle[0] : (
          <ul className="list-none space-y-0.5">{detalle.map((d) => <li key={d}>{d}</li>)}</ul>
        )}
      </td>
      <td className="px-3 py-2 text-xs">
        {e.modelo || e.version_prompt ? [e.modelo, e.version_prompt].filter(Boolean).join(' · ') : '—'}
      </td>
    </tr>
  )
}
