// Controles de las acciones del revisor (bloque H). Solo se montan para el rol revisor y con el folio
// abierto; la API vuelve a comprobarlo. Ninguno decide nada solo: todo lo inicia una persona.
import { Check, Pencil, X } from 'lucide-react'
import { useId, useState, type FormEvent, type ReactNode } from 'react'
import type { Alerta, DecisionHumana, TipoDocumental } from '../tipos/contrato'
import { formatearValor, nombreCampo, prepararCorreccion, sinValor } from '../utilidades/valores'

const boton = 'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs disabled:opacity-50'

// ------------------------------------------------------------------ corregir un dato

interface EditorCampoProps {
  campo: string
  valor: unknown
  tipo?: string | null
  /** `obligatorio` de la ficha: no se puede guardar vacio */
  obligatorio?: boolean
  /** `sensible` de la ficha (ADR-010): la API lo da enmascarado, asi que el formulario empieza vacio */
  sensible?: boolean
  deshabilitado: boolean
  /** Devuelve true si se guardo */
  alGuardar: (valor: unknown) => Promise<boolean>
  children: ReactNode
}

export function EditorCampo({ campo, valor, tipo, obligatorio = false, sensible = false, deshabilitado, alGuardar, children }: EditorCampoProps) {
  const [editando, setEditando] = useState(false)
  const [texto, setTexto] = useState('')
  const [guardando, setGuardando] = useState(false)
  const id = useId()
  const idAyuda = useId()
  const idMotivo = useId()
  const preparada = prepararCorreccion(texto, { tipo, obligatorio })

  if (!editando) {
    return (
      <div className="flex items-start justify-between gap-2">
        <div>{children}</div>
        <button type="button" disabled={deshabilitado} aria-label={`Corregir ${nombreCampo(campo)}`}
          // Un sensible llega enmascarado ("****1234"): no se precarga, para no guardar la mascara como valor
          onClick={() => { setTexto(sensible || sinValor(valor) ? '' : String(valor)); setEditando(true) }}
          className={`${boton} border-slate-300 text-slate-700 hover:bg-slate-100`}>
          <Pencil className="size-3" aria-hidden /> Corregir
        </button>
      </div>
    )
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!preparada.valida) return // el boton ya esta deshabilitado; Intro tampoco envia
    setGuardando(true)
    const ok = await alGuardar(preparada.valor)
    setGuardando(false)
    if (ok) setEditando(false)
  }

  return (
    <form onSubmit={enviar} className="space-y-1">
      <p className="text-xs text-slate-600">Valor actual: <span className="font-medium">{formatearValor(valor, tipo)}</span></p>
      <label htmlFor={id} className="sr-only">Nuevo valor de {nombreCampo(campo)}</label>
      {/* anio como texto con teclado numerico: un input number vacia el valor si no es un numero y el
          aviso de formato no llegaria a salir */}
      <input id={id} value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus
        type={tipo === 'fecha' ? 'date' : 'text'} inputMode={tipo === 'anio' ? 'numeric' : undefined}
        maxLength={tipo === 'anio' ? 4 : undefined} placeholder={tipo === 'anio' ? 'AAAA' : undefined}
        aria-invalid={!preparada.valida} aria-describedby={preparada.valida ? idAyuda : `${idMotivo} ${idAyuda}`}
        className="w-full rounded border border-slate-300 px-2 py-1 text-sm" />
      <p id={idMotivo} aria-live="polite" className="text-xs text-red-700">{preparada.valida ? '' : preparada.motivo}</p>
      <p id={idAyuda} className="text-xs text-slate-500">
        {sensible && 'Dato sensible: escribe el valor completo. '}
        {obligatorio
          ? 'Campo obligatorio de la ficha: escribe el valor correcto.'
          : 'Déjalo vacío si el documento no trae este dato (queda como “no detectado”).'}
      </p>
      <div className="flex gap-2">
        <button type="submit" disabled={guardando || !preparada.valida} className={`${boton} border-blue-700 bg-blue-700 text-white`}>
          <Check className="size-3" aria-hidden /> {guardando ? 'Guardando…' : 'Guardar corrección'}
        </button>
        <button type="button" onClick={() => setEditando(false)} disabled={guardando} className={`${boton} border-slate-300`}>
          <X className="size-3" aria-hidden /> Cancelar
        </button>
      </div>
    </form>
  )
}

// ------------------------------------------------------------------ confirmar la clasificacion

interface ConfirmarClasificacionProps {
  fichas: TipoDocumental[]
  /** Tipo con el que se extrajo (regla 2.5) */
  actual: string | null
  deshabilitado: boolean
  alConfirmar: (tipo: string) => Promise<boolean>
}

export function ConfirmarClasificacion({ fichas, actual, deshabilitado, alConfirmar }: ConfirmarClasificacionProps) {
  const [tipo, setTipo] = useState(actual ?? fichas[0]?.nombre ?? '')
  const [enviando, setEnviando] = useState(false)
  const id = useId()
  const distinto = tipo !== actual
  return (
    <form className="mt-2 flex flex-wrap items-end gap-2 text-sm"
      onSubmit={async (e) => { e.preventDefault(); setEnviando(true); await alConfirmar(tipo); setEnviando(false) }}>
      <div>
        <label htmlFor={id} className="block text-xs text-slate-600">Tipo documental correcto</label>
        <select id={id} value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={deshabilitado || enviando}
          className="rounded border border-slate-300 px-2 py-1">
          {fichas.map((f) => <option key={f.nombre} value={f.nombre}>{f.nombre_visible}</option>)}
        </select>
      </div>
      <button type="submit" disabled={deshabilitado || enviando || !tipo} className={`${boton} border-slate-700 py-1`}>
        {enviando ? 'Confirmando…' : 'Confirmar clasificación'}
      </button>
      {distinto && <p className="w-full text-xs text-q-orange-700">Es distinto del tipo con el que se extrajo: el documento se volverá a analizar.</p>}
    </form>
  )
}

