// Texto legible del `detalle` de cada entrada de auditoria (endpoints.md, EntradaAuditoria).
// Nunca se muestra el JSON en bruto. El contrato dice que `detalle` no lleva valores sensibles sin
// enmascarar; aun asi, cualquier clave que no sea de la forma conocida de su accion se enmascara aqui
// (si la API anade, por ejemplo, el valor corregido o un comentario, no sale completo en pantalla).
import { ACCIONES_AUDITORIA, type AccionAuditoria, type EntradaAuditoria } from '../tipos/contrato'
import { ETIQUETA_ACCION, ETIQUETA_DECISION } from './etiquetas'

/** nombre del tipo -> nombre_visible (de GET /tipos-documentales; si falta, el nombre legible) */
export type NombresTipos = Record<string, string>

const esAccion = (accion: string): accion is AccionAuditoria => (ACCIONES_AUDITORIA as readonly string[]).includes(accion)

export function etiquetaAccion(accion: string): string {
  return esAccion(accion) ? ETIQUETA_ACCION[accion] : accion
}

/** `nombre_completo` -> `nombre completo` */
export const legible = (clave: string) => clave.replaceAll('_', ' ')

/** Solo los 4 ultimos caracteres; objetos y listas, ocultos. Para valores que no se sabe si son sensibles. */
export function enmascarar(valor: unknown): string {
  if (valor === null || valor === undefined) return '—'
  if (typeof valor === 'boolean') return valor ? 'sí' : 'no'
  if (typeof valor === 'object') return '(oculto)'
  const texto = String(valor)
  return texto.length > 4 ? `****${texto.slice(-4)}` : '****'
}

function tamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  return kb < 1024 ? `${kb.toLocaleString('es-ES', { maximumFractionDigits: 1 })} KB`
    : `${(kb / 1024).toLocaleString('es-ES', { maximumFractionDigits: 1 })} MB`
}

const texto = (v: unknown): v is string => typeof v === 'string' && v.length > 0
/** Nombre de campo o de tipo tecnico (snake_case): no es un valor de la persona */
const nombreTecnico = (v: unknown): v is string => typeof v === 'string' && /^[a-z][a-z0-9_]*$/.test(v)
const numero = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const formatoNumero = (n: number) => n.toLocaleString('es-ES', { maximumFractionDigits: 2 })

/** Numero, o {nombre: numero} (p. ej. tiempos o tokens por fase), como texto; null si no tiene esa forma */
function numeros(valor: unknown, unidad = ''): string | null {
  if (numero(valor)) return `${formatoNumero(valor)}${unidad}`
  if (valor && typeof valor === 'object' && !Array.isArray(valor)) {
    const partes = Object.entries(valor)
    if (partes.length && partes.every(([k, v]) => nombreTecnico(k) && numero(v))) {
      return partes.map(([k, v]) => `${legible(k)} ${formatoNumero(v as number)}${unidad}`).join(' · ')
    }
  }
  return null
}

/**
 * Frases del detalle con la forma de la API del PR #9 (tabla de api/README.md). Para cada accion se
 * formatean sus claves conocidas si tienen el tipo esperado; el resto (o una clave conocida con otro
 * tipo) sale como "clave: ****1234". Nada de esto es sensible: nombres de campo o de tipo, codigos,
 * huellas, tamanos, proveedor y tiempos (detalle nunca lleva valores de campos ni comentarios).
 */
