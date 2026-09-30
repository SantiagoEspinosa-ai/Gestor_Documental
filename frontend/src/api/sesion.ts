// Sesion en sessionStorage: se pierde al cerrar la pestana. La caducidad sale de expires_in.
import type { Rol } from '../tipos/api'

const CLAVE = 'gestor_documental.sesion'

export interface SesionGuardada {
  token: string
  rol: Rol
  /** Instante de caducidad en milisegundos (Date.now() + expires_in * 1000) */
  expira_en: number
}

// Respaldo en memoria si el navegador bloquea sessionStorage (modo privado, politicas)
let enMemoria: SesionGuardada | null = null

export function guardarSesion(token: string, rol: Rol, expiresIn: number, ahora = Date.now()): SesionGuardada {
  const sesion: SesionGuardada = { token, rol, expira_en: ahora + expiresIn * 1000 }
  enMemoria = sesion
  try {
    sessionStorage.setItem(CLAVE, JSON.stringify(sesion))
  } catch {
    // sin sessionStorage: queda solo en memoria
  }
  return sesion
}

export function leerSesion(ahora = Date.now()): SesionGuardada | null {
  let sesion = enMemoria
  try {
    const guardada = sessionStorage.getItem(CLAVE)
    if (guardada) sesion = JSON.parse(guardada) as SesionGuardada
  } catch {
    // JSON corrupto o sessionStorage no disponible: se usa lo que haya en memoria
  }
  if (!sesion || typeof sesion.token !== 'string' || typeof sesion.expira_en !== 'number') return null
  if (sesion.expira_en <= ahora) {
    borrarSesion()
    return null
  }
  return sesion
}

export function borrarSesion(): void {
  enMemoria = null
  try {
    sessionStorage.removeItem(CLAVE)
  } catch {
    // nada que borrar
  }
}
