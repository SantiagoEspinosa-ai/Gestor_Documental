// Logica de negocio simulada de los mocks: la minima para que el estado en memoria sea coherente
// con el contrato (reglas de ADR-006). No sustituye a validacion ni a expediente del backend.
import type { Alerta, ResultadoDocumento, ResultadoExpediente, ResumenFolio, Severidad, TipoDocumental } from '../tipos/contrato'
import {
  alertasQueBloquean, bloquea, enProceso, tipoEfectivo, tipoExtraccion, tipoNoPrevisto, tiposRequeridosQueFaltan,
} from '../utilidades/expediente'
import { sinValor } from '../utilidades/valores'
import { auditar, fechaIso, siguiente, type EstadoMock, type Procesamiento } from './estado'

/** pendiente -> procesando a los 3 s, -> completado a los 9 s */
export const MS_HASTA_PROCESANDO = 3_000
export const MS_HASTA_COMPLETADO = 9_000
// Modelos de .env.example (PERSONA_2, docs/motor_ia/pruebas_ollama.md). Siempre Ollama: con
// PERMITIR_PROVEEDORES_NO_PRIVADOS=false el respaldo comercial no se usa nunca (ADR-003), asi que no hay SYS-005.
const PROVEEDOR = 'ollama'
export const MODELO_TEXTO = 'gemma4:e2b' // pdf_digital
export const MODELO_VISION = 'qwen2.5vl:3b' // pdf_escaneado e imagen
const VERSION_PROMPT = 'extraccion@v1'

/**
 * Modelo con el que se "analiza" un documento subido: el del documento de los datos con el mismo
 * SHA-256 (sabe si es digital o escaneado); si no hay, por la extension: imagen -> vision, PDF -> texto
 * (el mock no distingue un PDF escaneado de uno digital).
 */
function modeloDeAnalisis(doc: ResultadoDocumento, proc: Procesamiento): string {
  if (proc.origen?.fecha_y_modelo_utilizado) return proc.origen.fecha_y_modelo_utilizado.modelo
  return /\.pdf$/i.test(doc.referencia_archivo_original.nombre_archivo) ? MODELO_TEXTO : MODELO_VISION
}

export function normalizar(valor: unknown): string {
  return String(valor).normalize('NFKD').replace(/[̀-ͯ]/g, '').toUpperCase().split(/\s+/).filter(Boolean).join(' ')
}

/** Un campo sin valor es null, nunca "" ni solo espacios (VAL-001 y VAL-004: "ausente o null") */
export function valorOnull(valor: unknown): unknown {
  return sinValor(valor) ? null : valor
}

export { bloquea, enProceso, tipoExtraccion }
const pesa = (a: Alerta) => (a.severidad === 'critica' || a.severidad === 'bloqueante') && a.aplica !== false

export function ficha(estado: EstadoMock, tipo: string | null): TipoDocumental | undefined {
  return estado.tipos.find((t) => t.nombre === tipo)
}

export function nuevaAlerta(
  estado: EstadoMock, codigo: string, mensaje: string, severidad: Severidad, campo: string | null = null, confianza = 1,
): Alerta {
  return {
    id: `alr-m${String(siguiente(estado)).padStart(5, '0')}`, codigo, mensaje, severidad, confianza, campo,
    resuelta_por_revisor: false, aplica: null, comentario_revisor: null, resuelta_por: null, resuelta_en: null,
  }
}

export function bloqueantesSinResolver(folio: ResultadoExpediente): Alerta[] {
  return alertasQueBloquean(folio)
}

function recomendarDocumento(estado: EstadoMock, doc: ResultadoDocumento): void {
  if (doc.estado_analisis !== 'completado') {
    doc.recomendacion = null
    return
  }
  const minimo = ficha(estado, tipoExtraccion(doc))?.confianza_minima_campo ?? 0
  const bajas = Object.values(doc.nivel_confianza_por_campo).some((c) => c < minimo)
  doc.recomendacion = bajas || doc.alertas_encontradas.some(pesa) ? 'revision_manual' : 'aprobar'
}

