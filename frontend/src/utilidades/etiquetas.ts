// Textos visibles de los valores del contrato
import type { Alerta, DecisionHumana, EstadoAnalisis, EstadoGeneral, Recomendacion, Rol, Severidad } from '../tipos/contrato'

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

/** Estado de revision de una alerta (ADR-006 2.2): null = sin revisar; false = falso positivo */
export function etiquetaRevision(alerta: Pick<Alerta, 'aplica'>): string {
  if (alerta.aplica === null) return 'Sin revisar'
  return alerta.aplica ? 'Aplica (confirmada por el revisor)' : 'Falso positivo'
}

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
