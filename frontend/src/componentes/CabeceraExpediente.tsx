// Cabecera comun de las pestanas del expediente (Documentos, Cargar documentos, Resumen): folio, proceso,
// barra de fase y pestanas. Sin nombre de persona (ADR-004: no llega y no debe mostrarse).
import { ArrowLeft, Check, FileText, Lock } from 'lucide-react'
import { Link } from 'react-router'
import type { ResultadoExpediente } from '../tipos/contrato'
import { ETIQUETA_DECISION, ETIQUETA_ESTADO_GENERAL, fechaHora } from '../utilidades/etiquetas'
import { cuentaEnElFolio } from '../utilidades/expediente'
import { rutaPestana, type Pestana } from '../utilidades/navegacion'
import { PASOS_EXPEDIENTE, faseExpediente } from '../utilidades/semaforo'

const enlace = 'inline-flex items-center gap-1 text-sm text-q-slate underline hover:text-q-orange-700'

export function CabeceraExpediente({ expediente, pestana }: { expediente: ResultadoExpediente; pestana: Pestana }) {
  const cerrado = expediente.estado_general !== 'en_revision'
  const nDocumentos = expediente.documentos.filter(cuentaEnElFolio).length
  return (
    <>
      <Link to="/folios" className={enlace}><ArrowLeft className="size-4" aria-hidden /> Volver a los folios</Link>
      <header className="mt-2 rounded-lg border border-q-slate-100 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 id="titulo-expediente" className="font-semibold">
              <span className="block text-xs font-medium uppercase tracking-wide text-q-slate-400">Expediente</span>{' '}
              <span className="block font-mono text-2xl text-q-slate">{expediente.folio}</span>
            </h1>
            <p className="mt-1 text-sm text-slate-700">
              Proceso <span className="font-medium">{expediente.proceso}</span>
              {' · '}{nDocumentos} {nDocumentos === 1 ? 'documento' : 'documentos'}
              {' · '}{ETIQUETA_ESTADO_GENERAL[expediente.estado_general]}
            </p>
            <p className="text-xs text-slate-600">
              {`Referencia ${expediente.referencia_externa ?? '—'} · Solicitado el ${fechaHora(expediente.fecha_solicitud)}`}
            </p>
          </div>
          <Link to={rutaPestana(expediente.folio, 'resumen')}
            className="inline-flex items-center gap-1 rounded-[10px] border border-q-slate px-3 py-1.5 text-sm font-medium text-q-slate hover:bg-q-slate-50">
            <FileText className="size-4" aria-hidden /> Ver resumen
          </Link>
        </div>
        {cerrado && (
          <p role="status" className="mt-3 flex items-center gap-2 text-sm text-slate-700">
            <Lock className="size-4 shrink-0" aria-hidden /> Folio cerrado: solo lectura.
          </p>
        )}
        <BarraFase expediente={expediente} />
      </header>
      <Pestanas expediente={expediente} pestana={pestana} />
    </>
  )
}

/** Carga -> Analisis -> Revision -> Decision, con check / numero; el actual con aria-current="step" */
export function BarraFase({ expediente }: { expediente: ResultadoExpediente }) {
  const fase = faseExpediente(expediente)
  const actual = PASOS_EXPEDIENTE.findIndex((p) => p.fase === fase)
  const decidido = fase === 'decision'
  return (
    <nav aria-label="Fase del expediente" className="mt-4">
      <ol className="grid gap-2 sm:grid-cols-4">
        {PASOS_EXPEDIENTE.map((paso, i) => {
          // Con la decision tomada los 4 pasos estan hechos
          const hecho = decidido || i < actual
          const esActual = !decidido && i === actual
          const estilo = esActual
            ? 'border-q-orange bg-q-orange-50 text-q-slate'
            : hecho ? 'border-q-slate-200 bg-q-slate-50 text-q-slate' : 'border-slate-200 bg-white text-slate-600'
          return (
            <li key={paso.fase} aria-current={esActual ? 'step' : undefined} data-testid={`fase-${paso.fase}`}
              className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${estilo}`}>
              <span aria-hidden className={`flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                esActual ? 'bg-q-orange text-q-slate' : hecho ? 'bg-q-slate text-white' : 'bg-slate-200 text-slate-700'}`}>
                {hecho ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span>
                <span className="block font-medium">{paso.etiqueta}</span>
                <span className="block text-xs">
                  {esActual && <span className="font-semibold text-q-orange-700">Fase actual</span>}
                  {hecho && paso.fase === 'decision' && expediente.decision_humana
                    ? <>{ETIQUETA_DECISION[expediente.decision_humana]} · {fechaHora(expediente.fecha_decision)} · {expediente.usuario_decision ?? '—'}</>
                    : hecho && 'Hecho'}
                  {!hecho && !esActual && 'Pendiente'}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function Pestanas({ expediente, pestana }: { expediente: ResultadoExpediente; pestana: Pestana }) {
  const cerrado = expediente.estado_general !== 'en_revision'
  const n = expediente.documentos.length
  const clase = (activa: boolean) => `inline-block border-b-2 px-3 py-2 text-sm font-medium ${
    activa ? 'border-q-orange text-q-slate' : 'border-transparent text-slate-600 hover:text-q-slate'}`
  return (
    <nav aria-label="Secciones del expediente" className="mt-4 border-b border-q-slate-100">
      <ul className="flex flex-wrap items-end gap-1">
        <li>
          <Link to={rutaPestana(expediente.folio, 'documentos')} aria-current={pestana === 'documentos' ? 'page' : undefined}
            className={clase(pestana === 'documentos')}>Documentos · {n}</Link>
        </li>
        <li>
          {cerrado ? (
            // Folio decidido: no se puede subir nada; se explica en vez de esconder la pestana
            <span aria-disabled="true" className={`${clase(pestana === 'carga')} cursor-not-allowed text-slate-500`}
              title="El folio está cerrado: no se pueden subir documentos">
              Cargar documentos <span className="text-xs font-normal">(folio cerrado: no se pueden subir documentos)</span>
            </span>
          ) : (
            <Link to={rutaPestana(expediente.folio, 'carga')} aria-current={pestana === 'carga' ? 'page' : undefined}
              className={clase(pestana === 'carga')}>Cargar documentos</Link>
          )}
        </li>
        <li>
          <Link to={rutaPestana(expediente.folio, 'resumen')} aria-current={pestana === 'resumen' ? 'page' : undefined}
            className={clase(pestana === 'resumen')}>Resumen</Link>
        </li>
      </ul>
    </nav>
  )
}
