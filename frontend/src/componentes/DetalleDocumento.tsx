import { AlertTriangle, CircleX, Pencil } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { TIPO_DESCONOCIDO, type Correccion, type ResultadoDocumento, type Rol, type TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_ESTADO_ANALISIS, fechaHora } from '../utilidades/etiquetas'
import { enProceso, fichaDeTipo, nombreTipo, tipoExtraccion } from '../utilidades/expediente'
import { camposDelDocumento, semaforoDocumento } from '../utilidades/semaforo'
import { formatearValor, nombreCampo, sinValor } from '../utilidades/valores'
import { AvisoAnalisis } from './AvisoAnalisis'
import { BarraConfianza } from './BarraConfianza'
import { DatoSensible } from './DatoSensible'
import { TextoRecomendacion } from './Insignias'
import { InsigniaSemaforo } from './Semaforo'
import { SoloRol } from './SoloRol'
import { VisorOriginal } from './VisorOriginal'

interface Props {
  doc: ResultadoDocumento
  fichas: TipoDocumental[]
  /** GET /documentos/{id}/original solo para revisor y admin */
  puedeVerOriginal: boolean
  /** Usuario de la sesion: "Corregido por ti" */
  usuario: string | null
  /** Avisos del documento con su revision (lista de alertas) */
  avisos: ReactNode
  /** Acciones del revisor sobre la clasificacion (bloque H); sin ellas, solo lectura */
  accionesClasificacion?: ReactNode
  /** Celda de valor editable (bloque H); sin ella, el valor formateado */
  celdaValor?: (campo: string, contenido: ReactNode) => ReactNode
  /** Retirar o restaurar (ADR-013); sin ello, nada */
  retirar?: ReactNode
}

/** POST /documentos/{id}/revelar (ADR-010 A4): el integrador nunca ve "Mostrar" */
const ROLES_REVELAR: readonly Rol[] = ['revisor', 'admin']

/** Ultima correccion de cada campo (ADR-006 2.4) */
function ultimasCorrecciones(correcciones: Correccion[]): Map<string, Correccion> {
  return new Map(correcciones.map((c) => [c.campo, c]))
}

/**
 * Detalle de un documento: el original grande a la izquierda y, a la derecha, en este orden: avisos, tipo de
 * documento, datos leidos y retirar. Los detalles tecnicos (confianza, evidencia, reglas, modelo y prompt) no
 * se borran: van plegados al final, por auditoria, con el mismo enmascaramiento que antes.
 */
