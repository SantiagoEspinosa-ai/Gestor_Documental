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
}

/** Leyenda "Que significan los colores" */
export const LEYENDA_SEMAFORO: { color: Extract<ColorSemaforo, 'verde' | 'amarillo' | 'rojo'>; texto: string }[] = [
  { color: 'verde', texto: 'Se leyeron todos los datos.' },
  { color: 'amarillo', texto: 'Falta algún dato; revísalo en el original.' },
  { color: 'rojo', texto: 'No se pudo leer nada o hubo un error; vuelve a subirlo.' },
]

export const NOMBRE_COLOR: Record<ColorSemaforo, string> = {
  verde: 'Verde', amarillo: 'Amarillo', rojo: 'Rojo', en_proceso: 'Gris', retirado: 'Gris',
}

/** Campos que se muestran del documento: los de su ficha y los que trae aunque no esten en ella */
export function camposDelDocumento(doc: ResultadoDocumento, ficha: TipoDocumental | undefined): string[] {
  return [...new Set([...Object.keys(ficha?.campos ?? {}), ...Object.keys(doc.datos_extraidos)])]
}

/**
 * Semaforo de un documento (acordado el 2026-10-09; lo valida PERSONA_1 en el PR):
 * - retirado (ADR-013): gris "Retirado", aunque se hubiera analizado;
 * - pendiente o procesando: gris con la fase corta (ADR-014);
 * - rojo "No se pudo leer": el analisis acabo en error, o termino con TODOS los campos sin valor;
 * - amarillo "Tipo no reconocido": `desconocido` (o sin tipo) sin ficha y sin datos (ADR-009): se arregla
 *   confirmando el tipo, no volviendo a subirlo;
 * - amarillo "Falta un dato": algun campo OBLIGATORIO de la ficha sin valor. Los opcionales vacios no
 *   cambian el color (como VAL-001), aunque en el detalle salen como "No detectado";
 * - verde "Todo detectado": ningun obligatorio sin valor.
 */
export function semaforoDocumento(doc: ResultadoDocumento, fichas: readonly TipoDocumental[]): Semaforo {
  if (doc.retirado) return { color: 'retirado', etiqueta: 'Retirado', explicacion: 'No cuenta para la revisión del folio.' }
  if (enProceso(doc)) {
    return {
      color: 'en_proceso',
      etiqueta: doc.fase_analisis ? ETIQUETA_FASE_CORTA[doc.fase_analisis] : 'Analizando',
      explicacion: 'Se está analizando; la vista se actualiza sola.',
    }
  }
  if (doc.estado_analisis === 'error') {
    return { color: 'rojo', etiqueta: 'No se pudo leer', explicacion: 'Hubo un error al analizarlo; vuelve a subirlo.' }
  }
  const ficha = fichaDeTipo(fichas, tipoExtraccion(doc))
  const campos = camposDelDocumento(doc, ficha)
  if (!ficha && campos.length === 0) {
    return { color: 'amarillo', etiqueta: 'Tipo no reconocido', explicacion: 'No se sabe qué documento es; confirma su tipo.' }
  }
  if (campos.length > 0 && campos.every((c) => sinValor(doc.datos_extraidos[c]))) {
    return { color: 'rojo', etiqueta: 'No se pudo leer', explicacion: 'No se leyó ningún dato; vuelve a subirlo.' }
  }
  const faltan = Object.entries(ficha?.campos ?? {})
    .filter(([campo, def]) => def.obligatorio && sinValor(doc.datos_extraidos[campo]))
    .map(([campo]) => nombreCampo(campo))
  if (faltan.length > 0) {
    return {
      color: 'amarillo',
      etiqueta: faltan.length === 1 ? 'Falta un dato' : `Faltan ${faltan.length} datos`,
      explicacion: `No se detectó: ${faltan.join(', ')}. Revísalo en el original.`,
    }
  }
  return { color: 'verde', etiqueta: 'Todo detectado', explicacion: 'Se leyeron todos los datos.' }
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
 * "Lo que tienes que hacer": documentos en amarillo o rojo, alertas sin revisar (de documento y de
 * expediente) y comparaciones que no coinciden. Solo los documentos que cuentan (ADR-013).
 */
export function tareasDelRevisor(expediente: ResultadoExpediente, fichas: readonly TipoDocumental[]): Tarea[] {
  const tareas: Tarea[] = []
  const documentos = expediente.documentos.filter(cuentaEnElFolio)
  for (const d of documentos) {
    const id = d.identificador_unico_documento
    const s = semaforoDocumento(d, fichas)
    const nombre = nombreTipo(tipoEfectivo(d), fichas, 'Sin tipo')
    if (s.color === 'amarillo' || s.color === 'rojo') tareas.push({ clave: `doc-${id}`, texto: `${nombre}: ${s.etiqueta}. ${s.explicacion}`, documento: id })
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
