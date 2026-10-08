import { CircleX, Clock, Pencil } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Correccion, ResultadoDocumento, Rol, TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_ESTADO_ANALISIS, fechaHora } from '../utilidades/etiquetas'
import { enProceso, fichaDeTipo, nombreTipo, tipoExtraccion } from '../utilidades/expediente'
import { formatearValor, nombreCampo } from '../utilidades/valores'
import { BarraConfianza } from './BarraConfianza'
import { DatoSensible } from './DatoSensible'
import { TextoRecomendacion } from './Insignias'
import { SoloRol } from './SoloRol'
import { VisorOriginal } from './VisorOriginal'

interface Props {
  doc: ResultadoDocumento
  fichas: TipoDocumental[]
  /** GET /documentos/{id}/original solo para revisor y admin */
  puedeVerOriginal: boolean
  /** Acciones del revisor sobre la clasificacion (bloque H); sin ellas, solo lectura */
  accionesClasificacion?: ReactNode
  /** Celda de valor editable (bloque H); sin ella, el valor formateado */
  celdaValor?: (campo: string, contenido: ReactNode) => ReactNode
}

/** POST /documentos/{id}/revelar (ADR-010 A4): el integrador nunca ve "Mostrar" */
const ROLES_REVELAR: readonly Rol[] = ['revisor', 'admin']

/** Ultima correccion de cada campo (ADR-006 2.4) */
function ultimasCorrecciones(correcciones: Correccion[]): Map<string, Correccion> {
  return new Map(correcciones.map((c) => [c.campo, c]))
}

