// Acciones del revisor sobre documentos y expedientes (Contrato 2, reglas del ADR-006). Solo rol revisor,
// salvo revelar (revisor y admin, ADR-010 A4).
import type {
  PeticionConfirmarClasificacion, PeticionCorregirDatos, PeticionDecision, PeticionResolverAlerta, PeticionRetirar, PeticionRevelar,
  RespuestaRevelar, ResultadoDocumento, ResultadoExpediente,
} from '../tipos/contrato'
import { peticion } from './cliente'

const documento = (id: string) => `/documentos/${encodeURIComponent(id)}`
const folio = (id: string) => `/folios/${encodeURIComponent(id)}`

/** PATCH /documentos/{id}/datos: {campo: valor}; un campo vaciado se envia como null, nunca "" */
export function corregirDatos(id: string, cambios: PeticionCorregirDatos): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`${documento(id)}/datos`, { metodo: 'PATCH', cuerpo: cambios })
}

/** POST /documentos/{id}/confirmar-clasificacion (regla 2.5: si el tipo difiere, vuelve a pendiente) */
export function confirmarClasificacion(id: string, datos: PeticionConfirmarClasificacion): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`${documento(id)}/confirmar-clasificacion`, { metodo: 'POST', cuerpo: datos })
}

export function resolverAlertaDocumento(id: string, alertaId: string, datos: PeticionResolverAlerta): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`${documento(id)}/alertas/${encodeURIComponent(alertaId)}/resolver`, { metodo: 'POST', cuerpo: datos })
}

export function resolverAlertaExpediente(idFolio: string, alertaId: string, datos: PeticionResolverAlerta): Promise<ResultadoExpediente> {
  return peticion<ResultadoExpediente>(`${folio(idFolio)}/alertas/${encodeURIComponent(alertaId)}/resolver`, { metodo: 'POST', cuerpo: datos })
}

/** POST /folios/{folio}/decision: la decision es siempre humana y cierra el folio */
export function decidir(idFolio: string, datos: PeticionDecision): Promise<ResultadoExpediente> {
  return peticion<ResultadoExpediente>(`${folio(idFolio)}/decision`, { metodo: 'POST', cuerpo: datos })
}

/** POST /documentos/{id}/revelar (ADR-010 A4): valor real de un campo sensible; deja `dato_revelado` en la
 * auditoria. Revisor y admin. La respuesta no se guarda en ningun sitio (ni storage ni cache) */
export function revelarDato(id: string, datos: PeticionRevelar): Promise<RespuestaRevelar> {
  return peticion<RespuestaRevelar>(`${documento(id)}/revelar`, { metodo: 'POST', cuerpo: datos })
}

/** POST /documentos/{id}/retirar (ADR-013): revisor y admin; el documento deja de contar, nada se borra */
export function retirarDocumento(id: string, datos: PeticionRetirar): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`${documento(id)}/retirar`, { metodo: 'POST', cuerpo: datos })
}

/** POST /documentos/{id}/restaurar (ADR-013): deshace la retirada; sin cuerpo */
export function restaurarDocumento(id: string): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`${documento(id)}/restaurar`, { metodo: 'POST' })
}
