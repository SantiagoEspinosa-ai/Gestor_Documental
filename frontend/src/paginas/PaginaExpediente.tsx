import { AlertTriangle, ArrowLeft, CheckCircle2, Lock } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ErrorApi } from '../api/cliente'
import { listarTiposDocumentales, obtenerFolio } from '../api/folios'
import {
  confirmarClasificacion, corregirDatos, decidir, resolverAlertaDocumento, resolverAlertaExpediente, restaurarDocumento,
  retirarDocumento,
} from '../api/revision'
import { ConfirmarClasificacion, EditorCampo, PanelDecision, RevisarAlerta } from '../componentes/AccionesRevisor'
import { AvisoSondeoDetenido } from '../componentes/AvisoSondeoDetenido'
import { CabeceraExpediente } from '../componentes/CabeceraExpediente'
import { ComparacionesExpediente } from '../componentes/ComparacionesExpediente'
import { useRol, useSesion } from '../componentes/contextoSesion'
import { DetalleDocumento } from '../componentes/DetalleDocumento'
import { ListaAlertas } from '../componentes/ListaAlertas'
import { PestanaResumen } from '../componentes/PestanaResumen'
import { RetirarDocumento } from '../componentes/RetirarDocumento'
import { LeyendaSemaforo } from '../componentes/Semaforo'
import { TarjetaDocumento } from '../componentes/TarjetaDocumento'
import type { ResultadoDocumento, ResultadoExpediente, Rol, TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_DECISION, fechaHora } from '../utilidades/etiquetas'
import { alertasQueBloquean, cuentaEnElFolio, enProceso, tipoExtraccion } from '../utilidades/expediente'
import { mensajeDeError } from '../utilidades/mensajes'
import { rutaPestana } from '../utilidades/navegacion'
import { hayBloqueantesConfirmadas, pendientesDeRevisar } from '../utilidades/semaforo'
import { firmaDocumentos, useSondeo, type TiemposSondeo } from '../utilidades/sondeo'
import { nombreCampo } from '../utilidades/valores'

const ROLES_ORIGINAL: readonly Rol[] = ['revisor', 'admin'] // GET /documentos/{id}/original
const ROLES_RETIRAR: readonly Rol[] = ['revisor'] // POST /documentos/{id}/retirar y /restaurar (ADR-013): como las demas acciones de revision
const ROLES_SUBIR: readonly Rol[] = ['integrador', 'revisor'] // POST /folios/{folio}/documentos ("Volver a subir")

/**
 * Expediente de un folio, pensado para el revisor: pestanas Documentos (rejilla con semaforo, comparaciones,
 * alertas del expediente y la decision al final), Cargar documentos (PaginaCarga) y Resumen. El detalle de un
 * documento se abre en la misma pestana con ?doc=; el Resumen, con ?pestana=resumen.
 */
