// Codigos oficiales. Reflejo de docs/contratos/codigos_error.md y docs/contratos/codigos_alertas.md;
// lo comprueba backend/tests/test_contrato_frontend.py.
import type { Severidad } from './contrato'

/** Codigo de error -> estado HTTP (codigos_error.md) */
export const ESTADO_HTTP_POR_ERROR = {
  CREDENCIALES_INVALIDAS: 401,
  NO_AUTENTICADO: 401,
  TOKEN_CADUCADO: 401,
  SIN_PERMISO: 403,
  FOLIO_NO_ENCONTRADO: 404,
  DOCUMENTO_NO_ENCONTRADO: 404,
  ALERTA_NO_ENCONTRADA: 404,
  PROCESO_NO_ENCONTRADO: 404,
  RESUMEN_NO_DISPONIBLE: 404,
  RUTA_NO_ENCONTRADA: 404,
  METODO_NO_PERMITIDO: 405,
  DECISION_BLOQUEADA: 409,
  DOCUMENTO_EN_PROCESO: 409,
  FOLIO_CERRADO: 409,
  ARCHIVO_DEMASIADO_GRANDE: 413,
  FORMATO_NO_PERMITIDO: 415,
  PETICION_INVALIDA: 422,
  ERROR_INTERNO: 500,
} as const

export type CodigoError = keyof typeof ESTADO_HTTP_POR_ERROR
export const CODIGOS_ERROR = Object.keys(ESTADO_HTTP_POR_ERROR) as CodigoError[]

/** Codigos que solo genera el frontend (la API nunca los devuelve) */
export type CodigoLocal = 'SIN_CONEXION' | 'RESPUESTA_NO_VALIDA'

/** Alertas del catalogo con severidad fija (codigos_alertas.md) */
export const ALERTAS = {
  'CLS-001': { emisor: 'motor_ia', severidad: 'critica', cuando: 'Tipo declarado distinto del detectado' },
  'CLS-002': { emisor: 'motor_ia', severidad: 'preventiva', cuando: 'Confianza de clasificacion bajo el minimo de la ficha' },
  'VAL-001': { emisor: 'validacion', severidad: 'critica', cuando: 'Campo obligatorio ausente o null' },
  'VAL-002': { emisor: 'validacion', severidad: 'preventiva', cuando: 'Confianza del campo bajo el minimo de la ficha' },
  'DUP-001': { emisor: 'ingesta', severidad: 'critica', cuando: 'Mismo SHA-256 ya presente en el folio (no bloquea la subida)' },
  'CMP-001': { emisor: 'validacion', severidad: 'critica', cuando: 'Un campo comparado no coincide entre documentos (va en alertas_expediente)' },
  'EXP-001': { emisor: 'expediente', severidad: 'bloqueante', cuando: 'Falta un tipo requerido del proceso (va en alertas_expediente)' },
  'SYS-001': { emisor: 'motor_ia', severidad: 'critica', cuando: 'Fallo del proveedor principal y sin respaldo; estado_analisis=error' },
  'SYS-002': { emisor: 'motor_ia', severidad: 'critica', cuando: 'JSON del modelo invalido tras el reintento de correccion' },
  'VIS-001': { emisor: 'motor_ia', severidad: 'preventiva', cuando: 'Baja legibilidad o resolucion (extra 2)' },
  'VIS-002': { emisor: 'motor_ia', severidad: 'critica', cuando: 'Pagina incompleta o recortada (extra 2)' },
  'VIS-003': { emisor: 'motor_ia', severidad: 'critica', cuando: 'Alteracion o anomalia visible (extra 2)' },
} as const satisfies Record<string, { emisor: string; severidad: Severidad; cuando: string }>

/** Alertas de reglas de los YAML: REG-{id_regla}; su severidad la fija la ficha */
export const PREFIJO_REGLA = 'REG-'

export type CodigoAlerta = keyof typeof ALERTAS | `REG-${string}`

export function esCodigoAlertaOficial(codigo: string): codigo is CodigoAlerta {
  return codigo in ALERTAS || (codigo.startsWith(PREFIJO_REGLA) && codigo.length > PREFIJO_REGLA.length)
}
