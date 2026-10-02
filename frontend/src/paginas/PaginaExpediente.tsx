import { CheckCircle2, CircleX, Clock, LoaderCircle, Lock, Upload, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ErrorApi } from '../api/cliente'
import { listarTiposDocumentales, obtenerFolio } from '../api/folios'
import {
  confirmarClasificacion, corregirDatos, decidir, resolverAlertaDocumento, resolverAlertaExpediente,
} from '../api/revision'
import { ConfirmarClasificacion, EditorCampo, PanelDecision, RevisarAlerta } from '../componentes/AccionesRevisor'
import { useRol } from '../componentes/contextoSesion'
import { AvisoSondeoDetenido } from '../componentes/AvisoSondeoDetenido'
import { DetalleDocumento } from '../componentes/DetalleDocumento'
import { IndicadorBloqueantes, InsigniaEstado, TextoRecomendacion } from '../componentes/Insignias'
import { ListaAlertas } from '../componentes/ListaAlertas'
import { ResumenExpediente } from '../componentes/ResumenExpediente'
import type { EstadoAnalisis, ResultadoDocumento, ResultadoExpediente, TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_DECISION, ETIQUETA_ESTADO_ANALISIS, fechaHora } from '../utilidades/etiquetas'
import { alertasQueBloquean, enProceso, nombreTipo, tipoEfectivo, tipoExtraccion } from '../utilidades/expediente'
import { mensajeDeError } from '../utilidades/mensajes'
import { firmaDocumentos, useSondeo, type TiemposSondeo } from '../utilidades/sondeo'
import { formatearValor, nombreCampo } from '../utilidades/valores'

const ROLES_ORIGINAL = ['revisor', 'admin'] // GET /documentos/{id}/original

const ICONO_ESTADO: Record<EstadoAnalisis, typeof Clock> = {
  pendiente: Clock, procesando: LoaderCircle, completado: CheckCircle2, error: CircleX,
}

