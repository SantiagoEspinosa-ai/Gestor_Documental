// Logica de negocio simulada de los mocks: la minima para que el estado en memoria sea coherente
// con el contrato (reglas de ADR-006). No sustituye a validacion ni a expediente del backend.
import type { Alerta, ResultadoDocumento, ResultadoExpediente, ResumenFolio, Severidad, TipoDocumental } from '../tipos/contrato'
import { auditar, fechaIso, siguiente, type EstadoMock, type Procesamiento } from './estado'

/** pendiente -> procesando a los 3 s, -> completado a los 9 s */
export const MS_HASTA_PROCESANDO = 3_000
export const MS_HASTA_COMPLETADO = 9_000
const MODELO = { proveedor: 'ollama', modelo: 'llama3.2-vision:11b', version_prompt: 'extraccion@v1' }

export function normalizar(valor: unknown): string {
  return String(valor).normalize('NFKD').replace(/[̀-ͯ]/g, '').toUpperCase().split(/\s+/).filter(Boolean).join(' ')
}

/** Regla 2.2: bloquea la aprobacion mientras no se marque como falso positivo */
export const bloquea = (a: Alerta) => a.severidad === 'bloqueante' && a.aplica !== false
const pesa = (a: Alerta) => (a.severidad === 'critica' || a.severidad === 'bloqueante') && a.aplica !== false

/** Tipo con el que se extrae (regla 2.5) */
export const tipoExtraccion = (d: ResultadoDocumento) =>
  d.tipo_documental_confirmado ?? d.tipo_documental_declarado ?? d.tipo_documental_detectado
/** Tipo que representa el documento en el expediente */
const tipoDocumento = (d: ResultadoDocumento) =>
  d.tipo_documental_confirmado ?? d.tipo_documental_detectado ?? d.tipo_documental_declarado

export const enProceso = (d: ResultadoDocumento) => d.estado_analisis === 'pendiente' || d.estado_analisis === 'procesando'

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
  return [...folio.alertas_expediente, ...folio.documentos.flatMap((d) => d.alertas_encontradas)].filter(bloquea)
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

/** Recalcula comparaciones, CMP-001, EXP-001 y recomendaciones conservando lo ya resuelto */
export function recalcularExpediente(estado: EstadoMock, folio: ResultadoExpediente): void {
  folio.documentos.forEach((d) => recomendarDocumento(estado, d))

  // Comparaciones entre documentos completados segun las fichas (una por campo)
  const completos = folio.documentos.filter((d) => d.estado_analisis === 'completado')
  const porCampo = new Map<string, Record<string, unknown>>()
  completos.forEach((a, i) => completos.slice(i + 1).forEach((b) => {
    const [ta, tb] = [tipoDocumento(a), tipoDocumento(b)]
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

  // CMP-001 (una por campo que no coincide) y EXP-001 (tipos requeridos que faltan)
  const esperadas = new Map<string, { mensaje: string; campo: string | null; severidad: Severidad }>()
  folio.comparaciones.filter((c) => !c.coincide).forEach((c) =>
    esperadas.set(`CMP-001|${c.campo}`, { mensaje: `${c.campo} no coincide entre los documentos del folio`, campo: c.campo, severidad: 'critica' }))
  const presentes = new Set(folio.documentos.filter((d) => d.estado_analisis !== 'error').map(tipoDocumento))
  const proceso = estado.procesos.find((p) => p.nombre === folio.proceso)
  proceso?.tipos_requeridos.filter((t) => !presentes.has(t)).forEach((t) =>
    esperadas.set(`EXP-001|${t}`, { mensaje: `Falta ${t}, requerido por el proceso ${folio.proceso}`, campo: null, severidad: 'bloqueante' }))
  // EXP-001 no tiene campo: el tipo que falta va en el mensaje ("Falta <tipo>, requerido...")
  const clave = (a: Alerta) => a.codigo === 'EXP-001' ? `EXP-001|${/Falta (\w+)/.exec(a.mensaje)?.[1]}` : `${a.codigo}|${a.campo}`
  const recalculables = (a: Alerta) => a.codigo === 'CMP-001' || a.codigo === 'EXP-001'
  folio.alertas_expediente = folio.alertas_expediente.filter((a) => !recalculables(a) || esperadas.has(clave(a)))
  const existentes = new Set(folio.alertas_expediente.filter(recalculables).map(clave))
  esperadas.forEach((e, k) => {
    if (!existentes.has(k)) folio.alertas_expediente.push(nuevaAlerta(estado, k.split('|')[0], e.mensaje, e.severidad, e.campo))
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
  const alertas = doc.alertas_encontradas.filter((a) => a.codigo === 'DUP-001' || a.resuelta_por_revisor)
  doc.datos_extraidos = {}
  doc.nivel_confianza_por_campo = {}
  doc.evidencia_por_campo = {}
  for (const [campo, def] of Object.entries(fichaExtraccion.campos)) {
    const valor = fuente?.datos_extraidos[campo] ?? null
    // Con la ficha de otro tipo solo coinciden los campos comunes, y con poca confianza
    doc.datos_extraidos[campo] = valor
    doc.nivel_confianza_por_campo[campo] = valor === null ? 0.2 : mismaFicha ? fuente?.nivel_confianza_por_campo[campo] ?? 0.9 : 0.45
    doc.evidencia_por_campo[campo] = 'pagina_1'
    if (valor === null && def.obligatorio) {
      alertas.push(nuevaAlerta(estado, 'VAL-001', `Falta el campo obligatorio ${campo}`, 'critica', campo))
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
  doc.fecha_y_modelo_utilizado = { fecha_analisis: fechaIso(estado), ...MODELO }
  doc.estado_analisis = 'completado'
  auditar(estado, null, 'documento_procesado', folio.folio, doc.identificador_unico_documento,
    { estado_analisis: 'completado' }, MODELO.modelo, MODELO.version_prompt)
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
  if (cambios) recalcularExpediente(estado, folio)
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
