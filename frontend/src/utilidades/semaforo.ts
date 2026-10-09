// Vista del expediente pensada para el revisor: semaforo de cada documento, fase del folio y lo que queda
// por revisar. Todo se calcula en el cliente con los datos que ya da la API (sin cambios de contrato).
import type { Alerta, ResultadoDocumento, ResultadoExpediente, TipoDocumental } from '../tipos/contrato'
import { ETIQUETA_FASE_CORTA } from './etiquetas'
import { cuentaEnElFolio, enProceso, fichaDeTipo, nombreTipo, tipoEfectivo, tipoExtraccion } from './expediente'
import { nombreCampo, sinValor } from './valores'

export type ColorSemaforo = 'verde' | 'amarillo' | 'rojo' | 'en_proceso' | 'retirado'

export interface Semaforo {
  color: ColorSemaforo
  /** Texto corto junto al icono (el color nunca va solo) */
  etiqueta: string
  /** Una linea que explica que pasa y que hacer */
  explicacion: string
  /** Queda algo por hacer en el documento ("Lo que tienes que hacer"); un aviso ya confirmado no lo es */
  pendiente: boolean
}

/** Leyenda "Que significan los colores" */
export const LEYENDA_SEMAFORO: { color: Extract<ColorSemaforo, 'verde' | 'amarillo' | 'rojo'>; texto: string }[] = [
  { color: 'verde', texto: 'Se leyeron todos los datos.' },
  { color: 'amarillo', texto: 'falta algo o hay un aviso; revísalo o tenlo en cuenta al decidir.' },
  { color: 'rojo', texto: 'No se pudo leer nada o hubo un error; vuelve a subirlo.' },
]

export const NOMBRE_COLOR: Record<ColorSemaforo, string> = {
  verde: 'Verde', amarillo: 'Amarillo', rojo: 'Rojo', en_proceso: 'Gris', retirado: 'Gris',
}

/** Campos que se muestran del documento: los de su ficha y los que trae aunque no esten en ella */
export function camposDelDocumento(doc: ResultadoDocumento, ficha: TipoDocumental | undefined): string[] {
  return [...new Set([...Object.keys(ficha?.campos ?? {}), ...Object.keys(doc.datos_extraidos)])]
}

const plural = (n: number, uno: string, varios: string) => (n === 1 ? uno : varios.replace('N', String(n)))

/**
 * Semaforo de un documento (validado por PERSONA_1 en la revision del PR; gana la primera regla que se
 * cumple, lo mas grave siempre gana):
 * 1. retirado (ADR-013): gris "Retirado", aunque tenga avisos;
 * 2. pendiente o procesando: gris con la fase corta (ADR-014);
 * 3. rojo "No se pudo leer": el analisis acabo en error, o termino con TODOS los campos sin valor;
 * 4. rojo "Solo se puede rechazar": alguna alerta BLOQUEANTE del documento confirmada (aplica = true);
 * 5. amarillo "Tipo no reconocido: confirma el tipo": sin ficha (`desconocido` o sin tipo, ADR-009), traiga
 *    o no datos; los motivos de la regla 6 se anaden detras;
 * 6. amarillo con todos sus motivos, separados por " · " y en este orden: a) bloqueantes sin revisar ("N
 *    avisos impiden aprobar": puede ser un falso aviso, lo decide el revisor); b) no informativas y no
 *    bloqueantes sin revisar ("N avisos por revisar"); c) algun campo OBLIGATORIO sin valor ("Falta un
 *    dato"; los opcionales no cuentan, como VAL-001); d) alguna no bloqueante confirmada ("Aviso confirmado ·
 *    no impide aprobar": ya esta revisada, no es un pendiente);
 * 7. verde "Todo detectado".
 * No colorean: las informativas, los falsos avisos (aplica = false) ni las alertas del expediente.
 */