export function DetalleDocumento({ doc, fichas, puedeVerOriginal, accionesClasificacion, celdaValor }: Props) {
  // `desconocido` (ADR-009) nunca tiene ficha: "Tipo no reconocido", sin umbral ni campos
  const ficha = (tipo: string | null) => fichaDeTipo(fichas, tipo)
  const nombreVisible = (tipo: string | null) => nombreTipo(tipo, fichas, '—')
  const fichaExtraccion = ficha(tipoExtraccion(doc))
  const correcciones = ultimasCorrecciones(doc.correcciones)
  const campos = [...new Set([...Object.keys(fichaExtraccion?.campos ?? {}), ...Object.keys(doc.datos_extraidos)])]
  // H4: sin ficha para el tipo de extraccion y sin datos, un aviso en vez de una tabla vacia
  const sinDatosNiFicha = !fichaExtraccion && campos.length === 0
  const fallos = doc.alertas_encontradas.filter((a) => a.codigo.startsWith('SYS-') && a.severidad !== 'informativa')
  const nombre = doc.referencia_archivo_original.nombre_archivo

  return (
    // ADR-013: un documento retirado sigue visible, atenuado y marcado
    <article aria-labelledby="titulo-documento" className={`space-y-4 ${doc.retirado ? 'opacity-60' : ''}`}>
      <header>
        <h2 id="titulo-documento" className="text-base font-semibold">
          <span className="font-mono">{nombre}</span>
          {doc.retirado && <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-xs font-normal text-slate-700">Retirado</span>}
        </h2>
        <p className="text-sm text-slate-600">
          Estado del análisis: <span className="font-medium">{ETIQUETA_ESTADO_ANALISIS[doc.estado_analisis]}</span>
          {doc.estado_analisis === 'completado' && <> · Recomendación: <TextoRecomendacion valor={doc.recomendacion} /></>}
        </p>
      </header>

      {enProceso(doc) && (
        <p role="status" className="flex items-center gap-2 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
          <Clock className="size-4" aria-hidden /> El documento se está analizando; la vista se actualiza sola.
        </p>
      )}
      {doc.estado_analisis === 'error' && (
        <div role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
          <p className="flex items-center gap-2 font-medium"><CircleX className="size-4" aria-hidden /> El análisis de este documento falló.</p>
          {fallos.map((a, i) => <p key={a.id ?? i} className="mt-1"><span className="font-mono">{a.codigo}</span>: {a.mensaje}</p>)}
          {/* Fallo de S3 o excepcion del motor: la API lo deja en error sin resultado ni SYS-00x (ingesta/README.md) */}
          {fallos.length === 0 && (
            <p className="mt-1">No se pudo procesar el archivo (fallo al leerlo o del motor de análisis) y no hay más detalle.</p>
          )}
          <p className="mt-1 text-red-800">Reprocesar un documento en error queda fuera del MVP: sube de nuevo el archivo si hace falta.</p>
        </div>
      )}

      {puedeVerOriginal
        ? <VisorOriginal documentoId={doc.identificador_unico_documento} nombreArchivo={nombre} />
        : <p className="text-sm text-slate-500">Tu rol no puede ver el original del documento.</p>}

      <section aria-label="Clasificación">
        <h3 className="text-sm font-semibold">Clasificación</h3>
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-slate-600">Declarado</dt><dd>{nombreVisible(doc.tipo_documental_declarado)}</dd>
          <dt className="text-slate-600">Detectado</dt><dd>{nombreVisible(doc.tipo_documental_detectado)}</dd>
          <dt className="text-slate-600">Confirmado por el revisor</dt><dd>{nombreVisible(doc.tipo_documental_confirmado)}</dd>
          <dt className="text-slate-600">Confianza</dt>
          <dd>
            <BarraConfianza valor={doc.confianza_clasificacion} de="la clasificación"
              minimo={ficha(doc.tipo_documental_detectado)?.confianza_minima_clasificacion ?? null} />
          </dd>
        </dl>
        {accionesClasificacion}
      </section>

      {doc.estado_analisis === 'completado' && sinDatosNiFicha && (
        <p role="status" className="rounded border border-q-orange-100 bg-q-orange-50 px-3 py-2 text-sm text-q-orange-700">
          No se han extraído datos: el tipo del documento no está reconocido. Confirma la clasificación para
          analizarlo con la ficha correcta.
        </p>
      )}
      {doc.estado_analisis === 'completado' && !sinDatosNiFicha && (
        <section aria-label="Datos extraídos">
          <h3 className="text-sm font-semibold">Datos extraídos</h3>
          <table className="mt-1 w-full border-collapse bg-white text-sm">
            <caption className="sr-only">Datos extraídos del documento con su confianza verificada y evidencia</caption>
            <thead className="bg-slate-100 text-left">
              <tr>{['Campo', 'Valor', 'Confianza verificada', 'Evidencia'].map((c) => <th key={c} scope="col" className="px-2 py-1.5 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {campos.map((campo) => {
                const correccion = correcciones.get(campo)
                const tipo = fichaExtraccion?.campos[campo]?.tipo
                const enmascarado = (
                  <span className={doc.datos_extraidos[campo] == null ? 'italic text-slate-500' : ''}>
                    {formatearValor(doc.datos_extraidos[campo], tipo)}
                  </span>
                )
                // Dato sensible con valor (ADR-010): llega enmascarado; revisor y admin pueden "Mostrar" (H17).
                // Solo aqui: comparaciones, evidencia y correcciones siguen enmascaradas
                const sensible = fichaExtraccion?.campos[campo]?.sensible === true && doc.datos_extraidos[campo] != null
                const valor = (
                  <>
                    {sensible
                      ? (
                        <SoloRol roles={ROLES_REVELAR} alternativa={enmascarado}>
                          {/* key: cambiar de documento o que cambie el dato olvida lo revelado */}
                          <DatoSensible key={`${doc.identificador_unico_documento}:${String(doc.datos_extraidos[campo])}`}
                            documentoId={doc.identificador_unico_documento} campo={campo} tipo={tipo}>
                            {enmascarado}
                          </DatoSensible>
                        </SoloRol>
                      )
                      : enmascarado}
                    {correccion && (
                      <span className="mt-0.5 flex items-center gap-1 text-xs text-q-orange-700">
                        <Pencil className="size-3" aria-hidden /> Corregido por revisor (antes: {formatearValor(correccion.valor_anterior, tipo)})
                      </span>
                    )}
                  </>
                )
                return (
                  <tr key={campo} className="border-t border-slate-200 align-top">
                    <th scope="row" className="px-2 py-1.5 text-left font-normal">{nombreCampo(campo)}</th>
                    <td className="px-2 py-1.5">{celdaValor ? celdaValor(campo, valor) : valor}</td>
                    <td className="px-2 py-1.5">
                      <BarraConfianza valor={doc.nivel_confianza_por_campo[campo] ?? null} de={nombreCampo(campo)}
                        minimo={fichaExtraccion?.confianza_minima_campo ?? null} />
                    </td>
                    <td className="px-2 py-1.5 font-mono text-xs text-slate-600">{doc.evidencia_por_campo[campo] ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-2 text-sm">
            Reglas: {doc.reglas_cumplidas_e_incumplidas.cumplidas.length} cumplidas
            {doc.reglas_cumplidas_e_incumplidas.incumplidas.length > 0 && <> · incumplidas: <span className="font-mono">{doc.reglas_cumplidas_e_incumplidas.incumplidas.join(', ')}</span></>}
          </p>
        </section>
      )}

      {doc.fecha_y_modelo_utilizado && (
        <p className="text-xs text-slate-600">
          Analizado el {fechaHora(doc.fecha_y_modelo_utilizado.fecha_analisis)} con {doc.fecha_y_modelo_utilizado.proveedor} ·
          modelo <span className="font-mono">{doc.fecha_y_modelo_utilizado.modelo}</span> · prompt <span className="font-mono">{doc.fecha_y_modelo_utilizado.version_prompt}</span>
        </p>
      )}
    </article>
  )
}
