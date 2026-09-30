import { useParams } from 'react-router'

// Pendiente: vista del expediente (diapositiva 8) con GET /folios/{folio}
export function PaginaExpediente() {
  const { folio } = useParams()
  return (
    <section>
      <h1 className="text-xl font-semibold">Expediente {folio}</h1>
      <p className="mt-2 text-slate-600">Vista del expediente: pendiente.</p>
    </section>
  )
}