export function semaforoDocumento(doc: ResultadoDocumento, fichas: readonly TipoDocumental[]): Semaforo {
  // 1 y 2
  if (doc.retirado) return { color: 'retirado', etiqueta: 'Retirado', explicacion: 'No cuenta para la revisión del folio.', pendiente: false }
  if (enProceso(doc)) {
    return {
      color: 'en_proceso',
      etiqueta: doc.fase_analisis ? ETIQUETA_FASE_CORTA[doc.fase_analisis] : 'Analizando',
      explicacion: 'Se está analizando; la vista se actualiza sola.',
      pendiente: false,
    }
  }
  // 3
  if (doc.estado_analisis === 'error') {
    return { color: 'rojo', etiqueta: 'No se pudo leer', explicacion: 'Hubo un error al analizarlo; vuelve a subirlo.', pendiente: true }
  }
  const ficha = fichaDeTipo(fichas, tipoExtraccion(doc))
  const campos = camposDelDocumento(doc, ficha)
  if (campos.length > 0 && campos.every((c) => sinValor(doc.datos_extraidos[c]))) {
    return { color: 'rojo', etiqueta: 'No se pudo leer', explicacion: 'No se leyó ningún dato; vuelve a subirlo.', pendiente: true }
  }
  // 4
  const alertas = doc.alertas_encontradas.filter((a) => a.severidad !== 'informativa')
  const bloqueante = (a: Alerta) => a.severidad === 'bloqueante'
  if (alertas.some((a) => bloqueante(a) && a.aplica === true)) {
    return {
      color: 'rojo', etiqueta: 'Solo se puede rechazar',
      explicacion: 'Tiene un aviso confirmado que impide aprobar el folio.', pendiente: true,
    }
  }
  // 6: motivos del amarillo, en su orden
  const impiden = alertas.filter((a) => bloqueante(a) && a.aplica === null).length
  const porRevisar = alertas.filter((a) => !bloqueante(a) && a.aplica === null).length
  const faltan = Object.entries(ficha?.campos ?? {})
    .filter(([campo, def]) => def.obligatorio && sinValor(doc.datos_extraidos[campo]))
    .map(([campo]) => nombreCampo(campo))
  const confirmado = alertas.some((a) => !bloqueante(a) && a.aplica === true)
  const motivos = [
    impiden > 0 && plural(impiden, '1 aviso impide aprobar', 'N avisos impiden aprobar'),
    porRevisar > 0 && plural(porRevisar, '1 aviso por revisar', 'N avisos por revisar'),
    faltan.length > 0 && plural(faltan.length, 'Falta un dato', 'Faltan N datos'),
    confirmado && 'Aviso confirmado · no impide aprobar',
  ].filter((m): m is string => !!m)
  const explicacion = faltan.length > 0
    ? `No se detectó: ${faltan.join(', ')}. Revísalo en el original.`
    : impiden + porRevisar > 0 ? 'Revisa sus avisos en el detalle.' : 'Tiene un aviso confirmado; tenlo en cuenta al decidir.'
  // 5
  if (!ficha) {
    return {
      color: 'amarillo', etiqueta: ['Tipo no reconocido: confirma el tipo', ...motivos].join(' · '),
      explicacion: 'No se sabe qué documento es; confirma su tipo.', pendiente: true,
    }
  }
  // 6: es un pendiente salvo que solo quede un aviso confirmado (d)
  if (motivos.length > 0) return { color: 'amarillo', etiqueta: motivos.join(' · '), explicacion, pendiente: impiden + porRevisar + faltan.length > 0 }
  // 7
  return { color: 'verde', etiqueta: 'Todo detectado', explicacion: 'Se leyeron todos los datos.', pendiente: false }
}

// ------------------------------------------------------------------ fase del expediente

export type FaseExpediente = 'carga' | 'analisis' | 'revision' | 'decision'

export const PASOS_EXPEDIENTE: { fase: FaseExpediente; etiqueta: string }[] = [
  { fase: 'carga', etiqueta: 'Carga de documentos' },
  { fase: 'analisis', etiqueta: 'Análisis' },
  { fase: 'revision', etiqueta: 'Revisión' },
  { fase: 'decision', etiqueta: 'Decisión' },
]

/**
 * Fase del folio: decision si ya esta aprobado o rechazado; carga si no tiene documentos (que cuenten);
 * analisis si alguno esta pendiente o procesando; si no, revision.
 */
