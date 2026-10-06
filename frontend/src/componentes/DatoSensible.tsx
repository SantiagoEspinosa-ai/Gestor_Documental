import { Eye, EyeOff } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { revelarDato } from '../api/revision'
import { SEGUNDOS_DATO_REVELADO } from '../utilidades/etiquetas'
import { mensajeRevelar } from '../utilidades/mensajes'
import { formatearValor, nombreCampo } from '../utilidades/valores'

interface Props {
  documentoId: string
  campo: string
  tipo?: string | null
  /** El valor enmascarado tal como llega de la API (`****1234`) */
  children: ReactNode
}

const boton = 'inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50'

/**
 * "Mostrar" de un dato sensible (ADR-010 A4, H17): POST /documentos/{id}/revelar y el valor completo
 * mientras no se pulse "Ocultar", como mucho SEGUNDOS_DATO_REVELADO. El valor vive solo en el estado de
 * este componente: nada de storage, URL ni consola. Quien lo usa le pone una `key` con el documento y el
 * valor enmascarado, asi que cambiar de documento (o que cambie el dato) lo desmonta y lo olvida.
 * Solo para revisor y admin: lo decide quien lo pinta (SoloRol); la API lo vuelve a comprobar.
 */
export function DatoSensible({ documentoId, campo, tipo, children }: Props) {
  const [revelado, setRevelado] = useState<{ valor: unknown } | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nombre = nombreCampo(campo)

  // Se vuelve a ocultar solo; el temporizador se limpia al ocultar antes o al desmontar
  useEffect(() => {
    if (!revelado) return
    const temporizador = setTimeout(() => setRevelado(null), SEGUNDOS_DATO_REVELADO * 1000)
    return () => clearTimeout(temporizador)
  }, [revelado])

  async function mostrar() {
    setCargando(true)
    setError(null)
    try {
      const respuesta = await revelarDato(documentoId, { campo })
      setRevelado({ valor: respuesta.valor })
    } catch (causa) {
      setError(mensajeRevelar(causa))
    } finally {
      setCargando(false)
    }
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      {revelado ? <span className="font-mono">{formatearValor(revelado.valor, tipo)}</span> : children}
      {revelado
        ? (
          <button type="button" onClick={() => setRevelado(null)} aria-label={`Ocultar ${nombre}`} className={boton}>
            <EyeOff className="size-3" aria-hidden /> Ocultar
          </button>
        )
        : (
          <button type="button" onClick={mostrar} disabled={cargando} aria-label={`Mostrar ${nombre}`} className={boton}>
            <Eye className="size-3" aria-hidden /> {cargando ? 'Mostrando…' : 'Mostrar'}
          </button>
        )}
      <span aria-live="polite" className="sr-only">
        {revelado ? `Se muestra ${nombre}; se ocultará en ${SEGUNDOS_DATO_REVELADO} segundos.` : ''}
      </span>
      {error && <span role="alert" className="w-full text-xs text-red-700">{error}</span>}
    </span>
  )
}
