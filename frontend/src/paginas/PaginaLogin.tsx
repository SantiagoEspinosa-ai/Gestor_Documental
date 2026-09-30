import { LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ErrorApi } from '../api/cliente'
import { useSesion } from '../componentes/contextoSesion'

export function PaginaLogin() {
  const { estado, entrar } = useSesion()
  const navegar = useNavigate()
  const destino = (useLocation().state as { desde?: string } | null)?.desde ?? '/folios'
  const [usuario, setUsuario] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (estado.tipo === 'autenticado') return <Navigate to={destino} replace />

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await entrar(usuario, contrasena)
      navegar(destino, { replace: true })
    } catch (causa) {
      setError(causa instanceof ErrorApi ? causa.message : 'No se pudo iniciar sesion')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <form onSubmit={enviar} className="w-80 space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-lg font-semibold text-slate-800">Gestor Documental</h1>
        <label className="block text-sm text-slate-700">
          Usuario
          <input
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="block text-sm text-slate-700">
          Contrasena
          <input
            type="password"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={enviando}
          className="flex w-full items-center justify-center gap-2 rounded bg-slate-800 py-2 text-white disabled:opacity-60"
        >
          <LogIn className="size-4" aria-hidden /> {enviando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
