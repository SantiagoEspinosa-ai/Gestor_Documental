import { ExternalLink, Maximize2, RefreshCw, Scan, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { urlOriginal } from '../api/folios'
import { mensajeDeError } from '../utilidades/mensajes'

interface Props {
  documentoId: string
  nombreArchivo: string
}

const esPdf = (nombre: string) => nombre.toLowerCase().endsWith('.pdf')

/** Zoom de las imagenes: 100 % = ajustada al recuadro; de 50 % a 400 % en pasos de 25 */
const ZOOM_MIN = 50
const ZOOM_MAX = 400
const PASO_ZOOM = 25
const PASO_TECLADO = 40 // px que mueven las flechas con zoom
const limitar = (zoom: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom))

/**
 * Original del documento. La URL prefirmada caduca (300 s en la API real): se pide al abrir el visor
 * (al montar o al cambiar de documento) y con "Volver a cargar", nunca se reutiliza una anterior.
 * Zoom, arrastre, pantalla completa y "Abrir en pestana nueva" usan la URL ya cargada: cada peticion deja
 * `original_visto` en la auditoria (ADR-010 A4b). Solo revisor y admin pueden pedirla: quien lo monte debe
 * comprobar el rol.
 */
export function VisorOriginal({ documentoId, nombreArchivo }: Props) {
  const [estado, setEstado] = useState<{ url: string | null; error: string | null }>({ url: null, error: null })
  const [aperturas, setAperturas] = useState(0)
  const [ampliado, setAmpliado] = useState(false)
  const botonAmpliar = useRef<HTMLButtonElement>(null)

  // Quien lo usa lo monta con key = documento: al cambiar de documento empieza de cero
  useEffect(() => {
    const control = new AbortController()
    urlOriginal(documentoId, control.signal)
      .then(({ url }) => setEstado({ url, error: null }))
      .catch((causa) => { if (!control.signal.aborted) setEstado({ url: null, error: mensajeDeError(causa) }) })
    return () => control.abort()
  }, [documentoId, aperturas])

  const titulo = `Original: ${nombreArchivo}`
  const pdf = esPdf(nombreArchivo)
  const enlace = 'inline-flex items-center gap-1 text-q-slate underline hover:text-q-orange-700'
  return (
    <figure className="rounded border border-slate-200 bg-white p-2">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <span className="font-mono">{nombreArchivo}</span>
        <span className="flex flex-wrap items-center gap-3">
          {estado.url && pdf && (
            <a href={estado.url} target="_blank" rel="noopener noreferrer" className={enlace}>
              <ExternalLink className="size-3.5" aria-hidden /> Abrir en pestaña nueva
            </a>
          )}
          {estado.url && !pdf && (
            <button ref={botonAmpliar} type="button" onClick={() => setAmpliado(true)} className={enlace}>
              <Maximize2 className="size-3.5" aria-hidden /> Pantalla completa
            </button>
          )}
          <button type="button" onClick={() => { setEstado({ url: null, error: null }); setAperturas((n) => n + 1) }} className={enlace}>
            <RefreshCw className="size-3.5" aria-hidden /> Volver a cargar
          </button>
        </span>
      </figcaption>
      {estado.error && <p role="alert" className="mt-2 text-sm text-red-700">No se pudo abrir el original. {estado.error}</p>}
      {!estado.error && !estado.url && <p role="status" className="mt-2 text-sm text-slate-500">Abriendo el original…</p>}
      {estado.url && (pdf
        // PDF: el visor del navegador ya tiene zoom
        ? <iframe title={titulo} src={estado.url} className="mt-2 h-[28rem] w-full rounded border border-slate-100" />
        : <ImagenConZoom url={estado.url} alt={titulo} alto="h-[28rem]" />)}
      {ampliado && estado.url && (
        <VisorAmpliado url={estado.url} alt={titulo} nombreArchivo={nombreArchivo}
          alCerrar={() => { setAmpliado(false); botonAmpliar.current?.focus() }} />
      )}
    </figure>
  )
}

