// Mensajes para la persona usuaria segun el codigo de error (codigos_error.md y los pendientes de main).
import { ErrorApi } from '../api/cliente'
import type { CodigoError, CodigoLocal } from '../tipos/codigos'

/** Un mensaje por codigo: TypeScript falla si se anade un codigo sin su mensaje */
export const MENSAJES_ERROR: Record<CodigoError | CodigoLocal, string> = {
  CREDENCIALES_INVALIDAS: 'Usuario o contraseña incorrectos.',
  NO_AUTENTICADO: 'Tu sesión no es válida. Vuelve a entrar.',
  TOKEN_CADUCADO: 'Tu sesión ha caducado. Vuelve a entrar.',
  SIN_PERMISO: 'Tu rol no tiene permiso para esta acción.',
  FOLIO_NO_ENCONTRADO: 'El folio no existe.',
  DOCUMENTO_NO_ENCONTRADO: 'El documento no existe.',
  ALERTA_NO_ENCONTRADA: 'La alerta no existe.',
  PROCESO_NO_ENCONTRADO: 'El proceso no existe.',
  RESUMEN_NO_DISPONIBLE: 'El resumen de este folio aún no está disponible.',
  RUTA_NO_ENCONTRADA: 'La API no reconoce esta operación.',
  METODO_NO_PERMITIDO: 'La API no permite esta operación.',
  DECISION_BLOQUEADA: 'No se puede aprobar: hay alertas bloqueantes sin descartar.',
  DOCUMENTO_EN_PROCESO: 'El documento aún se está analizando.',
  FOLIO_CERRADO: 'El folio ya está decidido: solo lectura.',
  ARCHIVO_DEMASIADO_GRANDE: 'El archivo supera los 20 MB.',
  FORMATO_NO_PERMITIDO: 'El archivo no es válido: su formato o su contenido no corresponde a los formatos permitidos.',
  PETICION_INVALIDA: 'Los datos enviados no son válidos.',
  ERROR_INTERNO: 'Error interno del servidor. Inténtalo de nuevo más tarde.',
  DOCUMENTO_CON_ERROR: 'El documento terminó en error: no se puede corregir ni reclasificar.',
  DOCUMENTO_RETIRADO: 'El documento está retirado del folio. Restáuralo antes de revisarlo.',
  DOCUMENTO_NO_RETIRADO: 'El documento no está retirado.',
  SECUENCIA_AGOTADA: 'No quedan números de folio libres este año para el proceso.',
  SIN_CONEXION: 'No se pudo conectar con el servidor.',
  RESPUESTA_NO_VALIDA: 'La respuesta del servidor no tiene el formato esperado.',
}

/** Mensaje para mostrar; con PETICION_INVALIDA se anade el detalle de la API */
export function mensajeDeError(error: unknown): string {
  if (!(error instanceof ErrorApi)) return 'Ha ocurrido un error inesperado.'
  const base = MENSAJES_ERROR[error.codigo as CodigoError | CodigoLocal]
  if (!base) return error.message || 'Ha ocurrido un error inesperado.'
  return error.codigo === 'PETICION_INVALIDA' && error.message ? `${base} ${error.message}` : base
}

/** Mensajes propios de "Mostrar" (POST /documentos/{id}/revelar) para los codigos que pueden salir ahi */
const MENSAJES_REVELAR: Partial<Record<CodigoError, string>> = {
  DOCUMENTO_EN_PROCESO: 'El documento aún se está analizando: no se puede mostrar el dato todavía.',
  DOCUMENTO_CON_ERROR: 'El documento terminó en error: no tiene datos que mostrar.',
  SIN_PERMISO: 'Tu rol no puede ver datos sensibles.',
  PETICION_INVALIDA: 'Este campo no se puede mostrar.',
}

/** Mensaje de un fallo al mostrar un dato sensible; el resto de codigos, como en cualquier pantalla */
export function mensajeRevelar(error: unknown): string {
  if (error instanceof ErrorApi) {
    const propio = MENSAJES_REVELAR[error.codigo as CodigoError]
    if (propio) return propio
  }
  return mensajeDeError(error)
}
