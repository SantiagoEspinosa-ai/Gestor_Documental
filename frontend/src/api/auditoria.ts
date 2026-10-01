// Registro de acciones (Contrato 2, ADR-008): solo rol admin
import type { FiltrosAuditoria, PaginaAuditoria } from '../tipos/contrato'
import { peticion } from './cliente'

export function listarAuditoria(filtros: FiltrosAuditoria, signal?: AbortSignal): Promise<PaginaAuditoria> {
  const q = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) if (valor !== undefined && valor !== '') q.set(clave, String(valor))
  return peticion<PaginaAuditoria>(`/auditoria${q.size ? `?${q}` : ''}`, { signal })
}
