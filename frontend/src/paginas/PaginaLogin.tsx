import { Eye, EyeOff, LogIn } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ErrorApi } from '../api/cliente'
import { useSesion } from '../componentes/contextoSesion'
import { mensajeDeError } from '../utilidades/mensajes'
import { rutaInternaSegura } from '../utilidades/navegacion'

export function PaginaLogin() {
  const { estado, aviso, entrar } = useSesion()
  const navegar = useNavigate()
  // Ruta completa que se pidio sin sesion; solo si es interna (nunca otro sitio)
  const destino = rutaInternaSegura((useLocation().state as { desde?: unknown } | null)?.desde)
  const [usuario, setUsuario] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [verContrasena, setVerContrasena] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const refUsuario = useRef<HTMLInputElement>(null)
  const refContrasena = useRef<HTMLInputElement>(null)

  useEffect(() => refUsuario.current?.focus(), [])

  if (estado.tipo === 'autenticado') return <Navigate to={destino} replace />

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await entrar(usuario.trim(), contrasena)
      navegar(destino, { replace: true })
    } catch (causa) {
      setError(mensajeDeError(causa))
      if (causa instanceof ErrorApi && causa.codigo === 'CREDENCIALES_INVALIDAS') {
        setContrasena('')
        refContrasena.current?.focus()
      }
    } finally {
      setEnviando(false)
    }
  }

  const describe = error ? 'error-login' : undefined
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={enviar} noValidate aria-labelledby="titulo-login" aria-busy={enviando}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 id="titulo-login" className="text-lg font-semibold text-slate-800">Gestor Documental</h1>
        {aviso && !error && <p role="status" className="rounded bg-amber-50 px-3 py-2 text-sm text-amber-900">{aviso}</p>}
        <div>
          <label htmlFor="usuario" className="block text-sm text-slate-700">Usuario</label>
          <input id="usuario" ref={refUsuario} name="usuario" autoComplete="username" required
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 focus:outline-2 focus:outline-blue-600"
            value={usuario} onChange={(e) => setUsuario(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={describe} />
        </div>
        <div>
          <label htmlFor="contrasena" className="block text-sm text-slate-700">Contraseña</label>
          <div className="mt-1 flex">
            <input id="contrasena" ref={refContrasena} name="contrasena" type={verContrasena ? 'text' : 'password'}
              autoComplete="current-password" required
              className="w-full rounded-l border border-slate-300 px-2 py-1.5 focus:outline-2 focus:outline-blue-600"
              value={contrasena} onChange={(e) => setContrasena(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={describe} />
            <button type="button" onClick={() => setVerContrasena((v) => !v)} aria-pressed={verContrasena}
              aria-label={verContrasena ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              className="rounded-r border border-l-0 border-slate-300 px-2 text-slate-600 hover:bg-slate-50">
              {verContrasena ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          </div>
        </div>
        {error && <p id="error-login" role="alert" className="text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={enviando || !usuario.trim() || !contrasena}
          className="flex w-full items-center justify-center gap-2 rounded bg-slate-800 py-2 text-white disabled:opacity-60">
          <LogIn className="size-4" aria-hidden /> {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </main>
  )
}