// ------------------------------------------------------------------ revisar una alerta

interface RevisarAlertaProps {
  alerta: Alerta
  deshabilitado: boolean
  alResolver: (aplica: boolean, comentario: string) => Promise<boolean>
}

export function RevisarAlerta({ alerta, deshabilitado, alResolver }: RevisarAlertaProps) {
  const [comentario, setComentario] = useState('')
  const [enviando, setEnviando] = useState(false)
  const id = useId()
  if (!alerta.id) return <p className="mt-1 text-xs text-slate-500">Esta alerta no tiene identificador: no se puede revisar.</p>
  const resolver = async (aplica: boolean) => {
    setEnviando(true)
    if (await alResolver(aplica, comentario.trim())) setComentario('')
    setEnviando(false)
  }
  const inactivo = deshabilitado || enviando
  return (
    <div className="mt-1 space-y-1">
      <label htmlFor={id} className="sr-only">Comentario sobre {alerta.codigo}</label>
      <input id={id} value={comentario} onChange={(e) => setComentario(e.target.value)} disabled={inactivo}
        placeholder="Comentario (opcional)" className="w-full rounded border border-slate-300 bg-white px-2 py-0.5 text-xs" />
      <div className="flex gap-2">
        <button type="button" onClick={() => resolver(true)} disabled={inactivo} aria-label={`${alerta.codigo}: aplica`}
          className={`${boton} border-slate-700 bg-white`}>Aplica</button>
        <button type="button" onClick={() => resolver(false)} disabled={inactivo} aria-label={`${alerta.codigo}: falso positivo`}
          className={`${boton} border-slate-700 bg-white`}>Falso positivo</button>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ decision del folio

interface PanelDecisionProps {
  /** Alertas que impiden aprobar (regla 2.2) */
  bloqueantes: Alerta[]
  /** Documentos pendientes o procesando: no se puede decidir (409 DOCUMENTO_EN_PROCESO) */
  enCurso: boolean
  deshabilitado: boolean
  alDecidir: (decision: DecisionHumana, comentario: string) => Promise<boolean>
}

export function PanelDecision({ bloqueantes, enCurso, deshabilitado, alDecidir }: PanelDecisionProps) {
  const [comentario, setComentario] = useState('')
  const [pendiente, setPendiente] = useState<DecisionHumana | null>(null)
  const [enviando, setEnviando] = useState(false)
  const id = useId()
  const puedeAprobar = bloqueantes.length === 0 && !enCurso && !deshabilitado

  async function confirmar() {
    if (!pendiente) return
    setEnviando(true)
    const ok = await alDecidir(pendiente, comentario.trim())
    setEnviando(false)
    setPendiente(null)
    if (ok) setComentario('')
  }

  return (
    <section aria-label="Decisión del revisor" className="rounded border border-slate-300 bg-white p-3 text-sm">
      <h2 className="text-sm font-semibold">Decisión</h2>
      <label htmlFor={id} className="mt-1 block text-xs text-slate-600">Comentario de la decisión</label>
      <textarea id={id} value={comentario} onChange={(e) => setComentario(e.target.value)} rows={2} disabled={deshabilitado || enviando}
        className="w-full rounded border border-slate-300 px-2 py-1" />
      {bloqueantes.length > 0 && (
        <div role="note" className="mt-1 rounded bg-red-50 px-2 py-1 text-xs text-red-900">
          <p className="font-medium">No se puede aprobar: {bloqueantes.length === 1 ? 'bloquea esta alerta' : 'bloquean estas alertas'} (márcala como falso positivo si no aplica):</p>
          <ul className="list-disc pl-4">{bloqueantes.map((a, i) => <li key={a.id ?? i}><span className="font-mono">{a.codigo}</span>: {a.mensaje}</li>)}</ul>
        </div>
      )}
      {enCurso && <p className="mt-1 text-xs text-slate-600">Hay documentos analizándose: espera a que terminen para decidir.</p>}
      {pendiente ? (
        <div role="alertdialog" aria-label="Confirmar la decisión" className="mt-2 rounded border border-q-orange-100 bg-q-orange-50 p-2">
          <p>¿Confirmas <strong>{pendiente === 'aprobar' ? 'aprobar' : 'rechazar'}</strong> el folio? La decisión lo cierra y no se puede deshacer.</p>
          <div className="mt-2 flex gap-2">
            <button type="button" onClick={confirmar} disabled={enviando} className={`${boton} border-q-slate bg-q-slate text-white`}>
              {enviando ? 'Enviando…' : `Sí, ${pendiente}`}
            </button>
            <button type="button" onClick={() => setPendiente(null)} disabled={enviando} className={`${boton} border-slate-300`}>Cancelar</button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={() => setPendiente('aprobar')} disabled={!puedeAprobar}
            className={`${boton} rounded-[10px]! border-q-orange py-1 bg-q-orange font-medium text-white hover:bg-q-orange-500`}>Aprobar</button>
          <button type="button" onClick={() => setPendiente('rechazar')} disabled={enCurso || deshabilitado}
            className={`${boton} border-red-700 py-1 text-red-800`}>Rechazar</button>
        </div>
      )}
    </section>
  )
}