/** Vista de lectura del expediente (diapositiva 8): cabecera, documentos, documento seleccionado y alertas */
export function PaginaExpediente({ tiemposSondeo }: { tiemposSondeo?: Partial<TiemposSondeo> }) {
  const { folio = '' } = useParams()
  const rol = useRol()
  const [cargado, setCargado] = useState<ResultadoExpediente | null>(null)
  const [fichas, setFichas] = useState<TipoDocumental[]>([])
  const [fallo, setFallo] = useState<{ folio: string; mensaje: string } | null>(null)
  const [seleccionado, setSeleccionado] = useState<string | null>(null)
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  // Al cambiar de folio en la ruta no se muestra el anterior mientras llega el nuevo
  const expediente = cargado?.folio === folio ? cargado : null
  const error = fallo?.folio === folio ? fallo.mensaje : null

  useEffect(() => {
    const control = new AbortController()
    Promise.all([obtenerFolio(folio, control.signal), listarTiposDocumentales(control.signal)])
      .then(([exp, tipos]) => {
        setCargado(exp)
        setFichas(tipos)
      })
      .catch((causa) => { if (!control.signal.aborted) setFallo({ folio, mensaje: mensajeDeError(causa) }) })
    return () => control.abort()
  }, [folio])

  const refrescar = useCallback(async (signal?: AbortSignal) => {
    try {
      setCargado(await obtenerFolio(folio, signal))
    } catch (causa) {
      if (!signal?.aborted) setFallo({ folio, mensaje: mensajeDeError(causa) })
    }
  }, [folio])

  /**
   * Ejecuta una accion del revisor y refresca con la respuesta del endpoint. Tras una accion de
   * documento se vuelve a pedir el expediente (recomendacion global, CMP-001 y EXP-001 pueden cambiar).
   * Un 409 (DOCUMENTO_EN_PROCESO, DOCUMENTO_CON_ERROR, FOLIO_CERRADO, DECISION_BLOQUEADA) significa que
   * la vista estaba desfasada: se muestra el motivo y se recarga el expediente.
   */
  async function ejecutar<T>(accion: () => Promise<T>, aplicar: (respuesta: T) => void, exito: string, recargar = false) {
    setOcupado(true)
    setAviso(null)
    try {
      aplicar(await accion())
      if (recargar) await refrescar()
      setAviso({ tipo: 'ok', texto: exito })
      return true
    } catch (causa) {
      setAviso({ tipo: 'error', texto: `No se pudo completar la acción: ${mensajeDeError(causa)}` })
      if (causa instanceof ErrorApi && causa.estado === 409) await refrescar()
      return false
    } finally {
      setOcupado(false)
    }
  }
  const aplicarDocumento = (nuevo: ResultadoDocumento) => setCargado((e) => e && {
    ...e, documentos: e.documentos.map((d) => (d.identificador_unico_documento === nuevo.identificador_unico_documento ? nuevo : d)),
  })

  // Sondeo del expediente mientras quede algun documento pendiente o procesando: 3 s que crecen hasta
  // 15 s y se detiene tras 10 minutos sin cambios (utilidades/sondeo.ts)
  const sondeo = useSondeo({
    activo: expediente?.documentos.some(enProceso) ?? false,
    firma: firmaDocumentos(expediente?.documentos ?? []),
    comprobar: refrescar,
    tiempos: tiemposSondeo,
  })

  if (error && !expediente) {
    return (
      <section>
        <h1 className="text-xl font-semibold">Expediente {folio}</h1>
        <p role="alert" className="mt-2 text-red-700">{error}</p>
        <Link to="/folios" className="mt-2 inline-block text-blue-700 underline">Volver a los folios</Link>
      </section>
    )
  }
  if (!expediente) return <p role="status" className="text-slate-600">Cargando el expediente…</p>

  const doc = expediente.documentos.find((d) => d.identificador_unico_documento === seleccionado) ?? expediente.documentos[0]
  // "Tipo no reconocido" para `desconocido` (ADR-009); "Sin tipo" si no hay ninguno
  const nombreVisible = (tipo: string | null) => nombreTipo(tipo, fichas, 'Sin tipo')
  const nombreDocumento = (id: string) => {
    const d = expediente.documentos.find((x) => x.identificador_unico_documento === id)
    return d ? `${nombreVisible(tipoEfectivo(d))} (${d.referencia_archivo_original.nombre_archivo})` : id
  }
  const cerrado = expediente.estado_general !== 'en_revision'
  const bloqueantes = alertasQueBloquean(expediente)
  // Acciones solo para el revisor y con el folio abierto; la API vuelve a comprobarlo
  const puedeActuar = rol === 'revisor' && !cerrado
  const docAnalizado = doc?.estado_analisis === 'completado' // corregir y reclasificar: ni en curso ni en error
  const fichaDoc = doc ? fichas.find((t) => t.nombre === tipoExtraccion(doc)) : undefined
  const idDoc = doc?.identificador_unico_documento ?? ''

  return (
    <section aria-labelledby="titulo-expediente">
      <header className="rounded border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 id="titulo-expediente" className="text-xl font-semibold">Expediente <span className="font-mono">{expediente.folio}</span></h1>
          <InsigniaEstado estado={expediente.estado_general} />
          <Link to={`/folios/${encodeURIComponent(expediente.folio)}/carga`} className="inline-flex items-center gap-1 text-sm text-blue-700 underline">
            <Upload className="size-4" aria-hidden /> Carga de documentos
          </Link>
          <Link to="/folios" className="text-sm text-blue-700 underline">Volver a los folios</Link>
          {expediente.ruta_resumen_md && <ResumenExpediente folio={expediente.folio} />}
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
          <div><dt className="text-slate-600">Referencia</dt><dd className="font-mono">{expediente.referencia_externa ?? '—'}</dd></div>
          <div><dt className="text-slate-600">Fecha de solicitud</dt><dd>{fechaHora(expediente.fecha_solicitud)}</dd></div>
          <div><dt className="text-slate-600">Proceso</dt><dd>{expediente.proceso}</dd></div>
          <div><dt className="text-slate-600">Recomendación global</dt><dd><TextoRecomendacion valor={expediente.recomendacion_global} /></dd></div>
        </dl>
        {cerrado && expediente.decision_humana && (
          <div role="status" className="mt-3 flex items-start gap-2 rounded border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
            <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p>
              <span className="font-medium">Decisión: {ETIQUETA_DECISION[expediente.decision_humana]}</span>
              {expediente.comentario_decision && <> · “{expediente.comentario_decision}”</>}
              {' · '}{expediente.usuario_decision ?? '—'} · {fechaHora(expediente.fecha_decision)}. Folio cerrado: solo lectura.
            </p>
          </div>
        )}
      </header>

      {sondeo.detenido && <AvisoSondeoDetenido alReanudar={sondeo.reanudar} />}
      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} data-testid="aviso"
          className={`mt-3 rounded px-3 py-2 text-sm ${aviso.tipo === 'error' ? 'border border-red-300 bg-red-50 text-red-900' : 'bg-green-50 text-green-900'}`}>
          {aviso.texto}
        </p>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)_20rem]">
        <nav aria-label="Documentos del folio">
          <h2 className="text-sm font-semibold">Documentos ({expediente.documentos.length})</h2>
          {expediente.documentos.length === 0 && <p className="mt-1 text-sm text-slate-500">Aún no hay documentos.</p>}
          <ul className="mt-1 space-y-1">
            {expediente.documentos.map((d) => {
              const Icono = ICONO_ESTADO[d.estado_analisis]
              const activo = d === doc
              return (
                <li key={d.identificador_unico_documento}>
                  <button type="button" onClick={() => setSeleccionado(d.identificador_unico_documento)} aria-current={activo ? 'true' : undefined}
                    className={`w-full rounded border px-2 py-1.5 text-left text-sm ${activo ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
                    <span className="block font-medium">{nombreVisible(tipoEfectivo(d))}</span>
                    <span className="block truncate font-mono text-xs text-slate-600">{d.referencia_archivo_original.nombre_archivo}</span>
                    <span className="mt-0.5 inline-flex items-center gap-1 text-xs" data-testid={`estado-${d.identificador_unico_documento}`}>
                      <Icono className={`size-3.5 ${d.estado_analisis === 'procesando' ? 'animate-spin' : ''}`} aria-hidden />
                      {ETIQUETA_ESTADO_ANALISIS[d.estado_analisis]}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        <div>
          {doc
            ? <DetalleDocumento key={doc.identificador_unico_documento} doc={doc} fichas={fichas}
                puedeVerOriginal={rol !== null && ROLES_ORIGINAL.includes(rol)}
                accionesClasificacion={puedeActuar && docAnalizado ? (
                  <ConfirmarClasificacion fichas={fichas} actual={tipoExtraccion(doc)} deshabilitado={ocupado}
                    alConfirmar={(tipo) => ejecutar(() => confirmarClasificacion(idDoc, { tipo_documental: tipo }), aplicarDocumento,
                      'Clasificación confirmada.', true)} />
                ) : undefined}
                celdaValor={puedeActuar && docAnalizado ? (campo, contenido) => (
                  <EditorCampo campo={campo} valor={doc.datos_extraidos[campo]} tipo={fichaDoc?.campos[campo]?.tipo}
                    obligatorio={fichaDoc?.campos[campo]?.obligatorio ?? false} deshabilitado={ocupado}
                    alGuardar={(valor) => ejecutar(() => corregirDatos(idDoc, { [campo]: valor }), aplicarDocumento,
                      `${nombreCampo(campo)} corregido.`, true)}>
                    {contenido}
                  </EditorCampo>
                ) : undefined} />
            : <p className="text-sm text-slate-500">Selecciona un documento cuando se haya subido alguno.</p>}
        </div>

        <aside aria-label="Alertas y resultado" className="space-y-4">
          <section aria-label="Resultado global" className="rounded border border-slate-200 bg-white p-3 text-sm">
            <h2 className="text-sm font-semibold">Resultado global</h2>
            <p className="mt-1">Recomendación: <TextoRecomendacion valor={expediente.recomendacion_global} /></p>
            <p className="mt-1 flex items-center gap-2">Bloqueantes sin descartar: <IndicadorBloqueantes n={bloqueantes.length} /></p>
            <p className="mt-1 text-xs text-slate-500">La IA recomienda; la decisión final es del revisor.</p>
          </section>
          {puedeActuar && (
            <PanelDecision bloqueantes={bloqueantes} enCurso={expediente.documentos.some(enProceso)} deshabilitado={ocupado}
              alDecidir={(decision, comentario) => ejecutar(
                () => decidir(expediente.folio, { decision, ...(comentario ? { comentario } : {}) }), setCargado,
                `Folio ${decision === 'aprobar' ? 'aprobado' : 'rechazado'}.`)} />
          )}
          {doc && (
            <ListaAlertas titulo="Alertas del documento seleccionado" alertas={doc.alertas_encontradas}
              acciones={puedeActuar && !enProceso(doc) ? (a) => (
                <RevisarAlerta alerta={a} deshabilitado={ocupado}
                  alResolver={(aplica, comentario) => ejecutar(
                    () => resolverAlertaDocumento(idDoc, a.id!, { aplica, ...(comentario ? { comentario } : {}) }), aplicarDocumento,
                    `Alerta ${a.codigo} revisada.`, true)} />
              ) : undefined} />
          )}
          <ListaAlertas titulo="Alertas del expediente" alertas={expediente.alertas_expediente}
            acciones={puedeActuar ? (a) => (
              <RevisarAlerta alerta={a} deshabilitado={ocupado}
                alResolver={(aplica, comentario) => ejecutar(
                  () => resolverAlertaExpediente(expediente.folio, a.id!, { aplica, ...(comentario ? { comentario } : {}) }), setCargado,
                  `Alerta ${a.codigo} revisada.`)} />
            ) : undefined} />
          <section aria-label="Comparaciones entre documentos">
            <h3 className="text-sm font-semibold">Comparaciones</h3>
            {expediente.comparaciones.length === 0 && <p className="mt-1 text-sm text-slate-500">Sin comparaciones.</p>}
            <ul className="mt-1 space-y-2">
              {expediente.comparaciones.map((c) => (
                <li key={c.campo} className="rounded border border-slate-200 bg-white px-2 py-1.5 text-sm">
                  <p className={`flex items-center gap-1 font-medium ${c.coincide ? 'text-green-800' : 'text-orange-900'}`}>
                    {c.coincide ? <CheckCircle2 className="size-4" aria-hidden /> : <XCircle className="size-4" aria-hidden />}
                    {nombreCampo(c.campo)}: {c.coincide ? 'coincide' : 'no coincide'}
                  </p>
                  <dl className="mt-1 space-y-0.5 text-xs">
                    {Object.entries(c.valores).map(([id, valor]) => (
                      <div key={id}><dt className="text-slate-600">{nombreDocumento(id)}</dt><dd className="font-mono">{formatearValor(valor)}</dd></div>
                    ))}
                  </dl>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </section>
  )
}
