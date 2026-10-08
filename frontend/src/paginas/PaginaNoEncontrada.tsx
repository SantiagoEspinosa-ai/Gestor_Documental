import { Link } from 'react-router'

export function PaginaNoEncontrada() {
  return (
    <section className="p-8">
      <h1 className="text-xl font-semibold">Página no encontrada</h1>
      <Link to="/folios" className="mt-2 inline-block text-q-slate underline hover:text-q-orange-700">Volver a los folios</Link>
    </section>
  )
}
