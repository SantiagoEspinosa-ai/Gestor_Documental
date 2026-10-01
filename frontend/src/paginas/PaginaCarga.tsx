import { AlertTriangle, CheckCircle2, CircleX, Clock, FileUp, Info, LoaderCircle, Lock, Trash2, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { Link, useParams } from 'react-router'
import { listarProcesos, listarTiposDocumentales, obtenerDocumento, obtenerFolio, subirDocumento } from '../api/folios'
import { AvisoSondeoDetenido } from '../componentes/AvisoSondeoDetenido'
import { useRol } from '../componentes/contextoSesion'
import { InsigniaEstado } from '../componentes/Insignias'
import type { EstadoAnalisis, Proceso, ResultadoExpediente, TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_ESTADO_ANALISIS } from '../utilidades/etiquetas'
import { enProceso, tipoEfectivo, tiposRequeridosQueFaltan } from '../utilidades/expediente'
import { MENSAJES_ERROR, mensajeDeError } from '../utilidades/mensajes'
import { firmaDocumentos, useSondeo, type TiemposSondeo } from '../utilidades/sondeo'

const MAX_BYTES = 20 * 1024 * 1024
const ROLES_SUBIR = ['integrador', 'revisor'] // POST /folios/{folio}/documentos

interface EnCola {
  clave: number
  archivo: File
  /** '' = sin declarar: lo detecta el clasificador */
  tipo: string
  error: string | null
  subiendo: boolean
}

function extension(nombre: string): string {
  const i = nombre.lastIndexOf('.')
  return i >= 0 ? nombre.slice(i + 1).toLowerCase() : ''
}

function validar(archivo: File, tipo: string, tipos: TipoDocumental[]): string | null {
  if (archivo.size > MAX_BYTES) return MENSAJES_ERROR.ARCHIVO_DEMASIADO_GRANDE
  const ficha = tipos.find((t) => t.nombre === tipo)
  const permitidos = ficha ? ficha.formatos_permitidos : [...new Set(tipos.flatMap((t) => t.formatos_permitidos))]
  const ext = extension(archivo.name)
  if (permitidos.includes(ext)) return null
  return `Formato ${ext ? `.${ext}` : 'sin extensión'} no permitido${ficha ? ` para ${ficha.nombre_visible}` : ''}. `
    + `Permitidos: ${permitidos.join(', ')}.`
}

const ICONO_ESTADO: Record<EstadoAnalisis, typeof Clock> = {
  pendiente: Clock, procesando: LoaderCircle, completado: CheckCircle2, error: CircleX,
}

export function PaginaCarga({ tiemposSondeo }: { tiemposSondeo?: Partial<TiemposSondeo> }) {
  const { folio = '' } = useParams()
  const rol = useRol()
  const [expediente, setExpediente] = useState<ResultadoExpediente | null>(null)
  const [tipos, setTipos] = useState<TipoDocumental[]>([])
  const [proceso, setProceso] = useState<Proceso | null>(null)
  const [errorCarga, setErrorCarga] = useState<string | null>(null)
  const [cola, setCola] = useState<EnCola[]>([])
  const [subiendo, setSubiendo] = useState(false)
  const [anuncio, setAnuncio] = useState('')
  const [arrastrando, setArrastrando] = useState(false)
  const siguienteClave = useRef(0)

  useEffect(() => {
    const control = new AbortController()
    Promise.all([obtenerFolio(folio, control.signal), listarTiposDocumentales(control.signal), listarProcesos(control.signal)])
      .then(([exp, fichas, procesos]) => {
        setExpediente(exp)
        setTipos(fichas)
        setProceso(procesos.find((p) => p.nombre === exp.proceso) ?? null)
      })
      .catch((causa) => { if (!control.signal.aborted) setErrorCarga(mensajeDeError(causa)) })
    return () => control.abort()
  }, [folio])

  const refrescar = useCallback(async (signal?: AbortSignal) => {
    try {
      setExpediente(await obtenerFolio(folio, signal))
    } catch (causa) {
      if (!signal?.aborted) setErrorCarga(mensajeDeError(causa))
    }
  }, [folio])

  // Sondeo de los documentos pendientes o procesando: 3 s que crecen hasta 15 s, se detiene tras 10 minutos
  // sin cambios y al salir de la pantalla (utilidades/sondeo.ts)
  const enCurso = expediente?.documentos.filter(enProceso) ?? []
  const sondeo = useSondeo({
    activo: enCurso.length > 0,
    firma: firmaDocumentos(expediente?.documentos ?? []),
    tiempos: tiemposSondeo,
    comprobar: async (signal) => {
      const docs = await Promise.all(enCurso.map((d) => obtenerDocumento(d.identificador_unico_documento, signal)))
      const terminados = docs.filter((d) => !enProceso(d))
      setExpediente((e) => e && {
        ...e, documentos: e.documentos.map((d) => docs.find((n) => n.identificador_unico_documento === d.identificador_unico_documento) ?? d),
      })
      if (terminados.length) {
        setAnuncio(terminados.map((d) => `${d.referencia_archivo_original.nombre_archivo}: ${ETIQUETA_ESTADO_ANALISIS[d.estado_analisis].toLowerCase()}`).join('. '))
        await refrescar(signal) // EXP-001 y demas alertas del expediente se recalculan al procesar
      }
    },
  })

  const nombreVisible = (tipo: string | null) => tipos.find((t) => t.nombre === tipo)?.nombre_visible ?? tipo ?? 'Sin tipo'
  const cerrado = expediente !== null && expediente.estado_general !== 'en_revision'
  const puedeSubir = rol !== null && ROLES_SUBIR.includes(rol) && expediente !== null && !cerrado
  const faltan = expediente && proceso ? tiposRequeridosQueFaltan(expediente, proceso) : []
  const aceptados = [...new Set(tipos.flatMap((t) => t.formatos_permitidos))].map((f) => `.${f}`).join(',')

  function anadir(archivos: FileList | File[] | null) {
    if (!archivos || !puedeSubir) return
    const nuevos = Array.from(archivos).map((archivo) => ({
      clave: siguienteClave.current++, archivo, tipo: '', error: validar(archivo, '', tipos), subiendo: false,
    }))
    setCola((c) => [...c, ...nuevos])
    setAnuncio(`${nuevos.length} ${nuevos.length === 1 ? 'archivo añadido' : 'archivos añadidos'} a la cola`)
  }

  function cambiarTipo(clave: number, tipo: string) {
    setCola((c) => c.map((i) => (i.clave === clave ? { ...i, tipo, error: validar(i.archivo, tipo, tipos) } : i)))
  }

  async function subirTodo() {
    setSubiendo(true)
    for (const item of cola.filter((i) => !i.error)) {
      setCola((c) => c.map((i) => (i.clave === item.clave ? { ...i, subiendo: true } : i)))
      try {
        await subirDocumento(folio, item.archivo, item.tipo || undefined)
        setCola((c) => c.filter((i) => i.clave !== item.clave))
      } catch (causa) {
        setCola((c) => c.map((i) => (i.clave === item.clave ? { ...i, subiendo: false, error: mensajeDeError(causa) } : i)))
      }
    }
    await refrescar()
    setAnuncio('Subida terminada: los documentos se están analizando')
    setSubiendo(false)
  }

  function soltar(evento: DragEvent) {
    evento.preventDefault()
    setArrastrando(false)
    anadir(evento.dataTransfer.files)
  }

  if (errorCarga && !expediente) {
    return (
      <section>
        <h1 className="text-xl font-semibold">Carga de documentos</h1>
        <p role="alert" className="mt-2 text-red-700">{errorCarga}</p>
        <Link to="/folios" className="mt-2 inline-block text-blue-700 underline">Volver a los folios</Link>
      </section>
    )
  }
  if (!expediente) return <p role="status" className="text-slate-600">Cargando el folio…</p>

  const validos = cola.filter((i) => !i.error).length
  return (
    <section aria-labelledby="titulo-carga">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="titulo-carga" className="text-xl font-semibold">Carga de documentos — <span className="font-mono">{expediente.folio}</span></h1>
        <InsigniaEstado estado={expediente.estado_general} />
        <Link to={`/folios/${encodeURIComponent(expediente.folio)}`} className="text-sm text-blue-700 underline">Ver expediente</Link>
        <Link to="/folios" className="text-sm text-blue-700 underline">Volver a los folios</Link>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Proceso {expediente.proceso}{expediente.referencia_externa ? ` · Referencia ${expediente.referencia_externa}` : ''}
      </p>

      {cerrado && (
        <p role="status" className="mt-4 flex items-center gap-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
          <Lock className="size-4" aria-hidden /> El folio está {expediente.estado_general}: solo lectura. No se pueden subir documentos.
        </p>
      )}
      {!cerrado && rol !== null && !ROLES_SUBIR.includes(rol) && (
        <p role="status" className="mt-4 flex items-center gap-2 rounded bg-slate-100 px-3 py-2 text-slate-700">
          <Info className="size-4" aria-hidden /> Tu rol puede consultar los documentos, pero no subirlos.
        </p>
      )}

      <div role="status" aria-live="polite" className="mt-4">
        {faltan.length ? (
          <p className="flex items-center gap-2 rounded border border-orange-300 bg-orange-50 px-3 py-2 text-orange-900">
            <AlertTriangle className="size-4" aria-hidden /> Faltan tipos requeridos por el proceso: {faltan.map(nombreVisible).join(', ')}.
          </p>
        ) : (
          <p className="flex items-center gap-2 text-sm text-green-800">
            <CheckCircle2 className="size-4" aria-hidden /> Están todos los tipos requeridos por el proceso.
          </p>
        )}
      </div>

      <div onDragOver={(e) => { e.preventDefault(); if (puedeSubir) setArrastrando(true) }} onDragLeave={() => setArrastrando(false)}
        onDrop={soltar} data-testid="zona-carga" aria-disabled={!puedeSubir} aria-describedby="ayuda-carga"
        className={`mt-4 rounded-lg border-2 border-dashed p-6 text-center ${arrastrando ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white'} ${puedeSubir ? '' : 'opacity-60'}`}>
        <FileUp className="mx-auto size-8 text-slate-500" aria-hidden />
        <p id="ayuda-carga" className="mt-2 text-sm text-slate-600">
          Arrastra aquí los archivos o elígelos. Formatos: {aceptados.replaceAll(',', ', ') || '—'}; máximo 20 MB por archivo.
        </p>
        <label htmlFor="archivos" className="mt-2 block text-sm font-medium">Elegir archivos</label>
        <input id="archivos" type="file" multiple accept={aceptados} disabled={!puedeSubir}
          onChange={(e) => { anadir(e.currentTarget.files); e.currentTarget.value = '' }} className="mx-auto mt-1 block text-sm" />
      </div>

      {cola.length > 0 && (
        <div className="mt-4">
          <h2 className="text-base font-semibold">Por subir</h2>
          <ul className="mt-2 space-y-2">
            {cola.map((item) => (
              <li key={item.clave} className="flex flex-wrap items-center gap-3 rounded border border-slate-200 bg-white px-3 py-2">
                <span className="font-mono text-sm">{item.archivo.name}</span>
                <span className="text-xs text-slate-500">{(item.archivo.size / 1024).toFixed(0)} KB</span>
                <select value={item.tipo} onChange={(e) => cambiarTipo(item.clave, e.target.value)} disabled={item.subiendo}
                  className="rounded border border-slate-300 px-2 py-1 text-sm" aria-label={`Tipo declarado de ${item.archivo.name}`}>
                  <option value="">Sin declarar (se detecta)</option>
                  {tipos.map((t) => <option key={t.nombre} value={t.nombre}>{t.nombre_visible}</option>)}
                </select>
                {item.subiendo && <span role="status" className="text-sm text-slate-600">Subiendo…</span>}
                {item.error && <span role="alert" className="text-sm text-red-700">{item.error}</span>}
                <button type="button" onClick={() => setCola((c) => c.filter((i) => i.clave !== item.clave))} disabled={item.subiendo}
                  aria-label={`Quitar ${item.archivo.name}`} className="ml-auto text-slate-500 hover:text-red-700">
                  <Trash2 className="size-4" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={subirTodo} disabled={!puedeSubir || subiendo || validos === 0}
            className="mt-3 flex items-center gap-1 rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-60">
            <Upload className="size-4" aria-hidden /> {subiendo ? 'Subiendo…' : `Subir ${validos} ${validos === 1 ? 'archivo' : 'archivos'}`}
          </button>
        </div>
      )}

      <h2 className="mt-6 text-base font-semibold">Documentos del folio</h2>
      {sondeo.detenido && <AvisoSondeoDetenido alReanudar={sondeo.reanudar} />}
      {expediente.documentos.length === 0 ? <p className="mt-2 text-sm text-slate-500">Aún no hay documentos.</p> : (
        <table className="mt-2 w-full border-collapse bg-white text-sm">
          <caption className="sr-only">Documentos del folio y estado del análisis</caption>
          <thead className="bg-slate-100 text-left">
            <tr>{['Archivo', 'Tipo', 'Estado', 'Avisos'].map((c) => <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>)}</tr>
          </thead>
          <tbody>
            {expediente.documentos.map((d) => {
              const Icono = ICONO_ESTADO[d.estado_analisis]
              const duplicado = d.alertas_encontradas.find((a) => a.codigo === 'DUP-001')
              const fallo = d.alertas_encontradas.find((a) => a.codigo.startsWith('SYS-'))
              return (
                <tr key={d.identificador_unico_documento} className="border-t border-slate-200">
                  <th scope="row" className="px-3 py-2 text-left font-mono font-normal">{d.referencia_archivo_original.nombre_archivo}</th>
                  <td className="px-3 py-2">{nombreVisible(tipoEfectivo(d))}</td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-1" data-testid={`estado-${d.identificador_unico_documento}`}>
                      <Icono className={`size-4 ${d.estado_analisis === 'procesando' ? 'animate-spin' : ''}`} aria-hidden />
                      {ETIQUETA_ESTADO_ANALISIS[d.estado_analisis]}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {duplicado && (
                      <p className="flex items-center gap-1 text-orange-800">
                        <AlertTriangle className="size-4" aria-hidden /> Duplicado (DUP-001): {duplicado.mensaje}
                      </p>
                    )}
                    {d.estado_analisis === 'error' && (
                      <p className="flex items-center gap-1 text-red-800">
                        <CircleX className="size-4" aria-hidden /> El análisis falló{fallo ? ` (${fallo.codigo}): ${fallo.mensaje}` : ''}
                      </p>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <p role="status" aria-live="polite" className="sr-only" data-testid="anuncio">{anuncio}</p>
    </section>
  )
}
