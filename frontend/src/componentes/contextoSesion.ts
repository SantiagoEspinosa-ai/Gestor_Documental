import { createContext, useContext } from 'react'
import type { UsuarioActual } from '../tipos/api'

export type EstadoSesion =
  | { tipo: 'cargando' }
  | { tipo: 'anonimo' }
  | { tipo: 'autenticado'; usuario: UsuarioActual }
  /** No se pudo recuperar la sesion (p. ej. sin conexion); el token se conserva */
  | { tipo: 'error'; mensaje: string }

export interface ContextoSesion {
  estado: EstadoSesion
  entrar: (usuario: string, contrasena: string) => Promise<void>
  salir: () => void
  reintentar: () => void
}

export const Sesion = createContext<ContextoSesion | null>(null)

export function useSesion(): ContextoSesion {
  const contexto = useContext(Sesion)
  if (!contexto) throw new Error('useSesion debe usarse dentro de <ProveedorSesion>')
  return contexto
}
