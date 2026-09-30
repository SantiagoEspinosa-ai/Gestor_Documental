import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { iniciarSesion, obtenerUsuarioActual } from '../api/auth'
import { alSesionCaducada, ErrorApi } from '../api/cliente'
import { borrarSesion, leerSesion } from '../api/sesion'
import { Sesion, type EstadoSesion } from './contextoSesion'

// setTimeout no admite mas de ~24,8 dias
const ESPERA_MAXIMA_MS = 2 ** 31 - 1

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<EstadoSesion>(() =>
    leerSesion() ? { tipo: 'cargando' } : { tipo: 'anonimo' },
  )
  const [intento, setIntento] = useState(0)

  // Al cargar la pagina: si hay token vigente, se recupera la sesion con GET /auth/yo
  useEffect(() => {
    if (!leerSesion()) return
    const control = new AbortController()
    obtenerUsuarioActual(control.signal)
      .then((usuario) => setEstado({ tipo: 'autenticado', usuario }))
      .catch((error: unknown) => {
        if (control.signal.aborted) return
        if (error instanceof ErrorApi && error.estado === 401) setEstado({ tipo: 'anonimo' })
        else setEstado({ tipo: 'error', mensaje: error instanceof Error ? error.message : String(error) })
      })
    return () => control.abort()
  }, [intento])

  // Un 401 en cualquier peticion cierra la sesion (el cliente ya ha borrado el token)
  useEffect(() => alSesionCaducada(() => setEstado({ tipo: 'anonimo' })), [])

  // Caducidad local segun expires_in, aunque no haya peticiones
  useEffect(() => {
    if (estado.tipo !== 'autenticado') return
    const guardada = leerSesion() // sin sesion guardada, espera 0: se cierra en el temporizador
    const espera = guardada ? Math.min(Math.max(guardada.expira_en - Date.now(), 0), ESPERA_MAXIMA_MS) : 0
    const temporizador = setTimeout(() => {
      if (!leerSesion()) setEstado({ tipo: 'anonimo' })
      else setIntento((n) => n + 1) // espera maxima alcanzada: se vuelve a comprobar
    }, espera)
    return () => clearTimeout(temporizador)
  }, [estado])

  const entrar = useCallback(async (usuario: string, contrasena: string) => {
    await iniciarSesion(usuario, contrasena)
    setEstado({ tipo: 'autenticado', usuario: await obtenerUsuarioActual() })
  }, [])

  const salir = useCallback(() => {
    borrarSesion()
    setEstado({ tipo: 'anonimo' })
  }, [])

  const reintentar = useCallback(() => {
    if (!leerSesion()) {
      setEstado({ tipo: 'anonimo' })
      return
    }
    setEstado({ tipo: 'cargando' })
    setIntento((n) => n + 1)
  }, [])

  const valor = useMemo(() => ({ estado, entrar, salir, reintentar }), [estado, entrar, salir, reintentar])
  return <Sesion.Provider value={valor}>{children}</Sesion.Provider>
}
