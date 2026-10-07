import { Archive, ArchiveRestore } from 'lucide-react'
import { useId, useState } from 'react'
import type { ResultadoDocumento } from '../tipos/contrato'
import { fechaHora } from '../utilidades/etiquetas'

const boton = 'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs disabled:opacity-50'

/** Motivo obligatorio de POST /documentos/{id}/retirar (ADR-013) */
export const MOTIVO_RETIRAR_MIN = 3
export const MOTIVO_RETIRAR_MAX = 200

interface Props {
  doc: ResultadoDocumento
  /** Folio abierto y rol revisor o admin; sin ello solo se informa de la retirada */
  puedeActuar: boolean
  deshabilitado: boolean
  alRetirar: (motivo: string) => Promise<boolean>
  alRestaurar: () => Promise<boolean>
}

/**
 * ADR-013: retirar un documento subido por error (deja de contar para el folio; nada se borra) o
 * restaurarlo. Retirar pide un motivo obligatorio y una confirmacion; la API guarda el motivo tapado.
 */
export function RetirarDocumento({ doc, puedeActuar, deshabilitado, alRetirar, alRestaurar }: Props) {
  const [abierto, setAbierto] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const id = useId()
  const texto = motivo.trim()
  const valido = texto.length >= MOTIVO_RETIRAR_MIN

  async function enviar(accion: () => Promise<boolean>) {
    setEnviando(true)
    const ok = await accion()
    setEnviando(false)
    setConfirmando(false)
    if (ok) {
      setAbierto(false)
      setMotivo('')
    }
  }

  if (doc.retirado) {
    return (
      <section aria-label="Documento retirado" className="rounded border border-slate-300 bg-slate-100 p-3 text-sm">
        <p className="flex items-center gap-2 font-medium"><Archive className="size-4" aria-hidden /> Retirado del folio: no cuenta para la revisión.</p>
        <p className="mt-1 text-slate-700">
          {fechaHora(doc.retirado.en)} · {doc.retirado.por} · Motivo: “{doc.retirado.motivo}”
        </p>
        {puedeActuar && (
          <button type="button" onClick={() => enviar(alRestaurar)} disabled={deshabilitado || enviando}
            className={`${boton} mt-2 border-slate-500 bg-white`}>
            <ArchiveRestore className="size-3" aria-hidden /> {enviando ? 'Restaurando…' : 'Restaurar'}
          </button>
        )}
      </section>
    )
  }
  if (!puedeActuar) return null
  if (!abierto) {
    return (
      <button type="button" onClick={() => setAbierto(true)} disabled={deshabilitado} className={`${boton} border-slate-400`}>
        <Archive className="size-3" aria-hidden /> Retirar
      </button>
    )
  }
  return (
    <section aria-label="Retirar el documento" className="rounded border border-slate-300 bg-white p-3 text-sm">
      <label htmlFor={id} className="block text-xs text-slate-600">
        Motivo de la retirada (obligatorio, de {MOTIVO_RETIRAR_MIN} a {MOTIVO_RETIRAR_MAX} caracteres)
      </label>
      <textarea id={id} value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={2} maxLength={MOTIVO_RETIRAR_MAX}
        required disabled={enviando || confirmando} className="w-full rounded border border-slate-300 px-2 py-1" />
      {confirmando ? (
        <div role="alertdialog" aria-label="Confirmar la retirada" className="mt-2 rounded border border-amber-300 bg-amber-50 p-2">
          <p>¿Retiras este documento del folio? Dejará de contar para la revisión; no se borra y se puede restaurar.</p>
          <div className="mt-2 flex gap-2">
            <button type="button" onClick={() => enviar(() => alRetirar(texto))} disabled={enviando}
              className={`${boton} border-slate-800 bg-slate-800 text-white`}>{enviando ? 'Enviando…' : 'Sí, retirar'}</button>
            <button type="button" onClick={() => setConfirmando(false)} disabled={enviando} className={`${boton} border-slate-300`}>Cancelar</button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={() => setConfirmando(true)} disabled={!valido || deshabilitado}
            className={`${boton} border-slate-700`}>Retirar documento</button>
          <button type="button" onClick={() => { setAbierto(false); setMotivo('') }} className={`${boton} border-slate-300`}>Cancelar</button>
        </div>
      )}
    </section>
  )
}
