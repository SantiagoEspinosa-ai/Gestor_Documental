// Tipos de los contratos. Un cambio aqui exige antes un cambio en el contrato (ADR).
//  - Contrato 1: backend/app/schemas/resultado.py (JSON de resultado). Reflejo exacto, campo a campo;
//    lo comprueba backend/tests/test_contrato_frontend.py.
//  - Contrato 2: docs/contratos/endpoints.md (peticiones y respuestas).
// Todas las claves estan siempre presentes en las respuestas (la API serializa los valores por
// defecto); por eso los opcionales de resultado.py son `T | null` y no `campo?`.

/** datetime ISO 8601, p. ej. "2026-09-30T10:00:00Z" */
export type FechaIso = string

// ------------------------------------------------------------------ Contrato 1: enums

export const SEVERIDADES = ['informativa', 'preventiva', 'critica', 'bloqueante'] as const
export type Severidad = (typeof SEVERIDADES)[number]

export const RECOMENDACIONES = ['aprobar', 'revision_manual', 'rechazar'] as const
export type Recomendacion = (typeof RECOMENDACIONES)[number]

export const ESTADOS_ANALISIS = ['pendiente', 'procesando', 'completado', 'error'] as const
export type EstadoAnalisis = (typeof ESTADOS_ANALISIS)[number]

export const ESTADOS_GENERALES = ['en_revision', 'aprobado', 'rechazado'] as const
export type EstadoGeneral = (typeof ESTADOS_GENERALES)[number]

export const DECISIONES_HUMANAS = ['aprobar', 'rechazar'] as const
export type DecisionHumana = (typeof DECISIONES_HUMANAS)[number]

// ------------------------------------------------------------------ Contrato 1: modelos

export interface Alerta {
  /** ADR-006 1.3: lo asigna la plataforma al guardar */
  id: string | null
  codigo: string
  mensaje: string
  severidad: Severidad
  /** 0..1 */
  confianza: number
  campo: string | null
  resuelta_por_revisor: boolean
  /** ADR-006 2.2: null = sin revisar; false = falso positivo */
  aplica: boolean | null
  comentario_revisor: string | null
  resuelta_por: string | null
  resuelta_en: FechaIso | null
}

export interface Reglas {
  cumplidas: string[]
  incumplidas: string[]
}

export interface FechaYModelo {
  fecha_analisis: FechaIso
  proveedor: string
  modelo: string
  version_prompt: string
}

export interface ReferenciaArchivoOriginal {
  nombre_archivo: string
  /** Clave en S3 */
  ruta: string
  /** SHA-256 */
  hash: string
}

/** ADR-006 2.4 */
export interface Correccion {
  campo: string
  valor_anterior: unknown
  valor_nuevo: unknown
  usuario: string
  fecha: FechaIso
}

export interface ResultadoDocumento {
  folio_solicitud: string
  /** UUID */
  identificador_unico_documento: string
  tipo_documental_declarado: string | null
  tipo_documental_detectado: string | null
  /** ADR-006 2.5: lo fija el revisor */
  tipo_documental_confirmado: string | null
  /** 0..1 */
  confianza_clasificacion: number | null
  /** Con las correcciones ya aplicadas */
  datos_extraidos: Record<string, unknown>
  nivel_confianza_por_campo: Record<string, number>
  /** "pagina_1", "pagina_2:seccion_superior", "correccion_revisor" */
  evidencia_por_campo: Record<string, string>
  reglas_cumplidas_e_incumplidas: Reglas
  alertas_encontradas: Alerta[]
  correcciones: Correccion[]
  recomendacion: Recomendacion | null
  estado_analisis: EstadoAnalisis
  fecha_y_modelo_utilizado: FechaYModelo | null
  referencia_archivo_original: ReferenciaArchivoOriginal
}

export interface ComparacionCampo {
  campo: string
  coincide: boolean
  /** {identificador_unico_documento: valor} */
  valores: Record<string, unknown>
}

export interface ResultadoExpediente {
  folio: string
  proceso: string
  /** ADR-004: id opaco del integrador, nunca el nombre */
  referencia_externa: string | null
  /** ADR-004: = folios.creado_en */
  fecha_solicitud: FechaIso | null
  estado_general: EstadoGeneral
  documentos: ResultadoDocumento[]
  comparaciones: ComparacionCampo[]
  /** EXP-001 y CMP-001 (ADR-006 2.3) */
  alertas_expediente: Alerta[]
  recomendacion_global: Recomendacion | null
  decision_humana: DecisionHumana | null
  /** ADR-006 G: datos de la decision; tras ella el folio queda cerrado */
  comentario_decision: string | null
  usuario_decision: string | null
  fecha_decision: FechaIso | null
  ruta_resumen_md: string | null
}

/** ADR-006 1.1: elemento de GET /folios */
export interface ResumenFolio {
  folio: string
  proceso: string
  estado_general: EstadoGeneral
  recomendacion_global: Recomendacion | null
  n_documentos: number
  n_bloqueantes_sin_resolver: number
  fecha_solicitud: FechaIso | null
  /** ADR-008; = folios.referencia_externa (id opaco, ADR-004) */
  referencia_externa: string | null
}

