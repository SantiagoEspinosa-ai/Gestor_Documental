// Tests de los mocks con msw/node. Datos ficticios; usuarios de src/mocks/usuarios.ts.
import { existsSync, readFileSync } from 'node:fs'
import { setupServer } from 'msw/node'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import {
  ROLES, type Alerta, type PaginaAuditoria, type PaginaFolios, type ResultadoDocumento, type ResultadoExpediente,
} from '../tipos/contrato'
import { crearEstado, type EstadoMock } from './estado'
import { crearHandlers } from './handlers'
import { MS_HASTA_COMPLETADO, MS_HASTA_PROCESANDO } from './logica'

const API = 'http://localhost:8000/api/v1'
const CONTRATO = new URL('../../../docs/contratos/endpoints.md', import.meta.url)
const ORIGINALES = new URL('../../public/mock-originales/', import.meta.url)

let t = Date.UTC(2026, 9, 1, 10, 0, 0)
let estado: EstadoMock
const servidor = setupServer()

beforeAll(() => servidor.listen({ onUnhandledRequest: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => {
  t = Date.UTC(2026, 9, 1, 10, 0, 0)
  estado = crearEstado(() => t)
  servidor.resetHandlers(...crearHandlers(estado).handlers)
})

interface Respuesta<T = unknown> { status: number; cuerpo: T; texto: string }

async function api<T = Record<string, unknown>>(metodo: string, ruta: string,
  opciones: { token?: string; cuerpo?: unknown; formulario?: FormData } = {}): Promise<Respuesta<T>> {
  const cabeceras: Record<string, string> = opciones.token ? { Authorization: `Bearer ${opciones.token}` } : {}
  if (opciones.cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json'
  const r = await fetch(`${API}${ruta}`, {
    method: metodo, headers: cabeceras,
    body: opciones.formulario ?? (opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined),
  })
  const texto = await r.text()
  let cuerpo: unknown = texto
  try { cuerpo = JSON.parse(texto) } catch { /* texto plano (resumen.md) */ }
  return { status: r.status, cuerpo: cuerpo as T, texto }
}

const CONTRASENAS = { 'admin.demo': 'demo-admin', 'revisor.demo': 'demo-revisor', 'integrador.demo': 'demo-integrador' }
async function entrar(usuario: keyof typeof CONTRASENAS): Promise<string> {
  const r = await api<{ access_token: string }>('POST', '/auth/login', { cuerpo: { usuario, contrasena: CONTRASENAS[usuario] } })
  expect(r.status).toBe(200)
  return r.cuerpo.access_token
}

function subida(nombre: string, datos: Uint8Array | Buffer, tipo?: string): FormData {
  const f = new FormData()
  f.append('archivo', new File([new Uint8Array(datos)], nombre))
  if (tipo) f.append('tipo_declarado', tipo)
  return f
}
const original = (nombre: string) => readFileSync(new URL(nombre, ORIGINALES))
const codigos = (alertas: Alerta[]) => alertas.map((a) => a.codigo)

// ------------------------------------------------------------------ cobertura del contrato

describe.skipIf(!existsSync(CONTRATO))('cobertura de docs/contratos/endpoints.md', () => {
  const filas = [...readFileSync(CONTRATO, 'utf-8').matchAll(/^\| (GET|POST|PATCH|PUT|DELETE) \| ([^|]+?) \| ([^|]+?) \|/gm)]
  const contrato = filas.map(([, metodo, ruta, rol]) => ({
    metodo, ruta: ruta.split('?')[0],
    roles: rol === '-' ? null : rol === 'todos' ? [...ROLES].sort() : rol.split(',').map((r) => r.trim()).sort(),
  }))

  it('hay un handler por cada endpoint del contrato, con sus roles, y ninguno de mas', () => {
    const mocks = crearHandlers(crearEstado()).rutas.map((r) => ({ ...r, roles: r.roles ? [...r.roles].sort() : null }))
    const clave = (r: { metodo: string; ruta: string }) => `${r.metodo} ${r.ruta}`
    expect(contrato.length).toBeGreaterThan(15)
    expect(mocks.map(clave).sort()).toEqual(contrato.map(clave).sort())
    for (const c of contrato) expect(mocks.find((m) => clave(m) === clave(c))?.roles, clave(c)).toEqual(c.roles)
  })

  it('cada endpoint del contrato responde con su handler (no con 404 RUTA_NO_ENCONTRADA ni 405)', async () => {
    const token = await entrar('admin.demo')
    for (const { metodo, ruta } of contrato) {
      const concreta = ruta.replace('{folio}', 'ONB-2026-000001').replace(/\{\w+\}/g, 'x')
      const r = await api<{ codigo?: string }>(metodo, concreta, { token, cuerpo: metodo === 'GET' ? undefined : {} })
      expect([404, 405].includes(r.status) && ['RUTA_NO_ENCONTRADA', 'METODO_NO_PERMITIDO'].includes(r.cuerpo.codigo ?? ''),
        `${metodo} ${ruta} -> ${r.status} ${r.cuerpo.codigo}`).toBe(false)
    }
  })
})

// ------------------------------------------------------------------ auth y roles

describe('sesion y roles', () => {
  it('login de los tres usuarios con expires_in y GET /auth/yo', async () => {
    for (const usuario of ['admin.demo', 'revisor.demo', 'integrador.demo'] as const) {
      const r = await api<{ access_token: string; rol: string; expires_in: number }>('POST', '/auth/login',
        { cuerpo: { usuario, contrasena: CONTRASENAS[usuario] } })
      expect(r.cuerpo.expires_in).toBe(3600)
      const yo = await api('GET', '/auth/yo', { token: r.cuerpo.access_token })
      expect(yo.cuerpo).toEqual({ usuario, rol: r.cuerpo.rol })
    }
  })

  it('401 con los codigos del catalogo', async () => {
    expect((await api('POST', '/auth/login', { cuerpo: { usuario: 'revisor.demo', contrasena: 'mal' } })).cuerpo.codigo).toBe('CREDENCIALES_INVALIDAS')
    const sinToken = await api('GET', '/auth/yo')
    expect([sinToken.status, sinToken.cuerpo.codigo]).toEqual([401, 'NO_AUTENTICADO'])
    const token = await entrar('revisor.demo')
    t += 3601 * 1000
    const caducado = await api('GET', '/auth/yo', { token })
    expect([caducado.status, caducado.cuerpo.codigo]).toEqual([401, 'TOKEN_CADUCADO'])
  })

  it('403 SIN_PERMISO segun el rol y procesos sin webhook ni modelos para el revisor', async () => {
    const integrador = await entrar('integrador.demo')
    expect((await api('GET', '/auditoria', { token: integrador })).status).toBe(403)
    expect((await api('GET', '/documentos/x/original', { token: integrador })).cuerpo.codigo).toBe('SIN_PERMISO')
    const revisor = await api<Record<string, unknown>[]>('GET', '/procesos', { token: await entrar('revisor.demo') })
    expect(revisor.cuerpo[0]).not.toHaveProperty('webhook_url')
    expect(revisor.cuerpo[0]).not.toHaveProperty('modelos')
    const admin = await api<Record<string, unknown>[]>('GET', '/procesos', { token: await entrar('admin.demo') })
    expect(admin.cuerpo[0]).toHaveProperty('webhook_url')
  })
})

// ------------------------------------------------------------------ consultas

describe('consultas', () => {
  it('GET /folios pagina, ordena del mas reciente al mas antiguo y filtra', async () => {
    const token = await entrar('revisor.demo')
    const p1 = await api<PaginaFolios>('GET', '/folios?tamano_pagina=2', { token })
    expect(p1.cuerpo.total).toBe(4)
    expect(p1.cuerpo.elementos.map((f) => f.folio)).toEqual(['ONB-2026-000003', 'ONB-2026-000002'])
    const aprobados = await api<PaginaFolios>('GET', '/folios?estado_general=aprobado', { token })
    expect(aprobados.cuerpo.elementos.map((f) => f.folio)).toEqual(['ONB-2026-000004'])
    const f1 = (await api<PaginaFolios>('GET', '/folios', { token })).cuerpo.elementos.find((f) => f.folio === 'ONB-2026-000001')
    expect(f1?.n_bloqueantes_sin_resolver).toBe(1)
    expect((await api('GET', '/folios?estado_general=cerrado', { token })).cuerpo.codigo).toBe('PETICION_INVALIDA')
    expect((await api('GET', '/folios?tamano_pagina=101', { token })).status).toBe(422)
  })

  it('404 del catalogo, ruta desconocida y metodo no permitido', async () => {
    const token = await entrar('revisor.demo')
    expect((await api('GET', '/folios/ONB-2026-999999', { token })).cuerpo.codigo).toBe('FOLIO_NO_ENCONTRADO')
    expect((await api('GET', '/documentos/no-existe', { token })).cuerpo.codigo).toBe('DOCUMENTO_NO_ENCONTRADO')
    expect((await api('POST', '/folios/ONB-2026-000001/alertas/no-existe/resolver', { token, cuerpo: { aplica: false } })).cuerpo.codigo)
      .toBe('ALERTA_NO_ENCONTRADA')
    expect((await api('GET', '/no-existe', { token })).cuerpo.codigo).toBe('RUTA_NO_ENCONTRADA')
    const metodo = await api('DELETE', '/folios/ONB-2026-000001', { token })
    expect([metodo.status, metodo.cuerpo.codigo]).toEqual([405, 'METODO_NO_PERMITIDO'])
  })

  it('resumen.md, antecedentes, tipos, auditoria y original', async () => {
    const revisor = await entrar('revisor.demo')
    const resumen = await api('GET', '/folios/ONB-2026-000004/resumen.md', { token: revisor })
    expect(resumen.status).toBe(200)
    expect(resumen.texto).toContain('# Expediente ONB-2026-000004')
    expect((await api('GET', '/folios/ONB-2026-000001/resumen.md', { token: revisor })).cuerpo.codigo).toBe('RESUMEN_NO_DISPONIBLE')
    expect((await api('GET', '/folios/ONB-2026-000001/antecedentes', { token: revisor })).cuerpo).toEqual([])
    expect((await api<unknown[]>('GET', '/tipos-documentales', { token: revisor })).cuerpo).toHaveLength(3)
    const f4 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000004', { token: revisor })).cuerpo
    const pedirUrl = async () => (await api<{ url: string }>('GET',
      `/documentos/${f4.documentos[0].identificador_unico_documento}/original`, { token: revisor })).cuerpo.url
    const url = await pedirUrl()
    expect(url).toMatch(/^http:\/\/localhost:5173\/mock-originales\/pasaporte_sano_digital\.pdf\?firma=\d+$/)
    expect(await pedirUrl()).not.toBe(url) // como la URL prefirmada: una nueva en cada peticion
    const auditoria = await api<PaginaAuditoria>('GET', '/auditoria?folio=ONB-2026-000004', { token: await entrar('admin.demo') })
    const entradas = auditoria.cuerpo.elementos
    expect([auditoria.cuerpo.pagina, auditoria.cuerpo.tamano_pagina, auditoria.cuerpo.total]).toEqual([1, 50, entradas.length])
    expect(entradas.every((e) => e.folio === 'ONB-2026-000004')).toBe(true)
    expect(entradas.map((e) => e.creado_en)).toEqual([...entradas.map((e) => e.creado_en)].sort().reverse())
  })

  it('GET /auditoria segun ADR-008: 50 por defecto, 1 a 100, creado_en desc e id desc, 422 fuera de rango', async () => {
    const token = await entrar('admin.demo')
    await entrar('revisor.demo') // dos logins en el mismo instante: el empate se ordena por id desc
    const todas = (await api<PaginaAuditoria>('GET', '/auditoria?tamano_pagina=100', { token })).cuerpo
    const [primera, segunda] = todas.elementos
    expect([primera.accion, segunda.accion, primera.creado_en === segunda.creado_en, primera.id > segunda.id])
      .toEqual(['login', 'login', true, true])
    const porDefecto = (await api<PaginaAuditoria>('GET', '/auditoria', { token })).cuerpo
    expect([porDefecto.pagina, porDefecto.tamano_pagina, porDefecto.elementos.length]).toEqual([1, 50, Math.min(50, todas.total)])
    const p2 = (await api<PaginaAuditoria>('GET', '/auditoria?pagina=2&tamano_pagina=3', { token })).cuerpo
    expect(p2.total).toBe(todas.total)
    expect(p2.elementos.map((e) => e.id)).toEqual(todas.elementos.slice(3, 6).map((e) => e.id))
    for (const q of ['tamano_pagina=101', 'tamano_pagina=0', 'pagina=0', 'pagina=1.5']) {
      const r = await api('GET', `/auditoria?${q}`, { token })
      expect([r.status, r.cuerpo.codigo], q).toEqual([422, 'PETICION_INVALIDA'])
    }
  })

  it('los cuerpos JSON con campos que sobran dan 422, como la API real', async () => {
    const login = await api('POST', '/auth/login', { cuerpo: { usuario: 'revisor.demo', contrasena: 'demo-revisor', recordar: true } })
    expect([login.status, login.cuerpo.codigo]).toEqual([422, 'PETICION_INVALIDA'])
    const token = await entrar('revisor.demo')
    const folio = await api('POST', '/folios', { token, cuerpo: { proceso: 'onboarding', solicitante: 'X' } })
    expect([folio.status, folio.cuerpo.mensaje]).toEqual([422, 'Peticion no valida en: solicitante (extra_forbidden)'])
    const decision = await api('POST', '/folios/ONB-2026-000001/decision', { token, cuerpo: { decision: 'rechazar', motivo: 'x' } })
    expect(decision.status).toBe(422)
  })
})

// ------------------------------------------------------------------ subida y procesamiento

describe('subida de documentos', () => {
  it('202 pendiente -> procesando -> completado en unos 9 s y EXP-001 se recalcula', async () => {
    const token = await entrar('integrador.demo')
    const creado = await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding', referencia_externa: 'CLI-000900' } })
    expect(creado.status).toBe(201)
    const folio = creado.cuerpo.folio
    expect(folio).toBe('ONB-2026-000005')
    let exp = (await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo
    const exp001 = (e: ResultadoExpediente) => e.alertas_expediente.filter((a) => a.codigo === 'EXP-001').map((a) => a.campo)
    expect(exp001(exp)).toEqual(['credencial_elector', 'comprobante_domicilio']) // campo = tipo que falta

    const r = await api<{ identificador_unico_documento: string; estado_analisis: string }>('POST', `/folios/${folio}/documentos`,
      { token, formulario: subida('credencial_elector_sano_digital.pdf', original('credencial_elector_sano_digital.pdf'), 'credencial_elector') })
    expect([r.status, r.cuerpo.estado_analisis]).toEqual([202, 'pendiente'])
    const id = r.cuerpo.identificador_unico_documento
    const estadoDoc = async () => (await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo
    expect((await estadoDoc()).estado_analisis).toBe('pendiente')
    // EXP-001 solo se recalcula cuando el documento se procesa, no al subirlo
    expect(exp001((await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo)).toHaveLength(2)
    t += MS_HASTA_PROCESANDO
    expect((await estadoDoc()).estado_analisis).toBe('procesando')
    t += MS_HASTA_COMPLETADO - MS_HASTA_PROCESANDO
    const hecho = await estadoDoc()
    expect(hecho.estado_analisis).toBe('completado')
    expect(hecho.datos_extraidos.curp).toBe('AEPA900101MDFXXX01') // mismo fichero que los datos -> mismos valores
    expect(hecho.recomendacion).toBe('aprobar')
    exp = (await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo
    expect(exp001(exp)).toEqual(['comprobante_domicilio'])
    expect(exp.alertas_expediente[0].mensaje).toBe('Falta comprobante_domicilio, requerido por el proceso onboarding')
  })

  it('el mismo archivo en el mismo folio devuelve 202 con DUP-001', async () => {
    const token = await entrar('revisor.demo')
    const r = await api<{ identificador_unico_documento: string; estado_analisis: string }>('POST', '/folios/ONB-2026-000003/documentos',
      { token, formulario: subida('credencial_elector_sano_digital.pdf', original('credencial_elector_sano_digital.pdf')) })
    expect(r.status).toBe(202)
    const doc = (await api<ResultadoDocumento>('GET', `/documentos/${r.cuerpo.identificador_unico_documento}`, { token })).cuerpo
    expect(codigos(doc.alertas_encontradas)).toEqual(['DUP-001'])
  })

  it('413 y 415 del catalogo', async () => {
    const token = await entrar('revisor.demo')
    const grande = await api('POST', '/folios/ONB-2026-000003/documentos', { token, formulario: subida('grande.pdf', new Uint8Array(20 * 1024 * 1024 + 1)) })
    expect([grande.status, grande.cuerpo.codigo]).toEqual([413, 'ARCHIVO_DEMASIADO_GRANDE'])
    const texto = await api('POST', '/folios/ONB-2026-000003/documentos', { token, formulario: subida('notas.txt', new Uint8Array([1]), 'pasaporte') })
    expect([texto.status, texto.cuerpo.codigo]).toEqual([415, 'FORMATO_NO_PERMITIDO'])
  })

  it('415 si el contenido no corresponde a la extension y 422 si el archivo esta vacio', async () => {
    const token = await entrar('revisor.demo')
    const subir = (nombre: string, datos: Uint8Array | Buffer) =>
      api('POST', '/folios/ONB-2026-000003/documentos', { token, formulario: subida(nombre, datos) })
    const jpgComoPdf = await subir('pasaporte_disfrazado.pdf', original('credencial_elector_vencido_foto.jpg'))
    expect([jpgComoPdf.status, jpgComoPdf.cuerpo.mensaje]).toEqual([415, 'El contenido del archivo no corresponde a su extension'])
    expect((await subir('corto.png', new Uint8Array([0x89, 0x50]))).status).toBe(415)
    const vacio = await subir('vacio.pdf', new Uint8Array())
    expect([vacio.status, vacio.cuerpo.codigo]).toEqual([422, 'PETICION_INVALIDA'])
  })

  it('auditoria de la subida sin nombre_archivo, como la API real', async () => {
    const revisor = await entrar('revisor.demo')
    const datos = original('credencial_elector_sano_digital.pdf')
    await api('POST', '/folios/ONB-2026-000003/documentos', { token: revisor, formulario: subida('credencial_elector_sano_digital.pdf', datos) })
    const [entrada] = (await api<PaginaAuditoria>('GET', '/auditoria?folio=ONB-2026-000003', { token: await entrar('admin.demo') })).cuerpo.elementos
    expect(entrada.accion).toBe('documento_subido')
    expect(entrada.detalle).toEqual({ hash_sha256: expect.stringMatching(/^[0-9a-f]{64}$/), tamano_bytes: datos.length, duplicado: true })
  })

  it('el anio del folio es el de la hora de Mexico, no el de UTC', async () => {
    t = Date.UTC(2027, 0, 1, 3, 0, 0) // 31/12/2026 21:00 en Ciudad de Mexico
    const token = await entrar('integrador.demo')
    const creado = await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })
    expect(creado.cuerpo.folio).toBe('ONB-2026-000005')
    const auditoria = (await api<PaginaAuditoria>('GET', `/auditoria?folio=${creado.cuerpo.folio}`, { token: await entrar('admin.demo') })).cuerpo
    expect(auditoria.elementos.map((e) => [e.accion, e.detalle])).toEqual([['folio_creado', {}]])
  })
})

// ------------------------------------------------------------------ acciones del revisor

describe('acciones del revisor', () => {
  it('regla 2.2: aprobar falla mientras quede una bloqueante con aplica distinto de false', async () => {
    const token = await entrar('revisor.demo')
    const f1 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo
    const pasaporte = f1.documentos[0]
    const bloqueante = pasaporte.alertas_encontradas.find((a) => a.severidad === 'bloqueante')!
    const aprobar = () => api('POST', '/folios/ONB-2026-000001/decision', { token, cuerpo: { decision: 'aprobar' } })
    expect((await aprobar()).cuerpo.codigo).toBe('DECISION_BLOQUEADA')
    const ruta = `/documentos/${pasaporte.identificador_unico_documento}/alertas/${bloqueante.id}/resolver`
    await api('POST', ruta, { token, cuerpo: { aplica: true, comentario: 'Confirmado' } })
    expect((await aprobar()).cuerpo.codigo).toBe('DECISION_BLOQUEADA') // aplica=true confirma el problema
    const resuelta = await api<ResultadoDocumento>('POST', ruta, { token, cuerpo: { aplica: false, comentario: 'Falso positivo' } })
    expect(resuelta.cuerpo.alertas_encontradas.find((a) => a.id === bloqueante.id))
      .toMatchObject({ aplica: false, comentario_revisor: 'Falso positivo', resuelta_por: 'revisor.demo', resuelta_por_revisor: true })

    const decision = await api<ResultadoExpediente>('POST', '/folios/ONB-2026-000001/decision', { token, cuerpo: { decision: 'aprobar', comentario: 'Revisado' } })
    expect(decision.cuerpo).toMatchObject({ estado_general: 'aprobado', decision_humana: 'aprobar', comentario_decision: 'Revisado', usuario_decision: 'revisor.demo' })
    expect(decision.cuerpo.fecha_decision).toMatch(/^2026-10-01T10:00:00Z$/)
    // Folio cerrado: cualquier accion devuelve 409 FOLIO_CERRADO
    for (const [metodo, r, cuerpo] of [
      ['POST', '/folios/ONB-2026-000001/decision', { decision: 'rechazar' }],
      ['PATCH', `/documentos/${pasaporte.identificador_unico_documento}/datos`, { sexo: 'F' }],
      ['POST', ruta, { aplica: true }],
    ] as const) {
      const res = await api(metodo, r, { token, cuerpo })
      expect([res.status, res.cuerpo.codigo], r).toEqual([409, 'FOLIO_CERRADO'])
    }
    expect((await api('POST', '/folios/ONB-2026-000001/documentos', { token, formulario: subida('pasaporte_x.pdf', new Uint8Array([1])) })).cuerpo.codigo)
      .toBe('FOLIO_CERRADO')
  })

  it('resolver una alerta de expediente (EXP-001) desbloquea la aprobacion', async () => {
    const token = await entrar('revisor.demo')
    const f3 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000003', { token })).cuerpo
    const exp001 = f3.alertas_expediente[0]
    const r = await api<ResultadoExpediente>('POST', `/folios/ONB-2026-000003/alertas/${exp001.id}/resolver`, { token, cuerpo: { aplica: false } })
    expect(r.cuerpo.alertas_expediente[0]).toMatchObject({ id: exp001.id, aplica: false, resuelta_por_revisor: true })
    const lista = (await api<PaginaFolios>('GET', '/folios', { token })).cuerpo.elementos
    expect(lista.find((f) => f.folio === 'ONB-2026-000003')?.n_bloqueantes_sin_resolver).toBe(0)
    expect((await api('POST', '/folios/ONB-2026-000003/decision', { token, cuerpo: { decision: 'aprobar' } })).status).toBe(200)
  })

  it('documento en error: 409 DOCUMENTO_CON_ERROR al corregir o confirmar; sus alertas si se resuelven', async () => {
    const token = await entrar('revisor.demo')
    const f3 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000003', { token })).cuerpo
    const conError = f3.documentos.find((d) => d.estado_analisis === 'error')!
    const id = conError.identificador_unico_documento
    for (const [r, cuerpo] of [[`/documentos/${id}/datos`, { sexo: 'F' }], [`/documentos/${id}/confirmar-clasificacion`, { tipo_documental: 'pasaporte' }]] as const) {
      const res = await api(r.endsWith('datos') ? 'PATCH' : 'POST', r, { token, cuerpo })
      expect([res.status, res.cuerpo.codigo], r).toEqual([409, 'DOCUMENTO_CON_ERROR'])
    }
    const sys = conError.alertas_encontradas.find((a) => a.codigo === 'SYS-001')!
    const resuelta = await api<ResultadoDocumento>('POST', `/documentos/${id}/alertas/${sys.id}/resolver`, { token, cuerpo: { aplica: true } })
    expect(resuelta.status).toBe(200)
    expect(resuelta.cuerpo.alertas_encontradas[0]).toMatchObject({ aplica: true, resuelta_por_revisor: true })
  })

  it('EXP-001 marcada como falso positivo se conserva al recalcular', async () => {
    const token = await entrar('revisor.demo')
    const f3 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000003', { token })).cuerpo
    const exp001 = f3.alertas_expediente.find((a) => a.codigo === 'EXP-001')!
    expect(exp001.campo).toBe('comprobante_domicilio')
    await api('POST', `/folios/ONB-2026-000003/alertas/${exp001.id}/resolver`, { token, cuerpo: { aplica: false } })
    await api('POST', '/folios/ONB-2026-000003/documentos',
      { token, formulario: subida('comprobante_domicilio_sano_digital.pdf', original('comprobante_domicilio_sano_digital.pdf'), 'comprobante_domicilio') })
    t += MS_HASTA_COMPLETADO
    const despues = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000003', { token })).cuerpo
    expect(despues.alertas_expediente).toEqual([expect.objectContaining({ id: exp001.id, aplica: false })])
  })

  it('EXP-001 usa el tipo efectivo (confirmado > detectado > declarado) al procesar y al confirmar', async () => {
    const token = await entrar('revisor.demo')
    const { folio } = (await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })).cuerpo
    const faltan = async () => (await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo.alertas_expediente
      .filter((a) => a.codigo === 'EXP-001').map((a) => a.campo)
    // Una credencial declarada como comprobante: al procesarse cuenta el detectado (credencial)
    const { identificador_unico_documento: id } = (await api<{ identificador_unico_documento: string }>('POST', `/folios/${folio}/documentos`, {
      token, formulario: subida('credencial_elector_sano_digital.pdf', original('credencial_elector_sano_digital.pdf'), 'comprobante_domicilio'),
    })).cuerpo
    t += MS_HASTA_COMPLETADO
    expect(await faltan()).toEqual(['comprobante_domicilio'])
    const doc = (await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo
    // Extraida con la ficha del declarado: faltan obligatorios (VAL-001) y el opcional proveedor (VAL-004)
    expect(doc.alertas_encontradas.filter((a) => a.codigo === 'VAL-004').map((a) => [a.campo, a.severidad])).toEqual([['proveedor', 'informativa']])
    // El revisor confirma el tipo declarado: ahora cuenta el confirmado
    await api('POST', `/documentos/${id}/confirmar-clasificacion`, { token, cuerpo: { tipo_documental: 'comprobante_domicilio' } })
    expect(await faltan()).toEqual(['credencial_elector'])
  })

  it('documento pendiente: 409 DOCUMENTO_EN_PROCESO en correcciones y decision', async () => {
    const token = await entrar('revisor.demo')
    const f2 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000002', { token })).cuerpo
    const pendiente = f2.documentos.find((d) => d.estado_analisis === 'pendiente')!
    expect((await api('PATCH', `/documentos/${pendiente.identificador_unico_documento}/datos`, { token, cuerpo: { sexo: 'F' } })).cuerpo.codigo)
      .toBe('DOCUMENTO_EN_PROCESO')
    expect((await api('POST', '/folios/ONB-2026-000002/decision', { token, cuerpo: { decision: 'rechazar' } })).cuerpo.codigo)
      .toBe('DOCUMENTO_EN_PROCESO')
  })

  it('corregir un dato guarda la correccion y recalcula CMP-001', async () => {
    const token = await entrar('revisor.demo')
    const f2 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000002', { token })).cuerpo
    expect(codigos(f2.alertas_expediente)).toEqual(['CMP-001'])
    const [credencial, comprobante] = f2.documentos
    const r = await api<ResultadoDocumento>('PATCH', `/documentos/${comprobante.identificador_unico_documento}/datos`,
      { token, cuerpo: { domicilio: credencial.datos_extraidos.domicilio } })
    expect(r.cuerpo.correcciones.at(-1)).toMatchObject({ campo: 'domicilio', valor_anterior: comprobante.datos_extraidos.domicilio, usuario: 'revisor.demo' })
    expect([r.cuerpo.nivel_confianza_por_campo.domicilio, r.cuerpo.evidencia_por_campo.domicilio]).toEqual([1, 'correccion_revisor'])
    const despues = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000002', { token })).cuerpo
    expect(despues.alertas_expediente).toEqual([])
    expect((await api('PATCH', `/documentos/${credencial.identificador_unico_documento}/datos`, { token, cuerpo: { inventado: 1 } })).status).toBe(422)
  })

  it('confirmar clasificacion: el mismo tipo resuelve CLS-001; otro tipo reprocesa', async () => {
    const token = await entrar('revisor.demo')
    const { folio } = (await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })).cuerpo
    const subir = async () => (await api<{ identificador_unico_documento: string }>('POST', `/folios/${folio}/documentos`, {
      token, formulario: subida('credencial_elector_sano_digital.pdf', original('credencial_elector_sano_digital.pdf'), 'pasaporte'),
    })).cuerpo.identificador_unico_documento
    const doc = async (id: string) => (await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo

    const a = await subir()
    t += MS_HASTA_COMPLETADO
    const extraido = await doc(a)
    expect(extraido.tipo_documental_detectado).toBe('credencial_elector')
    expect(codigos(extraido.alertas_encontradas)).toContain('CLS-001')
    const mismo = await api<ResultadoDocumento>('POST', `/documentos/${a}/confirmar-clasificacion`, { token, cuerpo: { tipo_documental: 'pasaporte' } })
    expect(mismo.cuerpo.tipo_documental_confirmado).toBe('pasaporte')
    expect(mismo.cuerpo.alertas_encontradas.find((x) => x.codigo === 'CLS-001')).toMatchObject({ aplica: false, resuelta_por_revisor: true })

    const b = await subir() // mismo SHA-256: DUP-001, pero sirve para el segundo camino
    t += MS_HASTA_COMPLETADO
    await doc(b)
    const otro = await api<ResultadoDocumento>('POST', `/documentos/${b}/confirmar-clasificacion`, { token, cuerpo: { tipo_documental: 'credencial_elector' } })
    expect([otro.cuerpo.estado_analisis, otro.cuerpo.tipo_documental_confirmado]).toEqual(['pendiente', 'credencial_elector'])
    expect(estado.versionesPrevias.get(b)).toHaveLength(1)
    t += MS_HASTA_COMPLETADO
    const reprocesado = await doc(b)
    expect(reprocesado.estado_analisis).toBe('completado')
    expect(reprocesado.datos_extraidos.curp).toBe('AEPA900101MDFXXX01')
    expect(reprocesado.alertas_encontradas.find((x) => x.codigo === 'CLS-001')).toMatchObject({ aplica: true })
    expect(codigos(reprocesado.alertas_encontradas)).not.toContain('VAL-001')
  })
})

// ------------------------------------------------------------------ campos sin valor

describe('campos sin valor', () => {
  it('PATCH de datos con "" o solo espacios deja el campo en null, nunca en ""', async () => {
    const token = await entrar('revisor.demo')
    const f1 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo
    const pasaporte = f1.documentos[0]
    const r = await api<ResultadoDocumento>('PATCH', `/documentos/${pasaporte.identificador_unico_documento}/datos`,
      { token, cuerpo: { sexo: '   ', nacionalidad: '' } })
    expect(r.status).toBe(200)
    expect([r.cuerpo.datos_extraidos.sexo, r.cuerpo.datos_extraidos.nacionalidad]).toEqual([null, null])
    expect(r.cuerpo.correcciones.slice(-2).map((c) => [c.campo, c.valor_nuevo])).toEqual([['sexo', null], ['nacionalidad', null]])
  })

  it('los datos iniciales no tienen "" ni solo espacios, y VAL-004 va en un campo opcional null', async () => {
    const token = await entrar('revisor.demo')
    const folios = await Promise.all(['ONB-2026-000001', 'ONB-2026-000002', 'ONB-2026-000003', 'ONB-2026-000004']
      .map(async (f) => (await api<ResultadoExpediente>('GET', `/folios/${f}`, { token })).cuerpo))
    const documentos = folios.flatMap((f) => f.documentos)
    const valores = documentos.flatMap((d) => Object.values(d.datos_extraidos))
    expect(valores.filter((v) => typeof v === 'string' && !v.trim())).toEqual([])
    const val004 = documentos.flatMap((d) => d.alertas_encontradas.filter((a) => a.codigo === 'VAL-004').map((a) => [d, a] as const))
    expect(val004.length).toBeGreaterThan(0)
    for (const [d, a] of val004) expect([a.severidad, d.datos_extraidos[a.campo!]]).toEqual(['informativa', null])
    // Tres informativas, todas posibles con la configuracion por defecto (sin SYS-005: ADR-003)
    const informativas = documentos.flatMap((d) => d.alertas_encontradas).filter((a) => a.severidad === 'informativa')
    expect(informativas.map((a) => [a.codigo, a.campo]).sort()).toEqual([['VAL-003', 'nacionalidad'], ['VAL-003', 'sexo'], ['VAL-004', 'proveedor']])
  })
})

describe('modelos de los analisis (configuracion de PERSONA_2)', () => {
  it('siempre Ollama: gemma4:e2b para PDF digitales y qwen2.5vl:3b para escaneados e imagenes; nunca SYS-005', async () => {
    const token = await entrar('revisor.demo')
    const folios = await Promise.all(['ONB-2026-000001', 'ONB-2026-000002', 'ONB-2026-000003', 'ONB-2026-000004']
      .map(async (f) => (await api<ResultadoExpediente>('GET', `/folios/${f}`, { token })).cuerpo))
    for (const d of folios.flatMap((f) => f.documentos).filter((x) => x.fecha_y_modelo_utilizado)) {
      const nombre = d.referencia_archivo_original.nombre_archivo
      expect([d.fecha_y_modelo_utilizado!.proveedor, d.fecha_y_modelo_utilizado!.modelo], nombre)
        .toEqual(['ollama', nombre.includes('_digital.') ? 'gemma4:e2b' : 'qwen2.5vl:3b'])
      expect(codigos(d.alertas_encontradas)).not.toContain('SYS-005')
    }
    const procesados = estado.auditoria.filter((e) => e.accion === 'documento_procesado')
    expect(new Set(procesados.map((e) => e.modelo))).toEqual(new Set(['gemma4:e2b', 'qwen2.5vl:3b']))
  })

  it('un documento subido usa el modelo del original con el mismo SHA-256 o, si no hay, el de su extension', async () => {
    const token = await entrar('revisor.demo')
    const { folio } = (await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })).cuerpo
    const subir = async (nombre: string, datos: Uint8Array | Buffer) => (await api<{ identificador_unico_documento: string }>(
      'POST', `/folios/${folio}/documentos`, { token, formulario: subida(nombre, datos) })).cuerpo.identificador_unico_documento
    const digital = await subir('credencial_elector_sano_digital.pdf', original('credencial_elector_sano_digital.pdf'))
    const foto = await subir('credencial_elector_vencido_foto.jpg', original('credencial_elector_vencido_foto.jpg'))
    t += MS_HASTA_COMPLETADO
    const modelo = async (id: string) => (await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo.fecha_y_modelo_utilizado?.modelo
    expect([await modelo(digital), await modelo(foto)]).toEqual(['gemma4:e2b', 'qwen2.5vl:3b'])
  })
})
