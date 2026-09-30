import { LoaderCircle } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { useSesion } from './contextoSesion'

/** Solo deja pasar con sesion; si no, lleva al login recordando la pagina pedida */
export function RutaProtegida() {
  const { estado, reintentar } = useSesion()
  const ubicacion = useLocation()

  if (estado.tipo === 'cargando') {
    return (
      <p className="flex items-center gap-2 p-8 text-slate-600">
        <LoaderCircle className="size-5 animate-spin" aria-hidden /> Recuperando la sesion...
      </p>
    )
  }
  if (estado.tipo === 'error') {
    return (
      <div className="p-8 text-slate-700">
        <p>No se pudo recuperar la sesion: {estado.mensaje}</p>
        <button className="mt-3 rounded bg-slate-800 px-3 py-1.5 text-white" onClick={reintentar}>
          Reintentar
        </button>
      </div>
    )
  }
  if (estado.tipo === 'anonimo') {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  }
  return <Outlet />
}
