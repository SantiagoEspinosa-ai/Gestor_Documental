// Tipos de la API (Contrato 2: docs/contratos/endpoints.md). Solo lo que usa el andamiaje;
// los modelos del Contrato 1 (resultado.py) se anaden con los mocks y las pantallas.

export type Rol = 'admin' | 'revisor' | 'integrador'

/** POST /auth/login */
export interface RespuestaLogin {
  access_token: string
  rol: Rol
  /** Segundos hasta que caduca el token */
  expires_in: number
}

/** GET /auth/yo */
export interface UsuarioActual {
  usuario: string
  rol: Rol
}

/** Cuerpo de todo error de la API */
export interface CuerpoError {
  codigo: string
  mensaje: string
}

/** Codigos de docs/contratos/codigos_error.md */
export const CODIGOS_ERROR = [
  'CREDENCIALES_INVALIDAS',
  'NO_AUTENTICADO',
  'TOKEN_CADUCADO',
  'SIN_PERMISO',
  'FOLIO_NO_ENCONTRADO',
  'DOCUMENTO_NO_ENCONTRADO',
  'ALERTA_NO_ENCONTRADA',
  'PROCESO_NO_ENCONTRADO',
  'RESUMEN_NO_DISPONIBLE',
  'RUTA_NO_ENCONTRADA',
  'METODO_NO_PERMITIDO',
  'DECISION_BLOQUEADA',
  'DOCUMENTO_EN_PROCESO',
  'FOLIO_CERRADO',
  'ARCHIVO_DEMASIADO_GRANDE',
  'FORMATO_NO_PERMITIDO',
  'PETICION_INVALIDA',
  'ERROR_INTERNO',
] as const

export type CodigoError = (typeof CODIGOS_ERROR)[number]

/** Codigos que solo genera el frontend (la API nunca los devuelve) */
export type CodigoLocal = 'SIN_CONEXION' | 'RESPUESTA_NO_VALIDA'
