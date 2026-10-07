// Logica de negocio simulada de los mocks: la minima para que el estado en memoria sea coherente
// con el contrato (reglas de ADR-006). No sustituye a validacion ni a expediente del backend.
import {
  TIPO_DESCONOCIDO, type Alerta, type ComparacionCampo, type Recomendacion, type RespuestaAntecedentes, type ResultadoDocumento,
  type ResultadoExpediente, type ResumenFolio, type Severidad, type TipoDocumental,
} from '../tipos/contrato'
import {
  alertasQueBloquean, bloquea, enProceso, fichaDeTipo, tipoEfectivo, tipoExtraccion, tipoNoPrevisto, tiposRequeridosQueFaltan,
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
/** Como el motor real: un prompt de extraccion por tipo (extraccion_<tipo>@v3) */
const versionPrompt = (tipo: string) => `extraccion_${tipo}@v3`
/** Evidencia como la valida el motor: pagina y seccion */
const EVIDENCIA = 'pagina_1:seccion_central'

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

/** Ficha de un tipo; nunca la de `desconocido` (ADR-009) */
export function ficha(estado: EstadoMock, tipo: string | null): TipoDocumental | undefined {
  return fichaDeTipo(estado.tipos, tipo)
}

export function nuevaAlerta(
  estado: EstadoMock, codigo: string, mensaje: string, severidad: Severidad, campo: string | null = null, confianza = 1,
): Alerta {
  return {
    id: `alr-m${String(siguiente(estado)).padStart(5, '0')}`, codigo, mensaje, severidad, confianza, campo,
    resuelta_por_revisor: false, aplica: null, comentario_revisor: null, resuelta_por: null, resuelta_en: null,
  }
}

/**
 * Bloqueantes que impiden aprobar (regla 2.2), sobre las alertas VISIBLES: las del expediente y las de
 * cada documento, que solo son las de la version vigente del analisis (las del motor de una version
 * anterior desaparecen al completar el reproceso, como en la API del PR #9). Las usan la lista de
 * folios y la decision.
 */
export function bloqueantesSinResolver(folio: ResultadoExpediente): Alerta[] {
  return alertasQueBloquean(folio)
}

/**
 * Recomendacion del documento: la da el analisis simulado al completar y, como la API (D3, sugerido por
 * PERSONA_2), se recalcula al corregir datos (los campos corregidos ya valen 1.0). No al resolver alertas.
 * Los mocks no reevaluan las reglas al corregir: las alertas del documento no cambian.
 */
export function recomendarDocumento(estado: EstadoMock, doc: ResultadoDocumento): void {
  const minimo = ficha(estado, tipoExtraccion(doc))?.confianza_minima_campo ?? 0
  const bajas = Object.values(doc.nivel_confianza_por_campo).some((c) => c < minimo)
  doc.recomendacion = bajas || doc.alertas_encontradas.some(pesa) ? 'revision_manual' : 'aprobar'
}

/**
 * Recomendacion global como la API (expediente/recomendacion.py, PR #9). La primera regla que se
 * cumple pide revision_manual; si ninguna, aprobar (nunca rechazar):
 * a) sin documentos, o alguno no completado (pendiente, procesando o error);
 * b) alguna critica o bloqueante, de documento o de expediente, que no sea falso positivo;
 * c) algun documento sin ficha para su tipo efectivo, sin confianza de clasificacion, o con ella o con
 *    algun campo por debajo de los minimos de la ficha (un campo sin valor tiene confianza 0).
 * No usa la recomendacion por documento.
 */
export function recomendacionGlobal(estado: EstadoMock, folio: ResultadoExpediente): Recomendacion {
  const documentos = folio.documentos
  if (!documentos.length || documentos.some((d) => d.estado_analisis !== 'completado')) return 'revision_manual'
  if ([...folio.alertas_expediente, ...documentos.flatMap((d) => d.alertas_encontradas)].some(pesa)) return 'revision_manual'
  for (const d of documentos) {
    const f = ficha(estado, tipoEfectivo(d))
    if (!f || d.confianza_clasificacion === null || d.confianza_clasificacion < f.confianza_minima_clasificacion) return 'revision_manual'
    if (Object.values(d.nivel_confianza_por_campo).some((c) => c < f.confianza_minima_campo)) return 'revision_manual'
  }
  return 'aprobar'
}

const FORMATOS_FECHA: [RegExp, (m: RegExpExecArray) => [string, string, string]][] = [
  [/^(\d{4})-(\d{1,2})-(\d{1,2})$/, (m) => [m[1], m[2], m[3]]],
  [/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/, (m) => [m[3], m[2], m[1]]],
  [/^(\d{1,2})-(\d{1,2})-(\d{4})$/, (m) => [m[3], m[2], m[1]]],
  [/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/, (m) => [m[1], m[2], m[3]]],
  [/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/, (m) => [m[3], m[2], m[1]]],
]

/** Fecha en ISO si se lee en alguno de los formatos de la API; si no, el texto normalizado */
export function normalizarFecha(valor: unknown): string {
  const texto = String(valor).trim()
  for (const [patron, partes] of FORMATOS_FECHA) {
    const m = patron.exec(texto)
    if (!m) continue
    const [a, mes, dia] = partes(m).map(Number)
    const fecha = new Date(Date.UTC(a, mes - 1, dia))
    if (fecha.getUTCFullYear() === a && fecha.getUTCMonth() === mes - 1 && fecha.getUTCDate() === dia) {
      return fecha.toISOString().slice(0, 10)
    }
  }
  return normalizar(valor)
}

/**
 * Comparaciones como validacion.comparar de la API (PR #9): por cada campo de `comparaciones` de las
 * fichas (uniendo los dos sentidos), participan los documentos completados con valor de los tipos de
 * un par cuyos dos lados tienen valor; con menos de 2, no hay comparacion. Los valores vacios no
 * participan. Se normalizan mayusculas, acentos y espacios, y las fechas en varios formatos.
 */
export function compararCampos(estado: EstadoMock, documentos: ResultadoDocumento[]): ComparacionCampo[] {
  const relaciones = new Map<string, Set<string>>() // campo -> pares "a|b" ordenados
  for (const f of estado.tipos) {
    for (const [otro, campos] of Object.entries(f.comparaciones ?? {})) {
      for (const campo of campos ?? []) {
        relaciones.set(campo, (relaciones.get(campo) ?? new Set()).add([f.nombre, otro].sort().join('|')))
      }
    }
  }
  const completos = documentos.filter((d) => d.estado_analisis === 'completado')
  const resultado: ComparacionCampo[] = []
  for (const campo of [...relaciones.keys()].sort()) {
    const conValor = completos.filter((d) => tipoEfectivo(d) && !sinValor(d.datos_extraidos[campo]))
    const tiposConValor = new Set(conValor.map(tipoEfectivo))
    const tipos = new Set([...relaciones.get(campo)!].map((p) => p.split('|')).filter((par) => par.every((t) => tiposConValor.has(t))).flat())
    const participantes = conValor.filter((d) => tipos.has(tipoEfectivo(d)!))
    if (participantes.length < 2) continue
    const normalizados = new Set(participantes.map((d) => {
      const valor = d.datos_extraidos[campo]
      return ficha(estado, tipoEfectivo(d))?.campos[campo]?.tipo === 'fecha' ? normalizarFecha(valor) : normalizar(valor)
    }))
    resultado.push({
      campo, coincide: normalizados.size === 1,
      valores: Object.fromEntries(participantes.map((d) => [d.identificador_unico_documento, d.datos_extraidos[campo]])),
    })
  }
  return resultado
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

  // EXP-001 como la API: solo cuentan los documentos completados (uno pendiente, procesando o en error
  // no cubre su tipo). El aviso de la pantalla de carga si cuenta todos los subidos.
  const completados = { documentos: folio.documentos.filter((d) => d.estado_analisis === 'completado') }
  const faltan = new Set(tiposRequeridosQueFaltan(completados, proceso))
  const esExp001 = (a: Alerta) => a.codigo === 'EXP-001'
  const conExp001 = new Set(folio.alertas_expediente.filter(esExp001).map((a) => a.campo))
  folio.alertas_expediente = folio.alertas_expediente.filter((a) => !esExp001(a) || a.aplica === false || faltan.has(a.campo ?? ''))
  faltan.forEach((tipo) => {
    if (!conExp001.has(tipo)) {
      const nombre = ficha(estado, tipo)?.nombre_visible ?? tipo
      folio.alertas_expediente.push(nuevaAlerta(estado, 'EXP-001', `Falta el documento requerido: ${nombre}`, 'bloqueante', tipo))
    }
  })

  for (const doc of folio.documentos) {
    if (doc.estado_analisis !== 'completado') continue
    const noPrevisto = tipoNoPrevisto(doc, proceso)
    doc.alertas_encontradas = doc.alertas_encontradas.filter((a) =>
      a.codigo !== 'EXP-002' || a.campo === noPrevisto || a.aplica === false)
    if (noPrevisto && !doc.alertas_encontradas.some((a) => a.codigo === 'EXP-002' && a.campo === noPrevisto)) {
      // Como expediente.servicio: `desconocido` (ADR-009) es un tipo no reconocido, no uno "no previsto"
      const mensaje = noPrevisto === TIPO_DESCONOCIDO
        ? 'Tipo de documento no reconocido'
        : `Tipo de documento no previsto en el proceso: ${ficha(estado, noPrevisto)?.nombre_visible ?? noPrevisto}`
      doc.alertas_encontradas.push(nuevaAlerta(estado, 'EXP-002', mensaje, 'informativa', noPrevisto))
    }
  }
  recalcularExpediente(estado, folio)
}

/**
 * Tras cada cambio: comparaciones, CMP-001 y recomendacion global. La recomendacion de cada documento
 * no se toca (es del analisis).
 * CMP-001 como la API (PR #9): una por campo que no coincide, con el mensaje "Los documentos no
 * coinciden en {campo}" (nunca los valores). En los campos que ya coinciden o ya no se comparan se
 * borran la sin revisar y la confirmada; solo se conserva el falso positivo (aplica=false).
 */
export function recalcularExpediente(estado: EstadoMock, folio: ResultadoExpediente): void {
  folio.comparaciones = compararCampos(estado, folio.documentos)

  const sinCoincidir = new Set(folio.comparaciones.filter((c) => !c.coincide).map((c) => c.campo))
  const conAlerta = new Set(folio.alertas_expediente.filter((a) => a.codigo === 'CMP-001').map((a) => a.campo))
  folio.alertas_expediente = folio.alertas_expediente.filter((a) =>
    a.codigo !== 'CMP-001' || sinCoincidir.has(a.campo ?? '') || a.aplica === false)
  ;[...sinCoincidir].sort().forEach((campo) => {
    if (!conAlerta.has(campo)) {
      folio.alertas_expediente.push(nuevaAlerta(estado, 'CMP-001', `Los documentos no coinciden en ${campo}`, 'critica', campo))
    }
  })

  folio.recomendacion_global = recomendacionGlobal(estado, folio)
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
  // Version nueva del analisis: solo sobreviven las alertas de plataforma (DUP-001, EXP-002). Las del motor
  // de la version anterior dejan de verse aunque estuvieran revisadas, y las correcciones eran de esa
  // version (como construir_resultado de la API)
  const alertas = doc.alertas_encontradas.filter((a) => a.codigo === 'DUP-001' || a.codigo === 'EXP-002')
  doc.correcciones = []
  doc.datos_extraidos = {}
  doc.nivel_confianza_por_campo = {}
  doc.evidencia_por_campo = {}
  for (const [campo, def] of Object.entries(fichaExtraccion.campos)) {
    const valor = valorOnull(fuente?.datos_extraidos[campo])
    // Con la ficha de otro tipo solo coinciden los campos comunes, y con poca confianza. Sin valor: 0 (ADR-007)
    doc.datos_extraidos[campo] = valor
    doc.nivel_confianza_por_campo[campo] = valor === null ? 0 : mismaFicha ? fuente?.nivel_confianza_por_campo[campo] ?? 0.9 : 0.45
    if (valor !== null) doc.evidencia_por_campo[campo] = EVIDENCIA // un campo sin valor no tiene evidencia
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
  doc.fecha_y_modelo_utilizado = {
    fecha_analisis: fechaIso(estado), proveedor: PROVEEDOR, modelo, version_prompt: versionPrompt(proc.tipoExtraccion),
  }
  doc.estado_analisis = 'completado'
  recomendarDocumento(estado, doc)
  // detalle = datos de auditoria del motor sin modelo ni version_prompt (van en sus columnas), como la API
  auditar(estado, null, 'documento_procesado', folio.folio, doc.identificador_unico_documento,
    { proveedor: PROVEEDOR, respaldo_usado: false }, modelo, versionPrompt(proc.tipoExtraccion))
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

// ---------------------------------------------------------------- enmascaramiento (ADR-010 A2-A5)
// La misma mascara que la API (backend/app/core/enmascaramiento.py), solo en el borde de salida: el estado
// en memoria guarda el valor real (como la BD) y cada respuesta sale enmascarada para todos los roles.

const MASCARA = '****'
/** Linea MRZ (30 o mas de [A-Z0-9<]); la que empieza por "P<" (linea 1 del pasaporte) se deja */
const MRZ = /(?<![A-Z0-9<])[A-Z0-9<]{30,}(?![A-Z0-9<])/g
/** Evidencia que es una ubicacion (como _EVIDENCIA del motor) o "correccion_revisor" */
const UBICACION = /^(?:pagina_[1-9]\d*(?::.+)?|correccion_revisor)$/

/** `****` + 4 ultimos caracteres; 4 o menos, `****`; null sigue siendo null */
export function mascara(valor: unknown): string | null {
  if (valor === null || valor === undefined) return null
  const texto = String(valor)
  return texto.length > 4 ? `${MASCARA}${texto.slice(-4)}` : MASCARA
}

/** Campos sensibles del documento: los de su ficha de extraccion y los del declarado y el detectado (como la API) */
export function camposSensibles(estado: EstadoMock, doc: ResultadoDocumento): Set<string> {
  const tipos = [doc.tipo_documental_confirmado, doc.tipo_documental_declarado, doc.tipo_documental_detectado]
  return new Set(tipos.flatMap((t) => Object.entries(ficha(estado, t)?.campos ?? {}).filter(([, c]) => c.sensible).map(([n]) => n)))
}

function taparEvidencia(campo: string, texto: string, literales: string[], sensibles: Set<string>): string {
  if (sensibles.has(campo) && !UBICACION.test(texto)) return MASCARA
  let tapado = texto.replace(MRZ, (linea) => (linea.startsWith('P<') ? linea : MASCARA))
  for (const literal of literales) tapado = tapado.split(literal).join(mascara(literal)!)
  return tapado
}

/** Copia del documento enmascarada: datos, evidencias y correcciones de los campos sensibles */
export function enmascararDocumento(estado: EstadoMock, doc: ResultadoDocumento): ResultadoDocumento {
  const sensibles = camposSensibles(estado, doc)
  const valores = [...sensibles].map((c) => doc.datos_extraidos[c])
    .concat(doc.correcciones.filter((c) => sensibles.has(c.campo)).flatMap((c) => [c.valor_anterior, c.valor_nuevo]))
  const literales = [...new Set(valores.filter((v) => v !== null && v !== undefined && String(v)).map(String))]
    .sort((a, b) => b.length - a.length)
  const copia = structuredClone(doc)
  for (const campo of sensibles) if (campo in copia.datos_extraidos) copia.datos_extraidos[campo] = mascara(copia.datos_extraidos[campo])
  copia.evidencia_por_campo = Object.fromEntries(Object.entries(copia.evidencia_por_campo)
    .map(([campo, texto]) => [campo, taparEvidencia(campo, texto, literales, sensibles)]))
  copia.correcciones = copia.correcciones.map((c) => (sensibles.has(c.campo)
    ? { ...c, valor_anterior: mascara(c.valor_anterior), valor_nuevo: mascara(c.valor_nuevo) } : c))
  return copia
}

/** Copia del expediente enmascarada: cada documento y las comparaciones de un campo sensible en alguno de ellos */
export function enmascararExpediente(estado: EstadoMock, folio: ResultadoExpediente): ResultadoExpediente {
  const sensibles = new Map(folio.documentos.map((d) => [d.identificador_unico_documento, camposSensibles(estado, d)]))
  const copia = structuredClone(folio)
  copia.documentos = folio.documentos.map((d) => enmascararDocumento(estado, d))
  copia.comparaciones = copia.comparaciones.map((c) => (Object.keys(c.valores).some((id) => sensibles.get(id)?.has(c.campo))
    ? { ...c, valores: Object.fromEntries(Object.entries(c.valores).map(([id, v]) => [id, mascara(v)])) } : c))
  return copia
}

// ---------------------------------------------------------------- antecedentes (ADR-010 C, H16)

const MAX_ANTECEDENTES = 10
const LIMITE_FRAGMENTO = 800
const MS_DIA = 24 * 60 * 60 * 1000

/**
 * Como GET /folios/{folio}/antecedentes de la API: motivo si el proceso no los permite o el folio no tiene
 * referencia; si no, los folios del mismo proceso y la misma referencia, cerrados, con la decision dentro de
 * caducidad_antecedentes_dias y sin el actual, del mas reciente al mas antiguo (como mucho 10). El fragmento
 * es el principio del resumen del mock de ese folio si tiene resumen (la API lo saca de la memoria de folios)
 */
export function antecedentes(estado: EstadoMock, folio: ResultadoExpediente): RespuestaAntecedentes {
  const proceso = estado.procesos.find((p) => p.nombre === folio.proceso)
  if (!proceso?.permitir_antecedentes) return { permitido: false, motivo: 'proceso_sin_antecedentes', elementos: [] }
  if (!folio.referencia_externa) return { permitido: false, motivo: 'folio_sin_referencia', elementos: [] }
  const desde = estado.ahora() - proceso.caducidad_antecedentes_dias * MS_DIA
  const elementos = [...estado.folios.values()]
    .filter((f) => f.folio !== folio.folio && f.proceso === folio.proceso && f.referencia_externa === folio.referencia_externa
      && f.decision_humana !== null && f.fecha_decision !== null && Date.parse(f.fecha_decision) >= desde)
    .sort((a, b) => b.fecha_decision!.localeCompare(a.fecha_decision!) || b.folio.localeCompare(a.folio))
    .slice(0, MAX_ANTECEDENTES)
    .map((f) => ({
      folio: f.folio, fecha_solicitud: f.fecha_solicitud, estado_general: f.estado_general, decision_humana: f.decision_humana,
      fecha_decision: f.fecha_decision, fragmento_resumen: f.ruta_resumen_md ? resumenMarkdown(f).slice(0, LIMITE_FRAGMENTO) : null,
    }))
  return { permitido: true, motivo: null, elementos }
}