export function faseExpediente(expediente: Pick<ResultadoExpediente, 'estado_general' | 'documentos'>): FaseExpediente {
  if (expediente.estado_general !== 'en_revision') return 'decision'
  const documentos = expediente.documentos.filter(cuentaEnElFolio)
  if (documentos.length === 0) return 'carga'
  if (documentos.some(enProceso)) return 'analisis'
  return 'revision'
}

// ------------------------------------------------------------------ lo que queda por revisar

/** Alertas sin revisar (aplica = null) y no informativas, del expediente y de los documentos que cuentan */
export function pendientesDeRevisar(expediente: Pick<ResultadoExpediente, 'documentos' | 'alertas_expediente'>): Alerta[] {
  return [...expediente.alertas_expediente, ...expediente.documentos.filter(cuentaEnElFolio).flatMap((d) => d.alertas_encontradas)]
    .filter((a) => a.aplica === null && a.severidad !== 'informativa')
}

/** Bloqueantes ya confirmadas como reales (aplica = true): estan revisadas, pero solo se puede rechazar */
export function hayBloqueantesConfirmadas(expediente: Pick<ResultadoExpediente, 'documentos' | 'alertas_expediente'>): boolean {
  return [...expediente.alertas_expediente, ...expediente.documentos.filter(cuentaEnElFolio).flatMap((d) => d.alertas_encontradas)]
    .some((a) => a.severidad === 'bloqueante' && a.aplica === true)
}

/** "A y B", "A, B y C" */
export function enumerar(partes: string[]): string {
  return partes.length <= 1 ? (partes[0] ?? '') : `${partes.slice(0, -1).join(', ')} y ${partes.at(-1)}`
}

/** Nombres de tipo de los documentos de una comparacion, en el orden de `valores` */
export function tiposComparados(valores: Record<string, unknown>, documentos: readonly ResultadoDocumento[],
  fichas: readonly TipoDocumental[]): string[] {
  return Object.keys(valores).map((id) => {
    const doc = documentos.find((d) => d.identificador_unico_documento === id)
    return doc ? nombreTipo(tipoEfectivo(doc), fichas, 'Sin tipo') : 'Documento'
  })
}

export interface Tarea {
  clave: string
  texto: string
  /** Documento al que lleva; null = la lista de documentos (alertas del expediente) */
  documento: string | null
}

/**
 * "Lo que tienes que hacer": documentos en rojo o en amarillo con algo pendiente (no los que solo tienen un
 * aviso ya confirmado), alertas sin revisar (de documento y de expediente) y comparaciones que no
 * coinciden. Solo los documentos que cuentan (ADR-013).
 */
export function tareasDelRevisor(expediente: ResultadoExpediente, fichas: readonly TipoDocumental[]): Tarea[] {
  const tareas: Tarea[] = []
  const documentos = expediente.documentos.filter(cuentaEnElFolio)
  for (const d of documentos) {
    const id = d.identificador_unico_documento
    const s = semaforoDocumento(d, fichas)
    const nombre = nombreTipo(tipoEfectivo(d), fichas, 'Sin tipo')
    if (s.pendiente) tareas.push({ clave: `doc-${id}`, texto: `${nombre}: ${s.etiqueta}. ${s.explicacion}`, documento: id })
    d.alertas_encontradas.filter((a) => a.aplica === null && a.severidad !== 'informativa').forEach((a, i) => {
      tareas.push({ clave: `alerta-${a.id ?? `${id}-${i}`}`, texto: `${nombre}: revisa el aviso ${a.codigo} (${a.mensaje})`, documento: id })
    })
  }
  expediente.alertas_expediente.filter((a) => a.aplica === null && a.severidad !== 'informativa').forEach((a, i) => {
    tareas.push({ clave: `alerta-exp-${a.id ?? i}`, texto: `Expediente: revisa el aviso ${a.codigo} (${a.mensaje})`, documento: null })
  })
  for (const c of expediente.comparaciones.filter((x) => !x.coincide)) {
    const tipos = tiposComparados(c.valores, documentos, fichas)
    tareas.push({
      clave: `cmp-${c.campo}`,
      texto: `${nombreCampo(c.campo)}: no coincide entre ${enumerar(tipos)}`,
      documento: Object.keys(c.valores)[0] ?? null,
    })
  }
  return tareas
}
