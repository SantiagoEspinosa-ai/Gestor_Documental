// Respuestas de error de los mocks: el estado HTTP sale del codigo (codigos_error.md), nunca a mano.
import { HttpResponse } from 'msw'
import { ESTADO_HTTP_POR_ERROR, type CodigoError } from '../tipos/codigos'

export function error(codigo: CodigoError, mensaje: string): Response {
  const cabeceras: Record<string, string> = ESTADO_HTTP_POR_ERROR[codigo] === 401 ? { 'WWW-Authenticate': 'Bearer' } : {}
  return HttpResponse.json({ codigo, mensaje }, { status: ESTADO_HTTP_POR_ERROR[codigo], headers: cabeceras })
}

/** Se lanza desde la logica de los mocks y el envoltorio de las rutas la convierte en respuesta */
export class FalloApi extends Error {
  readonly codigo: CodigoError

  constructor(codigo: CodigoError, mensaje: string) {
    super(mensaje)
    this.codigo = codigo
  }
}

/** Cuerpo JSON de la peticion como objeto, o 422 PETICION_INVALIDA */
export async function leerJson(request: Request): Promise<Record<string, unknown>> {
  let cuerpo: unknown
  try {
    cuerpo = await request.json()
  } catch {
    throw new FalloApi('PETICION_INVALIDA', 'El cuerpo no es JSON valido')
  }
  if (typeof cuerpo !== 'object' || cuerpo === null || Array.isArray(cuerpo)) {
    throw new FalloApi('PETICION_INVALIDA', 'El cuerpo debe ser un objeto JSON')
  }
  return cuerpo as Record<string, unknown>
}
