import { Link } from 'react-router'

export function PaginaNoEncontrada() {
  return (
    <section className="p-8">
      <h1 className="text-xl font-semibold">Pagina no encontrada</h1>
      <Link to="/folios" className="mt-2 inline-block text-blue-700 underline">Volver a los folios</Link>
    </section>
  )
}
