// Usuarios ficticios SOLO para los mocks. Contrasenas de prueba evidentes; nunca se usan fuera de msw.
import type { Rol } from '../tipos/contrato'

export interface UsuarioDemo {
  usuario: string
  contrasena: string
  rol: Rol
}

export const USUARIOS_DEMO: UsuarioDemo[] = [
  { usuario: 'admin.demo', contrasena: 'demo-admin', rol: 'admin' },
  { usuario: 'revisor.demo', contrasena: 'demo-revisor', rol: 'revisor' },
  { usuario: 'integrador.demo', contrasena: 'demo-integrador', rol: 'integrador' },
]

/** Duracion del token de los mocks (expires_in, en segundos) */
export const DURACION_SESION_S = 3600