// ------------------------------------------------------------------ Contrato 2: peticiones y respuestas

export const ROLES = ['admin', 'revisor', 'integrador'] as const
export type Rol = (typeof ROLES)[number]

/** Cuerpo de todo error de la API (docs/contratos/codigos_error.md) */
export interface CuerpoError {
  codigo: string
  mensaje: string
}

/** POST /auth/login (JSON, no formulario OAuth2) */
export interface PeticionLogin {
  usuario: string
  contrasena: string
}

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

/** GET /procesos para admin e integrador */
export interface ProcesoCompleto {
  nombre: string
  prefijo_folio: string
  tipos_requeridos: string[]
  tipos_opcionales: string[]
  permitir_antecedentes: boolean
  caducidad_antecedentes_dias: number
  /** Vacio = sin webhook */
  webhook_url: string
  modelos: string
}

/** GET /procesos para el revisor: sin webhook_url ni modelos */
export type ProcesoRevisor = Omit<ProcesoCompleto, 'webhook_url' | 'modelos'>
export type Proceso = ProcesoCompleto | ProcesoRevisor

/** POST /folios */
export interface PeticionCrearFolio {
  proceso: string
  referencia_externa?: string
}

export interface RespuestaCrearFolio {
  folio: string
  estado_general: EstadoGeneral
}

/** Query de GET /folios */
export interface FiltrosFolios {
  proceso?: string
  estado_general?: EstadoGeneral
  /** >= 1 */
  pagina?: number
  /** 1..100, 20 por defecto */
  tamano_pagina?: number
}

/** GET /auditoria (ADR-008, punto 1) */
export interface FiltrosAuditoria {
  folio?: string
  /** >= 1 */
  pagina?: number
  /** 1..100, 50 por defecto */
  tamano_pagina?: number
}

/** GET /folios */
export interface PaginaFolios {
  elementos: ResumenFolio[]
  total: number
  pagina: number
  tamano_pagina: number
}

/** POST /folios/{folio}/documentos: multipart `archivo` (max. 20 MB) y `tipo_declarado?` */
export interface RespuestaSubidaDocumento {
  identificador_unico_documento: string
  estado_analisis: 'pendiente'
}

/** GET /documentos/{id}/original */
export interface RespuestaOriginal {
  url: string
}

/** PATCH /documentos/{id}/datos: {campo: valor} */
export type PeticionCorregirDatos = Record<string, unknown>

/** POST /documentos/{id}/confirmar-clasificacion */
export interface PeticionConfirmarClasificacion {
  tipo_documental: string
}

/** POST /documentos/{id}/alertas/{alerta_id}/resolver y POST /folios/{folio}/alertas/{alerta_id}/resolver */
export interface PeticionResolverAlerta {
  aplica: boolean
  comentario?: string
}

/** POST /folios/{folio}/decision */
export interface PeticionDecision {
  decision: DecisionHumana
  comentario?: string
}

/** GET /folios/{folio}/antecedentes: forma pendiente de un ADR de la etapa 3 */
export type RespuestaAntecedentes = unknown[]

export interface CampoFicha {
  tipo: string
  obligatorio: boolean
  patron?: string
}

export interface ReglaFicha {
  id: string
  tipo: string
  campo: string
  severidad: Severidad
  mensaje: string
  dias?: number
}

/** GET /tipos-documentales: la ficha YAML tal como la valida `configuracion` */
export interface TipoDocumental {
  nombre: string
  nombre_visible: string
  categoria: string
  descripcion: string
  formatos_permitidos: string[]
  campos: Record<string, CampoFicha>
  confianza_minima_clasificacion: number
  confianza_minima_campo: number
  reglas: ReglaFicha[]
  comparaciones: Record<string, string[]>
}

export const ACCIONES_AUDITORIA = [
  'login',
  'folio_creado',
  'documento_subido',
  'documento_procesado',
  'dato_corregido',
  'clasificacion_confirmada',
  'alerta_resuelta',
  'decision_tomada',
  'dato_revelado', // etapa 3
] as const
export type AccionAuditoria = (typeof ACCIONES_AUDITORIA)[number]

/** GET /auditoria?folio=, del mas reciente al mas antiguo */
export interface EntradaAuditoria {
  id: number
  usuario: string | null
  accion: AccionAuditoria
  folio: string | null
  documento_id: string | null
  /** Nunca valores sensibles sin enmascarar */
  detalle: Record<string, unknown>
  modelo: string | null
  version_prompt: string | null
  creado_en: FechaIso
}

/**
 * GET /auditoria?folio=&pagina=1&tamano_pagina=50 (ADR-008, punto 1): tamano_pagina de 1 a 100 (50 por
 * defecto), orden creado_en desc e id desc, filtro por folio; fuera de rango, 422 PETICION_INVALIDA.
 * Misma forma que PaginaFolios.
 */
export interface PaginaAuditoria {
  elementos: EntradaAuditoria[]
  total: number
  pagina: number
  tamano_pagina: number
}
