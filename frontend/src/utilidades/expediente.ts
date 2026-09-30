// Reglas del expediente compartidas por la UI y los mocks (acordadas con PERSONA_1).
import type { Alerta, Proceso, ResultadoDocumento, ResultadoExpediente } from '../tipos/contrato'

/** Regla 2.2 del ADR-006: una bloqueante impide aprobar mientras `aplica` no sea false (falso positivo) */
export const bloquea = (a: Alerta) => a.severidad === 'bloqueante' && a.aplica !== false

/** Alertas que impiden aprobar el folio, de documento y de expediente (regla 2.2) */
export function alertasQueBloquean(expediente: Pick<ResultadoExpediente, 'documentos' | 'alertas_expediente'>): Alerta[] {
  return [...expediente.alertas_expediente, ...expediente.documentos.flatMap((d) => d.alertas_encontradas)].filter(bloquea)
}

/** Tipo con cuya ficha se extrajo (regla 2.5): confirmado; si no, declarado; si no, detectado */
export const tipoExtraccion = (d: Pick<ResultadoDocumento, 'tipo_documental_confirmado' | 'tipo_documental_declarado' | 'tipo_documental_detectado'>) =>
  d.tipo_documental_confirmado ?? d.tipo_documental_declarado ?? d.tipo_documental_detectado

export const enProceso =(d: Pick<ResultadoDocumento, 'estado_analisis'>) =>
  d.estado_analisis === 'pendiente' || d.estado_analisis === 'procesando'

/** Tipo que cuenta para el expediente: el confirmado; si no hay, el detectado; si no, el declarado */
export function tipoEfectivo(doc: ResultadoDocumento): string | null {
  return doc.tipo_documental_confirmado ?? doc.tipo_documental_detectado ?? doc.tipo_documental_declarado
}

/** Tipos requeridos por el proceso que ningun documento del folio cubre (aviso de la pantalla de carga y EXP-001) */
export function tiposRequeridosQueFaltan(
  expediente: Pick<ResultadoExpediente, 'documentos'>, proceso: Pick<Proceso, 'tipos_requeridos'>,
): string[] {
  const presentes = new Set(expediente.documentos.map(tipoEfectivo))
  return proceso.tipos_requeridos.filter((tipo) => !presentes.has(tipo))
}

/** Tipos de los documentos que el proceso no pide ni como requeridos ni como opcionales (EXP-002) */
export function tiposNoPedidos(
  expediente: Pick<ResultadoExpediente, 'documentos'>, proceso: Pick<Proceso, 'tipos_requeridos' | 'tipos_opcionales'>,
): string[] {
  const pedidos = new Set([...proceso.tipos_requeridos, ...proceso.tipos_opcionales])
  const tipos = expediente.documentos.map(tipoEfectivo).filter((t): t is string => t !== null && !pedidos.has(t))
  return [...new Set(tipos)]
}
