import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { urlOriginal } from '../api/folios'
import { mensajeDeError } from '../utilidades/mensajes'

interface Props {
  documentoId: string
  nombreArchivo: string
}

const esPdf = (nombre: string) => nombre.toLowerCase().endsWith('.pdf')

/**
 * Original del documento. La URL prefirmada caduca (300 s en la API real): se pide al abrir el visor
 * (al montar o al cambiar de documento) y con "Volver a cargar", nunca se reutiliza una anterior.
 * Solo revisor y admin pueden pedirla: quien lo monte debe comprobar el rol.
 */
export function VisorOriginal({ documentoId, nombreArchivo }: Props) {
  const [estado, setEstado] = useState<{ url: string | null; error: string | null }>({ url: null, error: null })
  const [aperturas, setAperturas] = useState(0)

  // Quien lo usa lo monta con key = documento: al cambiar de documento empieza de cero
  useEffect(() => {
    const control = new AbortController()
    urlOriginal(documentoId, control.signal)
      .then(({ url }) => setEstado({ url, error: null }))
      .catch((causa) => { if (!control.signal.aborted) setEstado({ url: null, error: mensajeDeError(causa) }) })
    return () => control.abort()
  }, [documentoId, aperturas])

  const titulo = `Original: ${nombreArchivo}`
  return (
    <figure className="rounded border border-slate-200 bg-white p-2">
      <figcaption className="flex items-center justify-between gap-2 text-xs text-slate-600">
        <span className="font-mono">{nombreArchivo}</span>
        <button type="button" onClick={() => { setEstado({ url: null, error: null }); setAperturas((n) => n + 1) }} className="inline-flex items-center gap-1 text-q-slate underline hover:text-q-orange-700">
          <RefreshCw className="size-3.5" aria-hidden /> Volver a cargar
        </button>
      </figcaption>
      {estado.error && <p role="alert" className="mt-2 text-sm text-red-700">No se pudo abrir el original. {estado.error}</p>}
      {!estado.error && !estado.url && <p role="status" className="mt-2 text-sm text-slate-500">Abriendo el original…</p>}
      {estado.url && (esPdf(nombreArchivo)
        ? <iframe title={titulo} src={estado.url} className="mt-2 h-[28rem] w-full rounded border border-slate-100" />
        : <img alt={titulo} src={estado.url} className="mt-2 max-h-[28rem] w-full rounded object-contain" />)}
    </figure>
  )
}
