import { FileText, Lock, LogOut, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router'
import { alFolioCerrado } from '../api/cliente'
import { useSesion } from './contextoSesion'

/** Cabecera comun de las paginas con sesion y aviso de folio en solo lectura */
export function Estructura() {
  const { estado, salir } = useSesion()
  const [avisoSoloLectura, setAvisoSoloLectura] = useState<string | null>(null)

  useEffect(() => alFolioCerrado((error) => setAvisoSoloLectura(error.message)), [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between bg-slate-800 px-6 py-3 text-white">
        <Link to="/folios" className="flex items-center gap-2 font-semibold">
          <FileText className="size-5" aria-hidden /> Gestor Documental
        </Link>
        {estado.tipo === 'autenticado' && (
          <div className="flex items-center gap-4 text-sm">
            <span>
              {estado.usuario.usuario} <span className="text-slate-300">({estado.usuario.rol})</span>
            </span>
            <button onClick={salir} className="flex items-center gap-1 rounded px-2 py-1 hover:bg-slate-700">
              <LogOut className="size-4" aria-hidden /> Salir
            </button>
          </div>
        )}
      </header>
      {avisoSoloLectura && (
        <div role="status" className="flex items-center gap-2 border-b border-amber-300 bg-amber-50 px-6 py-2 text-amber-900">
          <Lock className="size-4" aria-hidden />
          <span>Folio cerrado: solo lectura. {avisoSoloLectura}</span>
          <button className="ml-auto" onClick={() => setAvisoSoloLectura(null)} aria-label="Cerrar aviso">
            <X className="size-4" aria-hidden />
          </button>
        </div>
      )}
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}
