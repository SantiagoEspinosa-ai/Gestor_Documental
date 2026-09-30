// Estado en memoria de los mocks. Se crea a partir de mocks/datos y se pierde al recargar la pagina.
import type {
  AccionAuditoria, EntradaAuditoria, ProcesoCompleto, ResultadoDocumento, ResultadoExpediente, Rol, TipoDocumental,
} from '../tipos/contrato'
import { AUDITORIA, FOLIOS, PROCESOS, TIPOS_DOCUMENTALES } from './datos'
import { DURACION_SESION_S } from './usuarios'

export interface SesionMock {
  usuario: string
  rol: Rol
  expiraEn: number
}

/** Documento subido en esta sesion: su analisis avanza con el reloj */
export interface Procesamiento {
  inicio: number
  /** Tipo con cuya ficha se extrae (regla 2.5: confirmado > declarado > detectado) */
  tipoExtraccion: string
  /** Tipo real del contenido, el que "detecta" el clasificador simulado */
  tipoContenido: string
  confianzaClasificacion: number
  /** Documento de los datos con el mismo SHA-256 (se reutilizan sus valores) */
  origen?: ResultadoDocumento
}

export interface EstadoMock {
  /** Reloj inyectable para los tests (milisegundos) */
  ahora: () => number
  duracionSesionS: number
  folios: Map<string, ResultadoExpediente>
  procesos: ProcesoCompleto[]
  tipos: TipoDocumental[]
  auditoria: EntradaAuditoria[]
  sesiones: Map<string, SesionMock>
  procesamientos: Map<string, Procesamiento>
  archivos: Map<string, Blob>
  urls: Map<string, string>
  /** Resultado anterior al reprocesar por una clasificacion confirmada distinta (ADR-006 2.5) */
  versionesPrevias: Map<string, ResultadoDocumento[]>
  contador: number
}

export function crearEstado(ahora: () => number = () => Date.now()): EstadoMock {
  return {
    ahora,
    duracionSesionS: DURACION_SESION_S,
    folios: new Map(structuredClone(FOLIOS).map((f) => [f.folio, f])),
    procesos: structuredClone(PROCESOS),
    tipos: structuredClone(TIPOS_DOCUMENTALES),
    auditoria: structuredClone(AUDITORIA),
    sesiones: new Map(),
    procesamientos: new Map(),
    archivos: new Map(),
    urls: new Map(),
    versionesPrevias: new Map(),
    contador: 0,
  }
}

export function fechaIso(estado: EstadoMock): string {
  return new Date(estado.ahora()).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

export function siguiente(estado: EstadoMock): number {
  estado.contador += 1
  return estado.contador
}

export function buscarDocumento(estado: EstadoMock, id: string) {
  for (const folio of estado.folios.values()) {
    const doc = folio.documentos.find((d) => d.identificador_unico_documento === id)
    if (doc) return { folio, doc }
  }
  return null
}

export function auditar(
  estado: EstadoMock, usuario: string | null, accion: AccionAuditoria, folio: string | null,
  documentoId: string | null, detalle: Record<string, unknown> = {},
  modelo: string | null = null, versionPrompt: string | null = null,
): void {
  const id = Math.max(0, ...estado.auditoria.map((e) => e.id)) + 1
  estado.auditoria.push({
    id, usuario, accion, folio, documento_id: documentoId, detalle, modelo, version_prompt: versionPrompt,
    creado_en: fechaIso(estado),
  })
}
