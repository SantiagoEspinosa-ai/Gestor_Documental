import { FolderOpen, Lock, LogOut, ScrollText, Settings, UserRound, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { alFolioCerrado } from '../api/cliente'
import { ETIQUETA_ROL } from '../utilidades/etiquetas'
import { useSesion } from './contextoSesion'
import { SoloRol } from './SoloRol'

const ROLES_AUDITORIA = ['admin'] as const // GET /auditoria; tambien la pantalla de procesos (H8)
const claseEnlace = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1 rounded px-2 py-1 text-sm hover:bg-q-slate-700 ${isActive ? 'bg-q-slate-700' : ''}`

/** Cabecera comun de las paginas con sesion y aviso de folio en solo lectura */
export function Estructura() {
  const { estado, salir } = useSesion()
  const [avisoSoloLectura, setAvisoSoloLectura] = useState<string | null>(null)

  useEffect(() => alFolioCerrado((error) => setAvisoSoloLectura(error.message)), [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-slate-900">
        Saltar al contenido
      </a>
      <header className="flex flex-wrap items-center justify-between gap-3 bg-q-slate px-6 py-3 text-white">
        <div className="flex items-center gap-6">
          <Link to="/folios" className="flex items-center gap-2 font-semibold">
            <img src="/brand/logo-white.svg" alt="Qaracter" className="h-6" /> Gestor Documental
          </Link>
          <nav aria-label="Principal" className="flex items-center gap-1">
            <NavLink to="/folios" end className={claseEnlace}>
              <FolderOpen className="size-4" aria-hidden /> Folios
            </NavLink>
            <SoloRol roles={ROLES_AUDITORIA}>
              <NavLink to="/auditoria" className={claseEnlace}>
                <ScrollText className="size-4" aria-hidden /> Auditoría
              </NavLink>
              <NavLink to="/procesos" className={claseEnlace}>
                <Settings className="size-4" aria-hidden /> Procesos
              </NavLink>
            </SoloRol>
          </nav>
        </div>
        {estado.tipo === 'autenticado' && (
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1" data-testid="usuario-actual">
              <UserRound className="size-4" aria-hidden />
              <span>{estado.usuario.usuario}</span>
              <span className="rounded bg-q-slate-700 px-1.5 py-0.5 text-xs">{ETIQUETA_ROL[estado.usuario.rol]}</span>
            </span>
            <button type="button" onClick={salir} className="flex items-center gap-1 rounded px-2 py-1 hover:bg-q-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
              <LogOut className="size-4" aria-hidden /> Cerrar sesión
            </button>
          </div>
        )}
      </header>
      {avisoSoloLectura && (
        <div role="status" className="flex items-center gap-2 border-b border-q-orange-100 bg-q-orange-50 px-6 py-2 text-q-orange-700">
          <Lock className="size-4" aria-hidden />
          <span>Folio cerrado: solo lectura. {avisoSoloLectura}</span>
          <button type="button" className="ml-auto" onClick={() => setAvisoSoloLectura(null)} aria-label="Cerrar aviso">
            <X className="size-4" aria-hidden />
          </button>
        </div>
      )}
      <main id="contenido" tabIndex={-1} className="p-6 focus:outline-none">
        <Outlet />
      </main>
    </div>
  )
}
