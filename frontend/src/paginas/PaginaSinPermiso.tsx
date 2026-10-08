import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'

export function PaginaSinPermiso() {
  return (
    <section className="p-8" aria-labelledby="titulo-sin-permiso">
      <h1 id="titulo-sin-permiso" className="flex items-center gap-2 text-xl font-semibold">
        <ShieldAlert className="size-6 text-q-orange-700" aria-hidden /> Sin permiso
      </h1>
      <p className="mt-2 text-slate-600">Tu rol no tiene acceso a esta pantalla.</p>
      <Link to="/folios" className="mt-3 inline-block text-q-slate underline hover:text-q-orange-700">Volver a los folios</Link>
    </section>
  )
}
