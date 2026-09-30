// POST /auth/login y GET /auth/yo (Contrato 2)
import type { RespuestaLogin, UsuarioActual } from '../tipos/api'
import { peticion } from './cliente'
import { guardarSesion, type SesionGuardada } from './sesion'

export async function iniciarSesion(usuario: string, contrasena: string): Promise<SesionGuardada> {
  const respuesta = await peticion<RespuestaLogin>('/auth/login', {
    metodo: 'POST',
    cuerpo: { usuario, contrasena },
    sinAutenticacion: true,
  })
  return guardarSesion(respuesta.access_token, respuesta.rol, respuesta.expires_in)
}

export function obtenerUsuarioActual(signal?: AbortSignal): Promise<UsuarioActual> {
  return peticion<UsuarioActual>('/auth/yo', { signal })
}