/** Imagen con "Alejar", "Acercar", "Ajustar", el porcentaje, Ctrl + rueda y arrastre con zoom */
function ImagenConZoom({ url, alt, alto }: { url: string; alt: string; alto: string }) {
  const [zoom, setZoom] = useState(100)
  const [desplazamiento, setDesplazamiento] = useState({ x: 0, y: 0 })
  const arrastre = useRef<{ x: number; y: number; desdeX: number; desdeY: number } | null>(null)
  const [arrastrando, setArrastrando] = useState(false)
  const marco = useRef<HTMLDivElement>(null)

  const cambiarZoom = (nuevo: number) => {
    const z = limitar(nuevo)
    setZoom(z)
    if (z <= 100) setDesplazamiento({ x: 0, y: 0 }) // sin zoom no hay nada que mover
  }
  const ajustar = () => { setZoom(100); setDesplazamiento({ x: 0, y: 0 }) }

  // Ctrl + rueda: hace falta un listener no pasivo para que la pagina no haga su propio zoom
  useEffect(() => {
    const elemento = marco.current
    if (!elemento) return
    const alRodar = (e: WheelEvent) => {
      if (!e.ctrlKey) return
      e.preventDefault()
      setZoom((z) => {
        const nuevo = limitar(z + (e.deltaY < 0 ? PASO_ZOOM : -PASO_ZOOM))
        if (nuevo <= 100) setDesplazamiento({ x: 0, y: 0 })
        return nuevo
      })
    }
    elemento.addEventListener('wheel', alRodar, { passive: false })
    return () => elemento.removeEventListener('wheel', alRodar)
  }, [])

  const puedeMover = zoom > 100
  const empezar = (e: PointerEvent<HTMLDivElement>) => {
    if (!puedeMover) return
    arrastre.current = { x: e.clientX, y: e.clientY, desdeX: desplazamiento.x, desdeY: desplazamiento.y }
    setArrastrando(true)
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const mover = (e: PointerEvent<HTMLDivElement>) => {
    const a = arrastre.current
    if (!a) return
    setDesplazamiento({ x: a.desdeX + e.clientX - a.x, y: a.desdeY + e.clientY - a.y })
  }
  const soltar = () => { arrastre.current = null; setArrastrando(false) }
  const teclas = (e: KeyboardEvent<HTMLDivElement>) => {
    const pasos: Record<string, [number, number]> = {
      ArrowLeft: [PASO_TECLADO, 0], ArrowRight: [-PASO_TECLADO, 0], ArrowUp: [0, PASO_TECLADO], ArrowDown: [0, -PASO_TECLADO],
    }
    if (e.key === '+' || e.key === '=') { e.preventDefault(); cambiarZoom(zoom + PASO_ZOOM) }
    else if (e.key === '-') { e.preventDefault(); cambiarZoom(zoom - PASO_ZOOM) }
    else if (e.key === '0') { e.preventDefault(); ajustar() }
    else if (puedeMover && pasos[e.key]) {
      e.preventDefault()
      const [dx, dy] = pasos[e.key]
      setDesplazamiento((d) => ({ x: d.x + dx, y: d.y + dy }))
    }
  }

  const boton = 'inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50'
  return (
    <div className="mt-2">
      <div role="toolbar" aria-label="Zoom de la imagen" className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => cambiarZoom(zoom - PASO_ZOOM)} disabled={zoom <= ZOOM_MIN} aria-label="Alejar" className={boton}>
          <ZoomOut className="size-3.5" aria-hidden /> −
        </button>
        <span className="min-w-12 text-center text-xs font-medium tabular-nums text-slate-700" data-testid="zoom" aria-live="polite">{zoom} %</span>
        <button type="button" onClick={() => cambiarZoom(zoom + PASO_ZOOM)} disabled={zoom >= ZOOM_MAX} aria-label="Acercar" className={boton}>
          <ZoomIn className="size-3.5" aria-hidden /> +
        </button>
        <button type="button" onClick={ajustar} disabled={zoom === 100 && desplazamiento.x === 0 && desplazamiento.y === 0} className={boton}>
          <Scan className="size-3.5" aria-hidden /> Ajustar
        </button>
        <span className="text-xs text-slate-500">Ctrl + rueda para hacer zoom{puedeMover ? '; arrastra para moverla' : ''}</span>
      </div>
      <div ref={marco} tabIndex={0} onKeyDown={teclas} onPointerDown={empezar} onPointerMove={mover} onPointerUp={soltar}
        onPointerCancel={soltar} data-testid="marco-zoom" role="group" aria-label={`${alt}. Con zoom, usa las flechas para moverla`}
        className={`relative mt-1 ${alto} w-full touch-none overflow-hidden rounded bg-slate-50 outline-offset-2 ${
          puedeMover ? (arrastrando ? 'cursor-grabbing' : 'cursor-grab') : ''}`}>
        <img alt={alt} src={url} draggable={false}
          style={{ transform: `translate(${desplazamiento.x}px, ${desplazamiento.y}px) scale(${zoom / 100})` }}
          className="h-full w-full select-none object-contain" />
      </div>
    </div>
  )
}

/** Dialogo de "Pantalla completa" con la misma URL; Esc o "Cerrar" lo cierran */
function VisorAmpliado({ url, alt, nombreArchivo, alCerrar }: { url: string; alt: string; nombreArchivo: string; alCerrar: () => void }) {
  const cerrar = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    cerrar.current?.focus()
    const alPulsar = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') alCerrar() }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [alCerrar])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-q-slate-700/80 p-4">
      <div role="dialog" aria-modal="true" aria-label={`Pantalla completa: ${nombreArchivo}`}
        className="flex h-full max-h-[95vh] w-full max-w-[95vw] flex-col rounded-lg bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-sm text-slate-700">{nombreArchivo}</p>
          <button ref={cerrar} type="button" onClick={alCerrar}
            className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-sm hover:bg-slate-100">
            <X className="size-4" aria-hidden /> Cerrar <span className="text-xs text-slate-500">(Esc)</span>
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <ImagenConZoom url={url} alt={alt} alto="h-[calc(95vh-7rem)]" />
        </div>
      </div>
    </div>
  )
}