export function DetalleDocumento({ doc, fichas, puedeVerOriginal, usuario, avisos, accionesClasificacion, celdaValor, retirar }: Props) {
  // `desconocido` (ADR-009) nunca tiene ficha: "Tipo no reconocido", sin umbral ni campos
  const ficha = (tipo: string | null) => fichaDeTipo(fichas, tipo)
  const nombreVisible = (tipo: string | null) => nombreTipo(tipo, fichas, '—')
  const tipoActual = tipoExtraccion(doc)
  const fichaExtraccion = ficha(tipoActual)
  const correcciones = ultimasCorrecciones(doc.correcciones)
  const campos = camposDelDocumento(doc, fichaExtraccion)
  // H4: sin ficha para el tipo de extraccion y sin datos, un aviso en vez de una tabla vacia
  const sinDatosNiFicha = !fichaExtraccion && campos.length === 0
  const fallos = doc.alertas_encontradas.filter((a) => a.codigo.startsWith('SYS-') && a.severidad !== 'informativa')
  const nombre = doc.referencia_archivo_original.nombre_archivo
  // Sin tipo reconocido el cambio de tipo es lo primero que hay que hacer: el formulario sale abierto
  const [cambiandoTipo, setCambiandoTipo] = useState(!tipoActual || tipoActual === TIPO_DESCONOCIDO)

  return (
    // ADR-013: un documento retirado sigue visible y marcado
    <article aria-labelledby="titulo-documento" className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h2 id="titulo-documento" className="text-lg font-semibold">{nombreTipo(tipoActual, fichas, 'Sin tipo')}</h2>
        <InsigniaSemaforo semaforo={semaforoDocumento(doc, fichas)} id={doc.identificador_unico_documento} />
        <span className="font-mono text-xs text-slate-600">{nombre}</span>
      </header>

      {enProceso(doc) && <AvisoAnalisis fase={doc.fase_analisis} documento={doc.identificador_unico_documento} />}
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

      <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div>
          {puedeVerOriginal
            ? <VisorOriginal documentoId={doc.identificador_unico_documento} nombreArchivo={nombre} />
            : <p className="rounded border border-slate-200 bg-white p-3 text-sm text-slate-600">Tu rol no puede ver el original del documento.</p>}
        </div>

        <div className={`space-y-4 ${doc.retirado ? 'opacity-80' : ''}`}>
          {doc.retirado && retirar}
          {avisos}

          <section aria-label="Tipo de documento" className="rounded-lg border border-q-slate-100 bg-white p-3 text-sm">
            <h3 className="font-semibold">Tipo de documento</h3>
            <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
              <p data-testid="tipo-documento">{nombreTipo(tipoActual, fichas, 'Sin tipo')}</p>
              {accionesClasificacion && !cambiandoTipo && (
                <button type="button" onClick={() => setCambiandoTipo(true)}
                  className="inline-flex items-center gap-1 rounded border border-slate-400 px-2 py-0.5 text-xs">
                  <Pencil className="size-3" aria-hidden /> Cambiar tipo
                </button>
              )}
            </div>
            {accionesClasificacion && cambiandoTipo && accionesClasificacion}
          </section>

          {doc.estado_analisis === 'completado' && sinDatosNiFicha && (
            <p role="status" className="rounded border border-q-orange-100 bg-q-orange-50 px-3 py-2 text-sm text-q-orange-700">
              No se han extraído datos: el tipo del documento no está reconocido. Confirma la clasificación para
              analizarlo con la ficha correcta.
            </p>
          )}
          {doc.estado_analisis === 'completado' && !sinDatosNiFicha && (
            <section aria-label="Datos leídos" className="rounded-lg border border-q-slate-100 bg-white p-3">
              <h3 className="text-sm font-semibold">Datos leídos</h3>
              <table className="mt-1 w-full border-collapse text-sm">
                <caption className="sr-only">Datos leídos del documento</caption>
                <thead className="sr-only"><tr><th scope="col">Campo</th><th scope="col">Valor</th></tr></thead>
                <tbody>
                  {campos.map((campo) => {
                    const correccion = correcciones.get(campo)
                    const tipo = fichaExtraccion?.campos[campo]?.tipo
                    const vacio = sinValor(doc.datos_extraidos[campo])
                    const enmascarado = vacio
                      ? (
                        <span className="inline-flex items-center gap-1 font-medium text-semaforo-ambar">
                          <AlertTriangle className="size-3.5" aria-hidden /> No detectado · míralo en el original
                        </span>
                      )
                      : <span>{formatearValor(doc.datos_extraidos[campo], tipo)}</span>
                    // Dato sensible con valor (ADR-010): llega enmascarado; revisor y admin pueden "Mostrar" (H17).
                    // Solo aqui: comparaciones, evidencia y correcciones siguen enmascaradas
                    const sensible = fichaExtraccion?.campos[campo]?.sensible === true && !vacio
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
                            <Pencil className="size-3" aria-hidden />
                            Corregido por {correccion.usuario === usuario ? 'ti' : correccion.usuario} (antes: {formatearValor(correccion.valor_anterior, tipo)})
                          </span>
                        )}
                      </>
                    )
                    return (
                      <tr key={campo} className={`border-t border-slate-200 align-top ${vacio ? 'bg-semaforo-ambar-fondo' : ''}`}>
                        <th scope="row" className="w-2/5 px-2 py-1.5 text-left font-normal text-slate-700">{nombreCampo(campo)}</th>
                        <td className="px-2 py-1.5">{celdaValor ? celdaValor(campo, valor) : valor}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </section>
          )}

          {retirar && !doc.retirado && (
            <details className="rounded-lg border border-q-slate-100 bg-white p-3 text-sm">
              <summary className="cursor-pointer font-medium">Retirar este documento del expediente</summary>
              <p className="mt-1 text-xs text-slate-600">Si se subió por error: deja de contar para la revisión, no se borra y se puede restaurar.</p>
              <div className="mt-2">{retirar}</div>
            </details>
          )}

          <details className="rounded-lg border border-q-slate-100 bg-white p-3 text-sm" data-testid="detalles-tecnicos">
            <summary className="cursor-pointer font-medium">Detalles técnicos</summary>
            <section aria-label="Clasificación" className="mt-2">
              <h4 className="text-xs font-semibold uppercase text-slate-600">Clasificación</h4>
              <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                <dt className="text-slate-600">Estado del análisis</dt><dd>{ETIQUETA_ESTADO_ANALISIS[doc.estado_analisis]}</dd>
                <dt className="text-slate-600">Recomendación</dt><dd><TextoRecomendacion valor={doc.recomendacion} /></dd>
                <dt className="text-slate-600">Declarado</dt><dd>{nombreVisible(doc.tipo_documental_declarado)}</dd>
                <dt className="text-slate-600">Detectado</dt><dd>{nombreVisible(doc.tipo_documental_detectado)}</dd>
                <dt className="text-slate-600">Confirmado por el revisor</dt><dd>{nombreVisible(doc.tipo_documental_confirmado)}</dd>
                <dt className="text-slate-600">Confianza</dt>
                <dd>
                  <BarraConfianza valor={doc.confianza_clasificacion} de="la clasificación"
                    minimo={ficha(doc.tipo_documental_detectado)?.confianza_minima_clasificacion ?? null} />
                </dd>
              </dl>
            </section>
            {campos.length > 0 && (
              <table className="mt-3 w-full border-collapse text-sm">
                <caption className="sr-only">Confianza verificada y evidencia de cada campo</caption>
                <thead className="bg-slate-100 text-left">
                  <tr>{['Campo', 'Confianza verificada', 'Evidencia'].map((c) => <th key={c} scope="col" className="px-2 py-1.5 font-medium">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {campos.map((campo) => (
                    <tr key={campo} className="border-t border-slate-200 align-top" data-testid={`tecnico-${campo}`}>
                      <td className="px-2 py-1.5">{nombreCampo(campo)}</td>
                      <td className="px-2 py-1.5">
                        <BarraConfianza valor={doc.nivel_confianza_por_campo[campo] ?? null} de={nombreCampo(campo)}
                          minimo={fichaExtraccion?.confianza_minima_campo ?? null} />
                      </td>
                      {/* La evidencia tal como llega de la API (enmascarada igual que antes) */}
                      <td className="px-2 py-1.5 font-mono text-xs text-slate-600">{doc.evidencia_por_campo[campo] ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {doc.estado_analisis === 'completado' && (
              <p className="mt-2">
                Reglas: {doc.reglas_cumplidas_e_incumplidas.cumplidas.length} cumplidas
                {doc.reglas_cumplidas_e_incumplidas.incumplidas.length > 0 && <> · incumplidas: <span className="font-mono">{doc.reglas_cumplidas_e_incumplidas.incumplidas.join(', ')}</span></>}
              </p>
            )}
            {doc.fecha_y_modelo_utilizado && (
              <p className="mt-2 text-xs text-slate-600">
                Analizado el {fechaHora(doc.fecha_y_modelo_utilizado.fecha_analisis)} con {doc.fecha_y_modelo_utilizado.proveedor} ·
                modelo <span className="font-mono">{doc.fecha_y_modelo_utilizado.modelo}</span> · prompt <span className="font-mono">{doc.fecha_y_modelo_utilizado.version_prompt}</span>
              </p>
            )}
          </details>
        </div>
      </div>
    </article>
  )
}
