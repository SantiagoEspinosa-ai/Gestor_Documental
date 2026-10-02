import { createContext, useContext } from 'react'
import type { Rol, UsuarioActual } from '../tipos/contrato'

export type EstadoSesion =
  | { tipo: 'cargando' }
  /** `porCierre`: el usuario cerro la sesion; el login no vuelve a la pagina en la que estaba */
  | { tipo: 'anonimo'; porCierre?: boolean }
  | { tipo: 'autenticado'; usuario: UsuarioActual }
  /** No se pudo recuperar la sesion (p. ej. sin conexion); el token se conserva */
  | { tipo: 'error'; mensaje: string }

export interface ContextoSesion {
  estado: EstadoSesion
  /** Aviso para la pantalla de login, p. ej. al caducar la sesion */
  aviso: string | null
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

/** Rol de la sesion actual, o null si no hay sesion */
export function useRol(): Rol | null {
  const { estado } = useSesion()
  return estado.tipo === 'autenticado' ? estado.usuario.rol : null
}
