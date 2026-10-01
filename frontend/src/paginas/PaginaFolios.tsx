import { ChevronLeft, ChevronRight, Plus, Upload } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { listarFolios, listarProcesos } from '../api/folios'
import { useRol } from '../componentes/contextoSesion'
import { FormularioNuevoFolio } from '../componentes/FormularioNuevoFolio'
import { IndicadorBloqueantes, InsigniaEstado, TextoRecomendacion } from '../componentes/Insignias'
import { SoloRol } from '../componentes/SoloRol'
import { ESTADOS_GENERALES, type EstadoGeneral, type PaginaFolios as Pagina, type Proceso } from '../tipos/contrato'
import { ETIQUETA_ESTADO_GENERAL, fechaHora } from '../utilidades/etiquetas'
import { mensajeDeError } from '../utilidades/mensajes'

const ROLES_LISTA = ['revisor', 'admin'] as const // GET /folios
const ROLES_CREAR = ['integrador', 'revisor'] as const // POST /folios

export function PaginaFolios({ tamanoPagina = 20 }: { tamanoPagina?: number }) {
  const rol = useRol()
  const puedeListar = rol !== null && (ROLES_LISTA as readonly string[]).includes(rol)
  const [procesos, setProcesos] = useState<Proceso[]>([])
  const [filtroProceso, setFiltroProceso] = useState('')
  const [filtroEstado, setFiltroEstado] = useState<EstadoGeneral | ''>('')
  const [pagina, setPagina] = useState(1)
  // Resultado de la ultima consulta y los filtros con que se pidio: cargando = no coinciden
  const [resultado, setResultado] = useState<{ clave: string; datos?: Pagina; error?: string } | null>(null)
  const [creando, setCreando] = useState(false)
  const refBotonNuevo = useRef<HTMLButtonElement>(null)
  const filtros = { proceso: filtroProceso || undefined, estado_general: filtroEstado || undefined, pagina, tamano_pagina: tamanoPagina }
  const clave = JSON.stringify(filtros)
  const cargando = puedeListar && resultado?.clave !== clave
  const datos = resultado?.datos ?? null
  const error = resultado?.clave === clave ? resultado.error ?? null : null

  useEffect(() => {
    const control = new AbortController()
    listarProcesos(control.signal).then(setProcesos).catch(() => { /* los filtros quedan con "Todos" */ })
    return () => control.abort()
  }, [])

  useEffect(() => {
    if (!puedeListar) return
    const control = new AbortController()
    listarFolios(JSON.parse(clave), control.signal)
      .then((datosNuevos) => setResultado({ clave, datos: datosNuevos }))
      .catch((causa) => {
        if (!control.signal.aborted) setResultado((r) => ({ clave, datos: r?.datos, error: mensajeDeError(causa) }))
      })
    return () => control.abort()
  }, [puedeListar, clave])

  const paginas = datos ? Math.max(1, Math.ceil(datos.total / datos.tamano_pagina)) : 1
  const cerrarFormulario = () => {
    setCreando(false)
    refBotonNuevo.current?.focus()
  }

  return (
    <section aria-labelledby="titulo-folios">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="titulo-folios" className="text-xl font-semibold">Folios</h1>
        <SoloRol roles={ROLES_CREAR}>
          <button ref={refBotonNuevo} type="button" onClick={() => setCreando((c) => !c)} aria-expanded={creando} aria-controls="nuevo-folio"
            className="flex items-center gap-1 rounded bg-slate-800 px-3 py-1.5 text-white">
            <Plus className="size-4" aria-hidden /> Nuevo folio
          </button>
        </SoloRol>
      </div>
      {creando && <FormularioNuevoFolio procesos={procesos} onCancelar={cerrarFormulario} />}

      {!puedeListar ? <AbrirFolio /> : (
        <>
          <form className="mt-4 flex flex-wrap gap-4" aria-label="Filtros" onSubmit={(e) => e.preventDefault()}>
            <div>
              <label htmlFor="filtro-proceso" className="block text-sm text-slate-700">Proceso</label>
              <select id="filtro-proceso" value={filtroProceso} onChange={(e) => { setFiltroProceso(e.target.value); setPagina(1) }}
                className="mt-1 rounded border border-slate-300 px-2 py-1.5">
                <option value="">Todos</option>
                {procesos.map((p) => <option key={p.nombre} value={p.nombre}>{p.nombre}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="filtro-estado" className="block text-sm text-slate-700">Estado</label>
              <select id="filtro-estado" value={filtroEstado} onChange={(e) => { setFiltroEstado(e.target.value as EstadoGeneral | ''); setPagina(1) }}
                className="mt-1 rounded border border-slate-300 px-2 py-1.5">
                <option value="">Todos</option>
                {ESTADOS_GENERALES.map((e) => <option key={e} value={e}>{ETIQUETA_ESTADO_GENERAL[e]}</option>)}
              </select>
            </div>
          </form>

          {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse bg-white text-sm" aria-busy={cargando}>
              <caption className="sr-only">Folios, del más reciente al más antiguo</caption>
              <thead className="bg-slate-100 text-left">
                <tr>
                  {['Folio', 'Referencia', 'Proceso', 'Fecha de solicitud', 'Estado', 'Recomendación', 'Documentos', 'Bloqueantes', 'Acciones']
                    .map((c) => <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {datos?.elementos.map((f) => {
                  return (
                    <tr key={f.folio} className="border-t border-slate-200">
                      <th scope="row" className="px-3 py-2 text-left font-mono font-normal">
                        <Link to={`/folios/${f.folio}`} className="text-blue-700 underline">{f.folio}</Link>
                      </th>
                      <td className="px-3 py-2 font-mono">{f.referencia_externa ?? '—'}</td>
                      <td className="px-3 py-2">{f.proceso}</td>
                      <td className="px-3 py-2">{fechaHora(f.fecha_solicitud)}</td>
                      <td className="px-3 py-2"><InsigniaEstado estado={f.estado_general} /></td>
                      <td className="px-3 py-2"><TextoRecomendacion valor={f.recomendacion_global} /></td>
                      <td className="px-3 py-2">{f.n_documentos}</td>
                      <td className="px-3 py-2"><IndicadorBloqueantes n={f.n_bloqueantes_sin_resolver} /></td>
                      <td className="px-3 py-2">
                        <Link to={`/folios/${f.folio}/carga`} className="inline-flex items-center gap-1 text-blue-700 underline"
                          aria-label={`Cargar documentos en ${f.folio}`}>
                          <Upload className="size-4" aria-hidden /> Cargar
                        </Link>
                      </td>
                    </tr>
                  )
                })}
                {datos && datos.elementos.length === 0 && (
                  <tr><td colSpan={9} className="px-3 py-6 text-center text-slate-500">No hay folios con esos filtros.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {cargando && <p role="status" className="mt-2 text-sm text-slate-600">Cargando folios…</p>}
          {datos && (
            <nav aria-label="Paginación" className="mt-3 flex items-center gap-3 text-sm">
              <button type="button" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}
                className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 disabled:opacity-50">
                <ChevronLeft className="size-4" aria-hidden /> Anterior
              </button>
              <span aria-live="polite">Página {pagina} de {paginas} ({datos.total} folios)</span>
              <button type="button" disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}
                className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 disabled:opacity-50">
                Siguiente <ChevronRight className="size-4" aria-hidden />
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  )
}

/** El integrador no puede listar folios (GET /folios es de revisor y admin): abre uno por su numero */
function AbrirFolio() {
  const navegar = useNavigate()
  const [folio, setFolio] = useState('')
  const abrir = (e: FormEvent) => {
    e.preventDefault()
    if (folio.trim()) navegar(`/folios/${folio.trim().toUpperCase()}/carga`)
  }
  return (
    <form onSubmit={abrir} className="mt-4 rounded border border-slate-200 bg-white p-4" aria-labelledby="titulo-abrir">
      <h2 id="titulo-abrir" className="text-base font-semibold">Abrir un folio</h2>
      <p className="text-sm text-slate-600">Tu rol no puede ver la lista de folios. Abre uno por su número para cargar documentos.</p>
      <label htmlFor="abrir-folio" className="mt-2 block text-sm text-slate-700">Número de folio</label>
      <p id="formato-folio" className="text-xs text-slate-500">Formato: prefijo del proceso, año y secuencia (p. ej. ONB-AAAA-NNNNNN).</p>
      <div className="mt-1 flex gap-2">
        <input id="abrir-folio" value={folio} onChange={(e) => setFolio(e.target.value)} placeholder="PREFIJO-AAAA-NNNNNN" aria-describedby="formato-folio"
          className="rounded border border-slate-300 px-2 py-1.5 font-mono" />
        <button type="submit" disabled={!folio.trim()} className="rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-60">Abrir</button>
      </div>
    </form>
  )
}
