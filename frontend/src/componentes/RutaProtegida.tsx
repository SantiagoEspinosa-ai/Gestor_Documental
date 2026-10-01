import { LoaderCircle } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'
import type { Rol } from '../tipos/contrato'
import { PaginaSinPermiso } from '../paginas/PaginaSinPermiso'
import { rutaCompleta } from '../utilidades/navegacion'
import { useSesion } from './contextoSesion'

/** Solo deja pasar con sesion (y, si se indican, con uno de los roles); si no, al login */
export function RutaProtegida({ roles }: { roles?: readonly Rol[] }) {
  const { estado, reintentar } = useSesion()
  const ubicacion = useLocation()

  if (estado.tipo === 'cargando') {
    return (
      <p role="status" className="flex items-center gap-2 p-8 text-slate-600">
        <LoaderCircle className="size-5 animate-spin" aria-hidden /> Recuperando la sesión…
      </p>
    )
  }
  if (estado.tipo === 'error') {
    return (
      <div role="alert" className="p-8 text-slate-700">
        <p>No se pudo recuperar la sesión: {estado.mensaje}</p>
        <button className="mt-3 rounded bg-slate-800 px-3 py-1.5 text-white" onClick={reintentar}>
          Reintentar
        </button>
      </div>
    )
  }
  if (estado.tipo === 'anonimo') {
    // Ruta completa (con search y hash): el login vuelve a ella si es interna (utilidades/navegacion.ts)
    return <Navigate to="/login" replace state={{ desde: rutaCompleta(ubicacion) }} />
  }
  if (roles && !roles.includes(estado.usuario.rol)) return <PaginaSinPermiso />
  return <Outlet />
}
