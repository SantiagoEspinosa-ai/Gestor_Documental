// Textos visibles de los valores del contrato
import type {
  AccionAuditoria, Alerta, DecisionHumana, EstadoAnalisis, EstadoGeneral, Recomendacion, Rol, Severidad,
} from '../tipos/contrato'

export const ETIQUETA_ROL: Record<Rol, string> = { admin: 'Administración', revisor: 'Revisión', integrador: 'Integración' }

export const ETIQUETA_ESTADO_GENERAL: Record<EstadoGeneral, string> = {
  en_revision: 'En revisión', aprobado: 'Aprobado', rechazado: 'Rechazado',
}

export const ETIQUETA_RECOMENDACION: Record<Recomendacion, string> = {
  aprobar: 'Aprobar', revision_manual: 'Revisión manual', rechazar: 'Rechazar',
}

export const ETIQUETA_ESTADO_ANALISIS: Record<EstadoAnalisis, string> = {
  pendiente: 'Pendiente', procesando: 'Procesando', completado: 'Completado', error: 'Error',
}

export const ETIQUETA_SEVERIDAD: Record<Severidad, string> = {
  bloqueante: 'Bloqueante', critica: 'Crítica', preventiva: 'Preventiva', informativa: 'Informativa',
}

export const ETIQUETA_DECISION: Record<DecisionHumana, string> = { aprobar: 'Aprobado', rechazar: 'Rechazado' }

/** Lista cerrada de acciones de la auditoria (ADR-006 1.5; dato_revelado en la etapa 3) */
export const ETIQUETA_ACCION: Record<AccionAuditoria, string> = {
  login: 'Inicio de sesión',
  folio_creado: 'Folio creado',
  documento_subido: 'Documento subido',
  documento_procesado: 'Documento analizado',
  dato_corregido: 'Dato corregido',
  clasificacion_confirmada: 'Clasificación confirmada',
  alerta_resuelta: 'Alerta revisada',
  decision_tomada: 'Decisión del folio',
  dato_revelado: 'Dato revelado',
}

/** Estado de revision de una alerta (ADR-006 2.2): null = sin revisar; false = falso positivo */
export function etiquetaRevision(alerta: Pick<Alerta, 'aplica'>): string {
  if (alerta.aplica === null) return 'Sin revisar'
  return alerta.aplica ? 'Aplica (confirmada por el revisor)' : 'Falso positivo'
}

/**
 * Segundos que un dato sensible revelado con "Mostrar" (ADR-010 A4) queda a la vista antes de ocultarse
 * solo. Unico sitio de este valor: lo usan DatoSensible y sus tests.
 */
export const SEGUNDOS_DATO_REVELADO = 60

/** Barra de confianza por campo (ADR-007): la calcula el codigo comprobando el dato, no el modelo */
export const ETIQUETA_CONFIANZA = 'Confianza verificada'
export const AYUDA_CONFIANZA =
  'Grado en que se ha podido comprobar el dato en el propio documento (aparece en el texto, cumple el formato ' +
  'y el tipo esperados). No es la seguridad del modelo. Un campo corregido por el revisor vale 100 %.'

/** Fecha y hora locales en formato corto (DD/MM/AAAA, HH:MM) */
export function fechaHora(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** Como fechaHora, con segundos (auditoria: varias acciones en el mismo minuto) */
export function fechaHoraCompleta(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