/**
 * Alertas que dependen de los tipos del proceso, con campo = nombre del tipo y el tipo efectivo de cada
 * documento. Segun PERSONA_1 solo se recalculan al crear el folio y cuando un documento se procesa o se
 * confirma. En las dos, cuando la condicion desaparece se borran las sin revisar y las confirmadas; solo
 * se conserva el falso positivo (aplica=false).
 * - EXP-001 (bloqueante, en alertas_expediente): una por tipo requerido que falta.
 * - EXP-002 (informativa, en alertas_encontradas del DOCUMENTO; definida por PERSONA_1 en el PR #9):
 *   una por documento completado cuyo tipo efectivo no esta ni en tipos_requeridos ni en
 *   tipos_opcionales. No bloquea ni cambia la recomendacion. Un documento no completado no se toca.
 */
export function recalcularTiposDelProceso(estado: EstadoMock, folio: ResultadoExpediente): void {
  const proceso = estado.procesos.find((p) => p.nombre === folio.proceso)
  if (!proceso) return

  const faltan = new Set(tiposRequeridosQueFaltan(folio, proceso))
  const esExp001 = (a: Alerta) => a.codigo === 'EXP-001'
  folio.alertas_expediente = folio.alertas_expediente.filter((a) => !esExp001(a) || a.aplica === false || faltan.has(a.campo ?? ''))
  const conExp001 = new Set(folio.alertas_expediente.filter(esExp001).map((a) => a.campo))
  faltan.forEach((tipo) => {
    if (!conExp001.has(tipo)) {
      folio.alertas_expediente.push(nuevaAlerta(estado, 'EXP-001', `Falta ${tipo}, requerido por el proceso ${folio.proceso}`, 'bloqueante', tipo))
    }
  })

  for (const doc of folio.documentos) {
    if (doc.estado_analisis !== 'completado') continue
    const noPrevisto = tipoNoPrevisto(doc, proceso)
    doc.alertas_encontradas = doc.alertas_encontradas.filter((a) =>
      a.codigo !== 'EXP-002' || a.campo === noPrevisto || a.aplica === false)
    if (noPrevisto && !doc.alertas_encontradas.some((a) => a.codigo === 'EXP-002' && a.campo === noPrevisto)) {
      const nombre = ficha(estado, noPrevisto)?.nombre_visible ?? noPrevisto
      doc.alertas_encontradas.push(nuevaAlerta(estado, 'EXP-002', `Tipo de documento no previsto en el proceso: ${nombre}`, 'informativa', noPrevisto))
    }
  }
  recalcularExpediente(estado, folio)
}

/** Tras cada cambio: recomendaciones, comparaciones y CMP-001, conservando lo ya resuelto */
export function recalcularExpediente(estado: EstadoMock, folio: ResultadoExpediente): void {
  folio.documentos.forEach((d) => recomendarDocumento(estado, d))

  // Comparaciones entre documentos completados segun las fichas (una por campo)
  const completos = folio.documentos.filter((d) => d.estado_analisis === 'completado')
  const porCampo = new Map<string, Record<string, unknown>>()
  completos.forEach((a, i) => completos.slice(i + 1).forEach((b) => {
    const [ta, tb] = [tipoEfectivo(a), tipoEfectivo(b)]
    const campos = new Set([...(ficha(estado, ta)?.comparaciones[tb ?? ''] ?? []), ...(ficha(estado, tb)?.comparaciones[ta ?? ''] ?? [])])
    campos.forEach((campo) => {
      if (!(campo in a.datos_extraidos) || !(campo in b.datos_extraidos)) return
      const valores = porCampo.get(campo) ?? {}
      valores[a.identificador_unico_documento] = a.datos_extraidos[campo]
      valores[b.identificador_unico_documento] = b.datos_extraidos[campo]
      porCampo.set(campo, valores)
    })
  }))
  folio.comparaciones = [...porCampo.entries()].sort(([x], [y]) => x.localeCompare(y)).map(([campo, valores]) => ({
    campo, valores, coincide: new Set(Object.values(valores).map(normalizar)).size === 1,
  }))

  // CMP-001: una por campo que no coincide (las ya existentes conservan su resolucion)
  const sinCoincidir = new Set(folio.comparaciones.filter((c) => !c.coincide).map((c) => c.campo))
  folio.alertas_expediente = folio.alertas_expediente.filter((a) => a.codigo !== 'CMP-001' || sinCoincidir.has(a.campo ?? ''))
  const conAlerta = new Set(folio.alertas_expediente.filter((a) => a.codigo === 'CMP-001').map((a) => a.campo))
  sinCoincidir.forEach((campo) => {
    if (!conAlerta.has(campo)) {
      folio.alertas_expediente.push(nuevaAlerta(estado, 'CMP-001', `${campo} no coincide entre los documentos del folio`, 'critica', campo))
    }
  })

  const todas = [...folio.alertas_expediente, ...folio.documentos.flatMap((d) => d.alertas_encontradas)]
  folio.recomendacion_global = folio.documentos.length === 0 ? null
    : todas.some(pesa) || folio.documentos.some((d) => d.recomendacion !== 'aprobar') ? 'revision_manual' : 'aprobar'
}

