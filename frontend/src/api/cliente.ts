// Cliente HTTP de la API (Contrato 2). Anade el token Bearer y convierte los errores
// {codigo, mensaje} (docs/contratos/codigos_error.md) en ErrorApi.
import type { CodigoError, CodigoLocal } from '../tipos/codigos'
import { entorno } from '../utilidades/entorno'
import { borrarSesion, leerSesion } from './sesion'

export class ErrorApi extends Error {
  /** Estado HTTP; 0 si no hubo respuesta */
  readonly estado: number
  readonly codigo: CodigoError | CodigoLocal | (string & {})

  constructor(estado: number, codigo: ErrorApi['codigo'], mensaje: string) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.estado = estado
    this.codigo = codigo
  }

  /** 409 FOLIO_CERRADO: el folio ya se decidio y la UI debe pasar a solo lectura */
  get esSoloLectura(): boolean {
    return this.estado === 409 && this.codigo === 'FOLIO_CERRADO'
  }
}

// Avisos para la UI: sesion cerrada por un 401 y folio en solo lectura
const alCaducar = new Set<() => void>()
const alCerrarFolio = new Set<(error: ErrorApi) => void>()

/** Se llama cuando la API responde 401 y la sesion se borra. Devuelve la funcion para darse de baja. */
export function alSesionCaducada(oyente: () => void): () => void {
  alCaducar.add(oyente)
  return () => alCaducar.delete(oyente)
}

/** Se llama cuando la API responde 409 FOLIO_CERRADO. Devuelve la funcion para darse de baja. */
export function alFolioCerrado(oyente: (error: ErrorApi) => void): () => void {
  alCerrarFolio.add(oyente)
  return () => alCerrarFolio.delete(oyente)
}

export interface OpcionesPeticion {
  metodo?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  /** Se envia como JSON */
  cuerpo?: unknown
  /** Se envia como multipart (subida de documentos); el navegador pone el boundary */
  formulario?: FormData
  /** 'texto' para respuestas text/markdown como resumen.md */
  respuesta?: 'json' | 'texto'
  /** Peticiones sin token (login): un 401 aqui no cierra ninguna sesion */
  sinAutenticacion?: boolean
  signal?: AbortSignal
}

export async function peticion<T>(ruta: string, opciones: OpcionesPeticion = {}): Promise<T> {
  const cabeceras: Record<string, string> = {
    Accept: opciones.respuesta === 'texto' ? 'text/markdown, text/plain' : 'application/json',
  }
  const sesion = opciones.sinAutenticacion ? null : leerSesion()
  if (sesion) cabeceras.Authorization = `Bearer ${sesion.token}`

  let cuerpo: BodyInit | undefined
  if (opciones.formulario) {
    cuerpo = opciones.formulario
  } else if (opciones.cuerpo !== undefined) {
    cabeceras['Content-Type'] = 'application/json'
    cuerpo = JSON.stringify(opciones.cuerpo)
  }

  let respuesta: Response
  try {
    respuesta = await fetch(`${entorno.apiBase}${ruta}`, {
      method: opciones.metodo ?? 'GET',
      headers: cabeceras,
      body: cuerpo,
      signal: opciones.signal,
    })
  } catch (causa) {
    if (causa instanceof DOMException && causa.name === 'AbortError') throw causa
    throw new ErrorApi(0, 'SIN_CONEXION', 'No se pudo conectar con el servidor')
  }

  if (!respuesta.ok) {
    const error = await leerError(respuesta)
    // El cierre de sesion lo decide el estado HTTP 401, no el codigo (NO_AUTENTICADO, TOKEN_CADUCADO...)
    if (respuesta.status === 401 && !opciones.sinAutenticacion) {
      borrarSesion()
      alCaducar.forEach((oyente) => oyente())
    }
    if (error.esSoloLectura) alCerrarFolio.forEach((oyente) => oyente(error))
    throw error
  }

  if (respuesta.status === 204) return undefined as T
  const texto = await respuesta.text()
  if (opciones.respuesta === 'texto') return texto as T
  if (!texto) return undefined as T
  try {
    return JSON.parse(texto) as T
  } catch {
    throw new ErrorApi(respuesta.status, 'RESPUESTA_NO_VALIDA', 'La respuesta de la API no es JSON valido')
  }
}

async function leerError(respuesta: Response): Promise<ErrorApi> {
  try {
    const cuerpo: unknown = await respuesta.json()
    if (
      typeof cuerpo === 'object' && cuerpo !== null &&
      typeof (cuerpo as { codigo?: unknown }).codigo === 'string' &&
      typeof (cuerpo as { mensaje?: unknown }).mensaje === 'string'
    ) {
      const { codigo, mensaje } = cuerpo as { codigo: string; mensaje: string }
      return new ErrorApi(respuesta.status, codigo, mensaje)
    }
  } catch {
    // cuerpo vacio o no JSON
  }
  return new ErrorApi(
    respuesta.status,
    'RESPUESTA_NO_VALIDA',
    `La API respondio ${respuesta.status} sin el formato {codigo, mensaje}`,
  )
}