export function describirDetalle(entrada: Pick<EntradaAuditoria, 'accion' | 'detalle'>, tipos: NombresTipos = {}): string[] {
  const d = entrada.detalle ?? {}
  const frases: string[] = []
  const usadas = new Set<string>()
  const usar = (clave: string, frase: string) => { usadas.add(clave); frases.push(frase) }
  const nombreTipo = (tipo: string) => tipos[tipo] ?? legible(tipo)

  switch (entrada.accion) {
    case 'login':
      if (d.resultado === 'ok') usar('resultado', 'Acceso correcto')
      else if (d.resultado === 'fallido') usar('resultado', 'Intento fallido')
      else if (d.resultado === 'bloqueado') usar('resultado', 'Acceso bloqueado') // ADR-011: no cuenta para el limite
      break
    case 'documento_subido':
      if (texto(d.hash_sha256)) usar('hash_sha256', `SHA-256 ${d.hash_sha256.slice(0, 12)}…`)
      if (typeof d.tamano_bytes === 'number') usar('tamano_bytes', tamano(d.tamano_bytes))
      if (typeof d.duplicado === 'boolean') usar('duplicado', d.duplicado ? 'Duplicado en el folio (DUP-001)' : 'No duplicado')
      break
    case 'documento_procesado': {
      // Datos de auditoria del motor; modelo y version_prompt van en sus columnas
      if (texto(d.proveedor)) usar('proveedor', `Proveedor: ${d.proveedor}`)
      if (typeof d.respaldo_usado === 'boolean') {
        usar('respaldo_usado', d.respaldo_usado ? 'Con el proveedor de respaldo' : 'Sin respaldo')
      }
      // ADR-007 punto 4: la confianza que da el modelo no se usa en la UI (solo queda en la auditoria)
      if ('confianzas_modelo' in d) usadas.add('confianzas_modelo')
      const tiempos = numeros(d.tiempos, ' s')
      if (tiempos) usar('tiempos', `Tiempo: ${tiempos}`)
      const tokens = numeros(d.tokens)
      if (tokens) usar('tokens', `Tokens: ${tokens}`)
      // Resto de datos_auditoria del motor real (H10, orquestador de PERSONA_2): ninguno es un dato del documento
      if (nombreTecnico(d.modalidad)) usar('modalidad', `Modalidad: ${legible(d.modalidad)}`)
      if (numero(d.paginas)) usar('paginas', `Páginas: ${formatoNumero(d.paginas)}`)
      if (texto(d.version_prompt_clasificacion) && /^[\w.@-]+$/.test(d.version_prompt_clasificacion)) {
        usar('version_prompt_clasificacion', `Prompt de clasificación: ${d.version_prompt_clasificacion}`)
      }
      // Detalle de cada llamada al modelo: solo cuantas hubo (el detalle queda en la auditoria)
      if (Array.isArray(d.llamadas)) usar('llamadas', `Llamadas al modelo: ${d.llamadas.length}`)
      break
    }
    case 'dato_corregido':
      if (Array.isArray(d.campos) && d.campos.length && d.campos.every(nombreTecnico)) {
        usar('campos', `${d.campos.length === 1 ? 'Campo' : 'Campos'}: ${d.campos.map(legible).join(', ')}`)
      }
      break
    case 'dato_revelado':
      if (nombreTecnico(d.campo)) usar('campo', `Campo: ${legible(d.campo)}`)
      // ADR-010 A4c: la API lo guarda ya tapado (enmascarar_texto), asi que se muestra entero
      if (texto(d.motivo)) usar('motivo', `Motivo: “${d.motivo}”`)
      break
    case 'clasificacion_confirmada':
      if (nombreTecnico(d.tipo)) usar('tipo', `Tipo confirmado: ${nombreTipo(d.tipo)}`)
      if (typeof d.reproceso === 'boolean') usar('reproceso', d.reproceso ? 'Se vuelve a analizar' : 'Sin volver a analizar')
      break
    case 'alerta_resuelta':
      if (texto(d.codigo)) {
        const revision = d.aplica === true ? 'aplica' : d.aplica === false ? 'falso positivo' : null
        usar('codigo', `Alerta ${d.codigo}${revision ? `: ${revision}` : ''}`)
        if (revision) usadas.add('aplica')
        // alerta_id: identificador interno, ya identificada por el codigo y el documento de la fila
        if (texto(d.alerta_id)) usadas.add('alerta_id')
      }
      break
    case 'decision_tomada':
      if (d.decision === 'aprobar' || d.decision === 'rechazar') usar('decision', `Decisión: ${ETIQUETA_DECISION[d.decision]}`)
      break
    case 'folio_creado':
    case 'original_visto':
      break
  }
  for (const [clave, valor] of Object.entries(d)) {
    if (!usadas.has(clave)) frases.push(`${legible(clave)}: ${enmascarar(valor)}`)
  }
  return frases
}
