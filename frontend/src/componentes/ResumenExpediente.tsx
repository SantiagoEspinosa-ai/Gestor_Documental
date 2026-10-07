import { FileText, X } from 'lucide-react'
import { useState } from 'react'
import Markdown from 'react-markdown'
import { obtenerResumen } from '../api/folios'
import { mensajeDeError } from '../utilidades/mensajes'

interface Props {
  folio: string
}

/**
 * "Ver resumen": GET /folios/{folio}/resumen.md renderizado con react-markdown sin HTML crudo
 * (skipHtml: las etiquetas HTML del Markdown se descartan). Quien lo usa lo oculta si
 * ruta_resumen_md es null; si aun asi no existe, la API responde 404 RESUMEN_NO_DISPONIBLE.
 */
export function ResumenExpediente({ folio }: Props) {
  const [abierto, setAbierto] = useState(false)
  const [estado, setEstado] = useState<{ texto: string | null; error: string | null; cargando: boolean }>(
    { texto: null, error: null, cargando: false })

  async function abrir() {
    setAbierto(true)
    setEstado({ texto: null, error: null, cargando: true })
    try {
      setEstado({ texto: await obtenerResumen(folio), error: null, cargando: false })
    } catch (causa) {
      setEstado({ texto: null, error: mensajeDeError(causa), cargando: false })
    }
  }

  if (!abierto) {
    return (
      <button type="button" onClick={abrir} className="inline-flex items-center gap-1 text-sm text-q-slate underline hover:text-q-orange-700">
        <FileText className="size-4" aria-hidden /> Ver resumen
      </button>
    )
  }
  return (
    <section aria-label="Resumen del expediente" className="mt-3 w-full rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Resumen del expediente</h2>
        <button type="button" onClick={() => setAbierto(false)} className="inline-flex items-center gap-1 text-xs text-slate-600 underline">
          <X className="size-3.5" aria-hidden /> Cerrar resumen
        </button>
      </div>
      {estado.cargando && <p role="status" className="mt-2 text-sm text-slate-500">Cargando el resumen…</p>}
      {estado.error && <p role="alert" className="mt-2 text-sm text-red-700">{estado.error}</p>}
      {estado.texto !== null && (
        <div className="resumen-md mt-2 space-y-2 text-sm [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:font-semibold [&_ul]:list-disc [&_ul]:pl-5">
          <Markdown skipHtml>{estado.texto}</Markdown>
        </div>
      )}
    </section>
  )
}