export function resumenFolio(folio: ResultadoExpediente): ResumenFolio {
  return {
    folio: folio.folio, proceso: folio.proceso, estado_general: folio.estado_general,
    recomendacion_global: folio.recomendacion_global, n_documentos: folio.documentos.length,
    n_bloqueantes_sin_resolver: bloqueantesSinResolver(folio).length, fecha_solicitud: folio.fecha_solicitud,
    referencia_externa: folio.referencia_externa,
  }
}

/** Plantilla de valores por tipo: primer documento completado y sin alertas de los datos */
function plantilla(estado: EstadoMock, tipo: string): ResultadoDocumento | undefined {
  return [...estado.folios.values()].flatMap((f) => f.documentos).find((d) =>
    d.estado_analisis === 'completado' && d.tipo_documental_detectado === tipo && d.alertas_encontradas.length === 0 &&
    d.correcciones.length === 0)
}

function completar(estado: EstadoMock, folio: ResultadoExpediente, doc: ResultadoDocumento, proc: Procesamiento): void {
  const fichaExtraccion = ficha(estado, proc.tipoExtraccion)
  if (!fichaExtraccion) return
  const fuente = proc.origen ?? plantilla(estado, proc.tipoContenido)
  const mismaFicha = proc.tipoExtraccion === proc.tipoContenido
  // Se conservan las de plataforma (DUP-001, EXP-002: no son del motor) y las ya revisadas
  const alertas = doc.alertas_encontradas.filter((a) => a.codigo === 'DUP-001' || a.codigo === 'EXP-002' || a.resuelta_por_revisor)
  doc.datos_extraidos = {}
  doc.nivel_confianza_por_campo = {}
  doc.evidencia_por_campo = {}
  for (const [campo, def] of Object.entries(fichaExtraccion.campos)) {
    const valor = valorOnull(fuente?.datos_extraidos[campo])
    // Con la ficha de otro tipo solo coinciden los campos comunes, y con poca confianza. Sin valor: 0 (ADR-007)
    doc.datos_extraidos[campo] = valor
    doc.nivel_confianza_por_campo[campo] = valor === null ? 0 : mismaFicha ? fuente?.nivel_confianza_por_campo[campo] ?? 0.9 : 0.45
    if (valor !== null) doc.evidencia_por_campo[campo] = 'pagina_1' // un campo sin valor no tiene evidencia
    if (valor === null && def.obligatorio) {
      alertas.push(nuevaAlerta(estado, 'VAL-001', `Falta el campo obligatorio ${campo}`, 'critica', campo))
    } else if (valor === null) {
      alertas.push(nuevaAlerta(estado, 'VAL-004', `Falta el campo opcional ${campo}`, 'informativa', campo))
    } else if (valor !== null && doc.nivel_confianza_por_campo[campo] < fichaExtraccion.confianza_minima_campo) {
      alertas.push(nuevaAlerta(estado, 'VAL-002', `Confianza de ${campo} por debajo del minimo de la ficha`, 'preventiva',
        campo, doc.nivel_confianza_por_campo[campo]))
    }
  }
  if (mismaFicha && fuente) {
    doc.reglas_cumplidas_e_incumplidas = structuredClone(fuente.reglas_cumplidas_e_incumplidas)
    fuente.alertas_encontradas.filter((a) => a.codigo.startsWith('REG-')).forEach((a) =>
      alertas.push(nuevaAlerta(estado, a.codigo, a.mensaje, a.severidad, a.campo, a.confianza)))
  } else {
    doc.reglas_cumplidas_e_incumplidas = { cumplidas: [], incumplidas: [] }
  }
  if (!doc.tipo_documental_confirmado && doc.tipo_documental_declarado && doc.tipo_documental_declarado !== proc.tipoContenido) {
    alertas.push(nuevaAlerta(estado, 'CLS-001',
      `Tipo declarado ${doc.tipo_documental_declarado} distinto del detectado ${proc.tipoContenido}`, 'critica', null, proc.confianzaClasificacion))
  }
  const minimaClasificacion = ficha(estado, proc.tipoContenido)?.confianza_minima_clasificacion ?? 0
  if (proc.confianzaClasificacion < minimaClasificacion) {
    alertas.push(nuevaAlerta(estado, 'CLS-002', 'Confianza de clasificacion por debajo del minimo de la ficha', 'preventiva',
      null, proc.confianzaClasificacion))
  }
  doc.alertas_encontradas = alertas
  doc.tipo_documental_detectado = proc.tipoContenido
  doc.confianza_clasificacion = proc.confianzaClasificacion
  const modelo = modeloDeAnalisis(doc, proc)
  doc.fecha_y_modelo_utilizado = { fecha_analisis: fechaIso(estado), proveedor: PROVEEDOR, modelo, version_prompt: VERSION_PROMPT }
  doc.estado_analisis = 'completado'
  auditar(estado, null, 'documento_procesado', folio.folio, doc.identificador_unico_documento,
    { estado_analisis: 'completado' }, modelo, VERSION_PROMPT)
}

