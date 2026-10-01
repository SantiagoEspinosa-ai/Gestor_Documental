// Texto legible del `detalle` de cada entrada de auditoria (endpoints.md, EntradaAuditoria).
// Nunca se muestra el JSON en bruto. El contrato dice que `detalle` no lleva valores sensibles sin
// enmascarar; aun asi, cualquier clave que no sea de la forma conocida de su accion se enmascara aqui
// (si la API anade, por ejemplo, el valor corregido o un comentario, no sale completo en pantalla).
import { ACCIONES_AUDITORIA, type AccionAuditoria, type EntradaAuditoria } from '../tipos/contrato'
import { ETIQUETA_ACCION, ETIQUETA_DECISION, ETIQUETA_ESTADO_ANALISIS } from './etiquetas'

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

/**
 * Frases del detalle. Para cada accion se formatean sus claves conocidas si tienen el tipo esperado;
 * el resto (o una clave conocida con otro tipo) sale como "clave: ****1234".
 */
export function describirDetalle(entrada: Pick<EntradaAuditoria, 'accion' | 'detalle'>, tipos: NombresTipos = {}): string[] {
  const d = entrada.detalle ?? {}
  const frases: string[] = []
  const usadas = new Set<string>()
  const usar = (clave: string, frase: string) => { usadas.add(clave); frases.push(frase) }

  switch (entrada.accion) {
    case 'login':
      if (d.resultado === 'ok') usar('resultado', 'Acceso correcto')
      else if (d.resultado === 'fallido') usar('resultado', 'Intento fallido')
      break
    case 'documento_subido':
      if (texto(d.hash_sha256)) usar('hash_sha256', `SHA-256 ${d.hash_sha256.slice(0, 12)}…`)
      if (typeof d.tamano_bytes === 'number') usar('tamano_bytes', tamano(d.tamano_bytes))
      if (typeof d.duplicado === 'boolean') usar('duplicado', d.duplicado ? 'Duplicado en el folio (DUP-001)' : 'No duplicado')
      break
    case 'documento_procesado':
      if (texto(d.estado_analisis) && d.estado_analisis in ETIQUETA_ESTADO_ANALISIS) {
        usar('estado_analisis', `Resultado: ${ETIQUETA_ESTADO_ANALISIS[d.estado_analisis as keyof typeof ETIQUETA_ESTADO_ANALISIS]}`)
      }
      break
    case 'dato_corregido':
      if (texto(d.campo)) usar('campo', `Campo: ${legible(d.campo)}`)
      break
    case 'dato_revelado':
      if (texto(d.campo)) usar('campo', `Campo mostrado: ${legible(d.campo)}`)
      break
    case 'clasificacion_confirmada':
      if (texto(d.tipo_documental)) usar('tipo_documental', `Tipo confirmado: ${tipos[d.tipo_documental] ?? legible(d.tipo_documental)}`)
      break
    case 'alerta_resuelta':
      if (texto(d.codigo)) {
        const revision = d.aplica === true ? 'aplica' : d.aplica === false ? 'falso positivo' : null
        usar('codigo', `Alerta ${d.codigo}${revision ? `: ${revision}` : ''}`)
        if (revision) usadas.add('aplica')
      }
      break
    case 'decision_tomada':
      if (d.decision === 'aprobar' || d.decision === 'rechazar') usar('decision', `Decisión: ${ETIQUETA_DECISION[d.decision]}`)
      break
    case 'folio_creado':
      break
  }
  for (const [clave, valor] of Object.entries(d)) {
    if (!usadas.has(clave)) frases.push(`${legible(clave)}: ${enmascarar(valor)}`)
  }
  return frases
}
