// Datos ficticios de los mocks, coherentes con fixtures/generados/INDICE.md (--hoy 2026-09-30).
// Los JSON se validan contra el contrato en backend/tests/test_contrato_frontend.py; por eso aqui
// basta con darles su tipo (TypeScript no conserva los literales de los enums al importar JSON).
import type { EntradaAuditoria, ProcesoCompleto, ResultadoExpediente, TipoDocumental } from '../../tipos/contrato'
import auditoria from './auditoria.json'
import folios from './folios.json'
import procesos from './procesos.json'
import tiposDocumentales from './tipos_documentales.json'

export const FOLIOS = folios as unknown as ResultadoExpediente[]
export const PROCESOS = procesos as ProcesoCompleto[]
export const TIPOS_DOCUMENTALES = tiposDocumentales as unknown as TipoDocumental[]
export const AUDITORIA = auditoria as unknown as EntradaAuditoria[]
