// Textos visibles de los valores del contrato
import type {
  AccionAuditoria, Alerta, DecisionHumana, EstadoAnalisis, EstadoGeneral, FaseAnalisis, MotivoSinAntecedentes, Recomendacion,
  Rol, Severidad,
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

/** ADR-014: frase de la fase en el aviso del documento que se esta analizando */
export const ETIQUETA_FASE: Record<FaseAnalisis, string> = {
  en_cola: 'En espera: se analiza un documento cada vez',
  preparando: 'Preparando el documento',
  ocr: 'Leyendo el texto (OCR)',
  clasificando: 'Identificando el tipo de documento',
  vision: 'La foto es difícil: la estamos leyendo como imagen, puede tardar unos minutos',
  extrayendo: 'Extrayendo los datos',
}

/** ADR-014: version corta, bajo "Procesando" en la lista de documentos del expediente */
export const ETIQUETA_FASE_CORTA: Record<FaseAnalisis, string> = {
  en_cola: 'En espera',
  preparando: 'Preparando',
  ocr: 'Leyendo el texto',
  clasificando: 'Identificando el tipo',
  vision: 'Leyendo como imagen',
  extrayendo: 'Extrayendo los datos',
}

export const ETIQUETA_SEVERIDAD: Record<Severidad, string> = {
  bloqueante: 'Bloqueante', critica: 'Crítica', preventiva: 'Preventiva', informativa: 'Informativa',
}

export const ETIQUETA_DECISION: Record<DecisionHumana, string> = { aprobar: 'Aprobado', rechazar: 'Rechazado' }

/** Lista cerrada de acciones de la auditoria (ADR-006 1.5; dato_revelado en la etapa 3; original_visto post-MVP; documento_retirado/restaurado ADR-013) */
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
  original_visto: 'Original consultado',
  documento_retirado: 'Documento retirado',
  documento_restaurado: 'Documento restaurado',
}

/** Estado de revision de una alerta (ADR-006 2.2): null = sin revisar; false = falso positivo */
export function etiquetaRevision(alerta: Pick<Alerta, 'aplica'>): string {
  if (alerta.aplica === null) return 'Sin revisar'
  return alerta.aplica ? 'Aplica (confirmada por el revisor)' : 'Falso positivo'
}

/** Por que un folio no tiene antecedentes (ADR-010 C3) */
export const ETIQUETA_MOTIVO_SIN_ANTECEDENTES: Record<MotivoSinAntecedentes, string> = {
  proceso_sin_antecedentes: 'El proceso de este folio no consulta antecedentes.',
  folio_sin_referencia: 'Este folio no tiene referencia externa: no se pueden relacionar antecedentes.',
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

/** ADR-014: tiempo que lleva una fase, contado en el cliente: "lleva 45 s", "lleva 1 min 20 s", "lleva 2 min" */
export function textoTranscurrido(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos))
  const minutos = Math.floor(s / 60)
  const resto = s % 60
  if (minutos === 0) return `lleva ${resto} s`
  return resto === 0 ? `lleva ${minutos} min` : `lleva ${minutos} min ${resto} s`
}