export function PaginaExpediente({ tiemposSondeo }: { tiemposSondeo?: Partial<TiemposSondeo> }) {
  const { folio = '' } = useParams()
  const [parametros] = useSearchParams()
  const rol = useRol()
  const { estado: sesion } = useSesion()
  const usuario = sesion.tipo === 'autenticado' ? sesion.usuario.usuario : null
  const [cargado, setCargado] = useState<ResultadoExpediente | null>(null)
  const [fichas, setFichas] = useState<TipoDocumental[]>([])
  const [fallo, setFallo] = useState<{ folio: string; mensaje: string } | null>(null)
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
        <Link to="/folios" className="mt-2 inline-block text-q-slate underline hover:text-q-orange-700">Volver a los folios</Link>
      </section>
    )
  }
  if (!expediente) return <p role="status" className="text-slate-600">Cargando el expediente…</p>

  const pestana = parametros.get('pestana') === 'resumen' ? 'resumen' : 'documentos'
  const idSeleccionado = pestana === 'documentos' ? parametros.get('doc') : null
  const cerrado = expediente.estado_general !== 'en_revision'
  // Acciones solo para el revisor y con el folio abierto; la API vuelve a comprobarlo
  const puedeActuar = rol === 'revisor' && !cerrado
  const puedeRetirar = rol !== null && ROLES_RETIRAR.includes(rol) && !cerrado
  const rutaCarga = rol !== null && ROLES_SUBIR.includes(rol) && !cerrado ? rutaPestana(expediente.folio, 'carga') : undefined

  const restaurar = (id: string) => ejecutar(() => restaurarDocumento(id), aplicarDocumento, 'Documento restaurado.', true)

  function vistaDocumento(doc: ResultadoDocumento) {
    const idDoc = doc.identificador_unico_documento
    // ADR-013: sobre un retirado no se revisa nada (la API responde 409 DOCUMENTO_RETIRADO)
    const docRevisable = puedeActuar && !doc.retirado
    const docAnalizado = doc.estado_analisis === 'completado' // corregir y reclasificar: ni en curso ni en error
    const fichaDoc = fichas.find((t) => t.nombre === tipoExtraccion(doc))
    const retirar = (puedeRetirar && !enProceso(doc)) || doc.retirado
      ? (
        <RetirarDocumento key={idDoc} doc={doc} puedeActuar={puedeRetirar && !enProceso(doc)} deshabilitado={ocupado}
          alRetirar={(motivo) => ejecutar(() => retirarDocumento(idDoc, { motivo }), aplicarDocumento, 'Documento retirado del folio.', true)}
          alRestaurar={() => restaurar(idDoc)} />
      )
      : undefined
    return (
      <DetalleDocumento key={idDoc} doc={doc} fichas={fichas} usuario={usuario}
        puedeVerOriginal={rol !== null && ROLES_ORIGINAL.includes(rol)}
        retirar={retirar}
        avisos={(
          <ListaAlertas titulo="Avisos de este documento" vacio="Este documento no tiene avisos." alertas={doc.alertas_encontradas}
            acciones={docRevisable && !enProceso(doc) ? (a) => (
              <RevisarAlerta alerta={a} deshabilitado={ocupado}
                alResolver={(aplica, comentario) => ejecutar(
                  () => resolverAlertaDocumento(idDoc, a.id!, { aplica, ...(comentario ? { comentario } : {}) }), aplicarDocumento,
                  `Alerta ${a.codigo} revisada.`, true)} />
            ) : undefined} />
        )}
        accionesClasificacion={docRevisable && docAnalizado ? (
          <ConfirmarClasificacion fichas={fichas} actual={tipoExtraccion(doc)} deshabilitado={ocupado}
            alConfirmar={(tipo) => ejecutar(() => confirmarClasificacion(idDoc, { tipo_documental: tipo }), aplicarDocumento,
              'Clasificación confirmada.', true)} />
        ) : undefined}
        celdaValor={docRevisable && docAnalizado ? (campo, contenido) => (
          <EditorCampo campo={campo} valor={doc.datos_extraidos[campo]} tipo={fichaDoc?.campos[campo]?.tipo}
            obligatorio={fichaDoc?.campos[campo]?.obligatorio ?? false}
            sensible={fichaDoc?.campos[campo]?.sensible ?? false} deshabilitado={ocupado}
            alGuardar={(valor) => ejecutar(() => corregirDatos(idDoc, { [campo]: valor }), aplicarDocumento,
              `${nombreCampo(campo)} corregido.`, true)}>
            {contenido}
          </EditorCampo>
        ) : undefined} />
    )
  }

  function vistaLista(exp: ResultadoExpediente) {
    // Los retirados (ADR-013) al final de la rejilla
    const ordenados = [...exp.documentos.filter(cuentaEnElFolio), ...exp.documentos.filter((d) => !cuentaEnElFolio(d))]
    const bloqueantes = alertasQueBloquean(exp)
    const pendientes = pendientesDeRevisar(exp).length
    const soloRechazar = hayBloqueantesConfirmadas(exp)
    return (
      <div className="space-y-4">
        <LeyendaSemaforo />
        <section aria-labelledby="titulo-documentos">
          <h2 id="titulo-documentos" className="font-semibold">Documentos del folio</h2>
          {ordenados.length === 0 && (
            <p className="mt-1 text-sm text-slate-600">
              Aún no hay documentos.{rutaCarga && <> <Link to={rutaCarga} className="text-q-slate underline">Cargar documentos</Link></>}
            </p>
          )}
          <div className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {ordenados.map((d) => (
              <TarjetaDocumento key={d.identificador_unico_documento} doc={d} fichas={fichas} deshabilitado={ocupado}
                rutaDetalle={rutaPestana(exp.folio, 'documentos', d.identificador_unico_documento)}
                textoAbrir={rol === 'revisor' ? 'Abrir y revisar' : 'Abrir'} rutaCarga={rutaCarga}
                alRestaurar={puedeRetirar ? () => restaurar(d.identificador_unico_documento) : undefined} />
            ))}
          </div>
        </section>

        <ComparacionesExpediente expediente={exp} fichas={fichas} />

        <div id="alertas-expediente" className="rounded-lg border border-q-slate-100 bg-white p-4">
          <ListaAlertas titulo="Alertas del expediente" alertas={exp.alertas_expediente}
            acciones={puedeActuar ? (a) => (
              <RevisarAlerta alerta={a} deshabilitado={ocupado}
                alResolver={(aplica, comentario) => ejecutar(
                  () => resolverAlertaExpediente(exp.folio, a.id!, { aplica, ...(comentario ? { comentario } : {}) }), setCargado,
                  `Alerta ${a.codigo} revisada.`)} />
            ) : undefined} />
        </div>

        {/* La decision, siempre la ultima seccion de la pagina */}
        <section aria-labelledby="titulo-decision" data-testid="seccion-decision" className="space-y-3">
          <h2 id="titulo-decision" className="font-semibold">Decisión del folio</h2>
          {cerrado && exp.decision_humana ? (
            <p role="status" className="flex items-start gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
              <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                <span className="font-medium">Decisión: {ETIQUETA_DECISION[exp.decision_humana]}</span>
                {exp.comentario_decision && <> · “{exp.comentario_decision}”</>}
                {' · '}{exp.usuario_decision ?? '—'} · {fechaHora(exp.fecha_decision)}. Folio cerrado: solo lectura.
              </span>
            </p>
          ) : (
            <>
              {pendientes > 0 ? (
                <p data-testid="estado-revision" className="flex items-center gap-2 rounded-lg border border-semaforo-ambar-borde bg-semaforo-ambar-fondo px-3 py-2 text-sm font-medium text-semaforo-ambar">
                  <AlertTriangle className="size-4 shrink-0" aria-hidden />
                  Antes de decidir: te {pendientes === 1 ? 'queda 1 cosa' : `quedan ${pendientes} cosas`} por revisar.
                  {soloRechazar && ' Hay bloqueantes confirmadas: solo puedes rechazar.'}
                </p>
              ) : (
                <p data-testid="estado-revision" className="flex items-center gap-2 rounded-lg border border-semaforo-verde-borde bg-semaforo-verde-fondo px-3 py-2 text-sm font-medium text-semaforo-verde">
                  <CheckCircle2 className="size-4 shrink-0" aria-hidden />
                  {soloRechazar ? 'Todo revisado. Hay bloqueantes confirmadas: solo puedes rechazar.' : 'Todo revisado. Ya puedes decidir.'}
                </p>
              )}
              {puedeActuar
                ? (
                  <PanelDecision bloqueantes={bloqueantes} enCurso={exp.documentos.filter(cuentaEnElFolio).some(enProceso)} deshabilitado={ocupado}
                    alDecidir={(decision, comentario) => ejecutar(
                      () => decidir(exp.folio, { decision, ...(comentario ? { comentario } : {}) }), setCargado,
                      `Folio ${decision === 'aprobar' ? 'aprobado' : 'rechazado'}.`)} />
                )
                : <p className="text-sm text-slate-600">La decisión la toma un revisor.</p>}
            </>
          )}
        </section>
      </div>
    )
  }

  const seleccionado = idSeleccionado ? expediente.documentos.find((d) => d.identificador_unico_documento === idSeleccionado) : undefined
  return (
    <section aria-labelledby="titulo-expediente">
      <CabeceraExpediente expediente={expediente} pestana={pestana} />

      {sondeo.detenido && <AvisoSondeoDetenido alReanudar={sondeo.reanudar} />}
      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} data-testid="aviso"
          className={`mt-3 rounded px-3 py-2 text-sm ${aviso.tipo === 'error' ? 'border border-red-300 bg-red-50 text-red-900' : 'bg-q-slate-50 text-q-slate'}`}>
          {aviso.texto}
        </p>
      )}

      <div className="mt-4">
        {pestana === 'resumen' && <PestanaResumen expediente={expediente} fichas={fichas} />}
        {pestana === 'documentos' && idSeleccionado && (
          <>
            <Link to={rutaPestana(expediente.folio, 'documentos')} className="mb-3 inline-flex items-center gap-1 text-sm text-q-slate underline hover:text-q-orange-700">
              <ArrowLeft className="size-4" aria-hidden /> Todos los documentos
            </Link>
            {seleccionado
              ? vistaDocumento(seleccionado)
              : <p role="alert" className="text-sm text-red-700">Ese documento no está en el folio.</p>}
          </>
        )}
        {pestana === 'documentos' && !idSeleccionado && vistaLista(expediente)}
      </div>
    </section>
  )
}
