// Textos visibles de los valores del contrato
import type { EstadoAnalisis, EstadoGeneral, Recomendacion, Rol } from '../tipos/contrato'

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

/** Fecha y hora locales en formato corto (DD/MM/AAAA, HH:MM) */
export function fechaHora(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
