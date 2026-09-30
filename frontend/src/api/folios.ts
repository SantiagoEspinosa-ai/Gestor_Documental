// Folios, procesos, tipos documentales y documentos (Contrato 2)
import type {
  FiltrosFolios, PaginaFolios, PeticionCrearFolio, Proceso, RespuestaCrearFolio, RespuestaSubidaDocumento,
  ResultadoDocumento, ResultadoExpediente, TipoDocumental,
} from '../tipos/contrato'
import { peticion } from './cliente'

export function listarFolios(filtros: FiltrosFolios, signal?: AbortSignal): Promise<PaginaFolios> {
  const q = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) if (valor !== undefined && valor !== '') q.set(clave, String(valor))
  return peticion<PaginaFolios>(`/folios${q.size ? `?${q}` : ''}`, { signal })
}

export function obtenerFolio(folio: string, signal?: AbortSignal): Promise<ResultadoExpediente> {
  return peticion<ResultadoExpediente>(`/folios/${encodeURIComponent(folio)}`, { signal })
}

export function crearFolio(datos: PeticionCrearFolio): Promise<RespuestaCrearFolio> {
  return peticion<RespuestaCrearFolio>('/folios', { metodo: 'POST', cuerpo: datos })
}

export function listarProcesos(signal?: AbortSignal): Promise<Proceso[]> {
  return peticion<Proceso[]>('/procesos', { signal })
}

export function listarTiposDocumentales(signal?: AbortSignal): Promise<TipoDocumental[]> {
  return peticion<TipoDocumental[]>('/tipos-documentales', { signal })
}

export function subirDocumento(folio: string, archivo: File, tipoDeclarado?: string): Promise<RespuestaSubidaDocumento> {
  const formulario = new FormData()
  formulario.append('archivo', archivo, archivo.name)
  if (tipoDeclarado) formulario.append('tipo_declarado', tipoDeclarado)
  return peticion<RespuestaSubidaDocumento>(`/folios/${encodeURIComponent(folio)}/documentos`, { metodo: 'POST', formulario })
}

export function obtenerDocumento(id: string, signal?: AbortSignal): Promise<ResultadoDocumento> {
  return peticion<ResultadoDocumento>(`/documentos/${encodeURIComponent(id)}`, { signal })
}
