import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { iniciarSesion, obtenerUsuarioActual } from '../api/auth'
import { alSesionCaducada, ErrorApi } from '../api/cliente'
import { borrarSesion, leerSesion } from '../api/sesion'
import { mensajeDeError } from '../utilidades/mensajes'
import { Sesion, type EstadoSesion } from './contextoSesion'

// setTimeout no admite mas de ~24,8 dias
const ESPERA_MAXIMA_MS = 2 ** 31 - 1
export const AVISO_SESION_CADUCADA = 'Tu sesión ha caducado o ya no es válida. Vuelve a entrar.'

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<EstadoSesion>(() =>
    leerSesion() ? { tipo: 'cargando' } : { tipo: 'anonimo' },
  )
  const [aviso, setAviso] = useState<string | null>(null)
  const [intento, setIntento] = useState(0)

  const caducar = useCallback(() => {
    setAviso(AVISO_SESION_CADUCADA)
    setEstado({ tipo: 'anonimo' })
  }, [])

  // Al cargar la pagina: si hay token vigente, se recupera la sesion con GET /auth/yo
  useEffect(() => {
    if (!leerSesion()) return
    const control = new AbortController()
    obtenerUsuarioActual(control.signal)
      .then((usuario) => setEstado({ tipo: 'autenticado', usuario }))
      .catch((error: unknown) => {
        if (control.signal.aborted) return
        if (error instanceof ErrorApi && error.estado === 401) caducar()
        else setEstado({ tipo: 'error', mensaje: mensajeDeError(error) })
      })
    return () => control.abort()
  }, [intento, caducar])

  // Un 401 en cualquier peticion cierra la sesion (el cliente ya ha borrado el token)
  useEffect(() => alSesionCaducada(caducar), [caducar])

  // Caducidad local segun expires_in, aunque no haya peticiones
  useEffect(() => {
    if (estado.tipo !== 'autenticado') return
    const guardada = leerSesion() // sin sesion guardada, espera 0: se cierra en el temporizador
    const espera = guardada ? Math.min(Math.max(guardada.expira_en - Date.now(), 0), ESPERA_MAXIMA_MS) : 0
    const temporizador = setTimeout(() => {
      if (!leerSesion()) caducar()
      else setIntento((n) => n + 1) // espera maxima alcanzada: se vuelve a comprobar
    }, espera)
    return () => clearTimeout(temporizador)
  }, [estado, caducar])

  const entrar = useCallback(async (usuario: string, contrasena: string) => {
    await iniciarSesion(usuario, contrasena)
    const actual = await obtenerUsuarioActual()
    setAviso(null)
    setEstado({ tipo: 'autenticado', usuario: actual })
  }, [])

  const salir = useCallback(() => {
    borrarSesion()
    setAviso(null)
    // Cierre voluntario: sin ruta de vuelta (RutaProtegida). Al caducar (401) si se conserva
    setEstado({ tipo: 'anonimo', porCierre: true })
  }, [])

  const reintentar = useCallback(() => {
    if (!leerSesion()) {
      setEstado({ tipo: 'anonimo' })
      return
    }
    setEstado({ tipo: 'cargando' })
    setIntento((n) => n + 1)
  }, [])

  const valor = useMemo(() => ({ estado, aviso, entrar, salir, reintentar }), [estado, aviso, entrar, salir, reintentar])
  return <Sesion.Provider value={valor}>{children}</Sesion.Provider>
}
