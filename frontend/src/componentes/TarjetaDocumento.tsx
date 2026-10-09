import { ArchiveRestore, FileImage, FileText, Upload } from 'lucide-react'
import { Link } from 'react-router'
import type { ResultadoDocumento, TipoDocumental } from '../tipos/contrato'
import { nombreTipo, tipoEfectivo } from '../utilidades/expediente'
import { semaforoDocumento } from '../utilidades/semaforo'
import { ESTILO_SEMAFORO } from './estiloSemaforo'
import { InsigniaSemaforo } from './Semaforo'

interface Props {
  doc: ResultadoDocumento
  fichas: readonly TipoDocumental[]
  /** Enlace al detalle (?doc=) */
  rutaDetalle: string
  /** "Abrir y revisar" para el revisor; "Abrir" para los demas roles */
  textoAbrir: string
  /** Enlace a la pestana de carga para "Volver a subir"; sin el (rol sin permiso o folio cerrado), sin boton */
  rutaCarga?: string
  /** Restaurar un retirado (ADR-013); sin el, sin boton */
  alRestaurar?: () => void
  deshabilitado: boolean
}

const esPdf = (nombre: string) => nombre.toLowerCase().endsWith('.pdf')

/**
 * Tarjeta de un documento en la rejilla. Sin miniatura del original: pedirlo dejaria `original_visto` en la
 * auditoria por cada documento solo por abrir el folio (ADR-010 A4b); un icono del tipo de archivo en su lugar.
 */
export function TarjetaDocumento({ doc, fichas, rutaDetalle, textoAbrir, rutaCarga, alRestaurar, deshabilitado }: Props) {
  const semaforo = semaforoDocumento(doc, fichas)
  const id = doc.identificador_unico_documento
  const nombre = doc.referencia_archivo_original.nombre_archivo
  const Icono = esPdf(nombre) ? FileText : FileImage
  const tipo = nombreTipo(tipoEfectivo(doc), fichas, 'Sin tipo')
  const boton = 'inline-flex items-center justify-center gap-1 rounded-[10px] border px-3 py-1.5 text-sm font-medium'
  return (
    <article aria-labelledby={`tarjeta-${id}`} data-testid={`tarjeta-${id}`}
      className={`flex flex-col rounded-lg border bg-white p-3 ${ESTILO_SEMAFORO[semaforo.color].caja.split(' ')[0]}`}>
      <div className="flex items-start gap-3">
        <div className="flex size-14 shrink-0 items-center justify-center rounded bg-q-slate-50 text-q-slate-400" aria-hidden>
          <Icono className="size-7" />
        </div>
        <div className="min-w-0">
          <InsigniaSemaforo semaforo={semaforo} id={id} />
          <h3 id={`tarjeta-${id}`} className="mt-1 font-semibold">{tipo}</h3>
          <p className="truncate font-mono text-xs text-slate-600" title={nombre}>{nombre}</p>
        </div>
      </div>
      <p className="mt-2 flex-1 text-sm text-slate-700">{semaforo.explicacion}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {semaforo.color === 'rojo' && rutaCarga && (
          <Link to={rutaCarga} className={`${boton} border-q-orange bg-q-orange text-q-slate hover:bg-q-orange-300`}>
            <Upload className="size-4" aria-hidden /> Volver a subir
          </Link>
        )}
        <Link to={rutaDetalle} aria-label={`${textoAbrir} ${nombre}`}
          className={`${boton} border-q-slate text-q-slate hover:bg-q-slate-50`}>{textoAbrir}</Link>
        {doc.retirado && alRestaurar && (
          <button type="button" onClick={alRestaurar} disabled={deshabilitado} aria-label={`Restaurar ${nombre}`}
            className={`${boton} border-slate-500 bg-white disabled:opacity-50`}>
            <ArchiveRestore className="size-4" aria-hidden /> Restaurar
          </button>
        )}
      </div>
    </article>
  )
}
