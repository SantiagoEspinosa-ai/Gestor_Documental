// Reglas del expediente compartidas por la UI y los mocks (acordadas con PERSONA_1).
import type { Proceso, ResultadoDocumento, ResultadoExpediente } from '../tipos/contrato'

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