/** Avanza con el reloj el analisis de los documentos subidos en esta sesion */
export function avanzarProcesamiento(estado: EstadoMock, folio: ResultadoExpediente): void {
  let cambios = false
  for (const doc of folio.documentos) {
    const proc = estado.procesamientos.get(doc.identificador_unico_documento)
    if (!proc || !enProceso(doc)) continue
    const transcurrido = estado.ahora() - proc.inicio
    if (transcurrido >= MS_HASTA_COMPLETADO) {
      completar(estado, folio, doc, proc)
      estado.procesamientos.delete(doc.identificador_unico_documento)
      cambios = true
    } else if (transcurrido >= MS_HASTA_PROCESANDO && doc.estado_analisis === 'pendiente') {
      doc.estado_analisis = 'procesando'
    }
  }
  if (cambios) recalcularTiposDelProceso(estado, folio) // un documento se ha procesado
}

export function resumenMarkdown(folio: ResultadoExpediente): string {
  const alertas = [...folio.alertas_expediente, ...folio.documentos.flatMap((d) => d.alertas_encontradas)]
  return [
    `# Expediente ${folio.folio} (datos ficticios, mock)`, '',
    `- Proceso: ${folio.proceso}`,
    `- Referencia: ${folio.referencia_externa ?? '-'}`,
    `- Fecha de solicitud: ${folio.fecha_solicitud ?? '-'}`,
    `- Estado: ${folio.estado_general}; recomendacion: ${folio.recomendacion_global ?? '-'}`,
    `- Decision: ${folio.decision_humana ?? '-'} (${folio.usuario_decision ?? '-'}, ${folio.fecha_decision ?? '-'})`, '',
    '## Documentos', '',
    ...folio.documentos.map((d) => `- ${d.tipo_documental_detectado ?? d.tipo_documental_declarado}: ${d.estado_analisis}`), '',
    '## Alertas', '',
    ...(alertas.length ? alertas.map((a) => `- ${a.codigo} (${a.severidad}): ${a.mensaje}`) : ['- Ninguna']), '',
  ].join('\n')
}
