// Tests de los mocks con msw/node. Datos ficticios; usuarios de src/mocks/usuarios.ts.
import { existsSync, readFileSync } from 'node:fs'
import { setupServer } from 'msw/node'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import {
  ROLES, type Alerta, type PaginaAuditoria, type PaginaFolios, type ResultadoDocumento, type ResultadoExpediente,
} from '../tipos/contrato'
import { crearEstado, type EstadoMock } from './estado'
import { crearHandlers } from './handlers'
import { compararCampos, enmascararDocumento, mascara, MS_HASTA_COMPLETADO, MS_HASTA_PROCESANDO } from './logica'

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

  it('el token sigue valido tras reiniciar msw (recargar la pagina), como un JWT', async () => {
    const token = await entrar('admin.demo')
    // Reinicio: estado nuevo y handlers nuevos, sin memoria de lo emitido
    estado = crearEstado(() => t)
    servidor.resetHandlers(...crearHandlers(estado).handlers)
    const yo = await api('GET', '/auth/yo', { token })
    expect([yo.status, yo.cuerpo]).toEqual([200, { usuario: 'admin.demo', rol: 'admin' }])
    expect((await api('GET', '/auditoria', { token })).status).toBe(200)
    // La caducidad viaja en el token: tambien tras el reinicio
    t += 3601 * 1000
    expect((await api('GET', '/auth/yo', { token })).cuerpo.codigo).toBe('TOKEN_CADUCADO')
  })

  it('un token retocado o inventado no vale (NO_AUTENTICADO)', async () => {
    const token = await entrar('revisor.demo')
    const [prefijo, carga, firma] = token.split('.')
    const otraCarga = btoa(JSON.stringify({ u: 'admin.demo', exp: t + 3600 * 1000, iat: t }))
      .replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
    const falsos = [
      `${prefijo}.${otraCarga}.${firma}`, // otro usuario con la firma del revisor
      `${prefijo}.${carga}.00000000`, // firma cambiada
      `${prefijo}.${carga}`, // sin firma
      `otro.${carga}.${firma}`, // otro prefijo
      'mock.revisor.demo.1', // formato antiguo, basado en la memoria del mock
      'TU_TOKEN_AQUI',
    ]
    for (const falso of falsos) {
      const r = await api('GET', '/auth/yo', { token: falso })
      expect([falso, r.status, r.cuerpo.codigo]).toEqual([falso, 401, 'NO_AUTENTICADO'])
    }
    expect((await api('GET', '/auth/yo', { token })).status).toBe(200)
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

describe('el integrador solo ve sus folios (ADR-012)', () => {
  it('los suyos si; los de otro integrador dan el mismo 404 que uno inexistente', async () => {
    const token = await entrar('integrador.demo')
    expect((await api('GET', '/folios/ONB-2026-000002', { token })).status).toBe(200)
    const ajeno = await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000003', { token })
    const inexistente = await api('GET', '/folios/ONB-2026-999999', { token })
    expect([ajeno.status, ajeno.cuerpo]).toEqual([404, { codigo: 'FOLIO_NO_ENCONTRADO', mensaje: 'No existe el folio ONB-2026-000003' }])
    expect(inexistente.cuerpo).toMatchObject({ codigo: 'FOLIO_NO_ENCONTRADO' })
    expect((await api('GET', '/folios/ONB-2026-000004/resumen.md', { token })).cuerpo).toMatchObject({ codigo: 'FOLIO_NO_ENCONTRADO' })
    const subida = new FormData()
    subida.append('archivo', new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], 'a.pdf'))
    expect((await api('POST', '/folios/ONB-2026-000003/documentos', { token, formulario: subida })).cuerpo)
      .toMatchObject({ codigo: 'FOLIO_NO_ENCONTRADO' })
    const docAjeno = estado.folios.get('ONB-2026-000003')!.documentos[0].identificador_unico_documento
    expect((await api('GET', `/documentos/${docAjeno}`, { token })).cuerpo).toMatchObject({ codigo: 'DOCUMENTO_NO_ENCONTRADO' })
    const docPropio = estado.folios.get('ONB-2026-000002')!.documentos[0].identificador_unico_documento
    expect((await api('GET', `/documentos/${docPropio}`, { token })).status).toBe(200)
  })

  it('un folio que crea en la sesion es suyo; revisor y admin ven todos', async () => {
    const token = await entrar('integrador.demo')
    const creado = await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })
    expect((await api('GET', `/folios/${creado.cuerpo.folio}`, { token })).status).toBe(200)
    for (const usuario of ['revisor.demo', 'admin.demo'] as const) {
      const otro = await entrar(usuario)
      for (const folio of ['ONB-2026-000003', creado.cuerpo.folio]) expect((await api('GET', `/folios/${folio}`, { token: otro })).status).toBe(200)
    }
  })
})

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
    expect((await api('GET', '/folios/ONB-2026-000001/antecedentes', { token: revisor })).cuerpo)
      .toEqual({ permitido: true, motivo: null, elementos: [] })
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
    // Mismo fichero que los datos -> mismos valores; la curp sale enmascarada (ADR-010)
    expect(hecho.datos_extraidos.curp).toBe('****XX01')
    expect(hecho.recomendacion).toBe('aprobar')
    exp = (await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo
    expect(exp001(exp)).toEqual(['comprobante_domicilio'])
    expect(exp.alertas_expediente[0].mensaje).toBe('Falta el documento requerido: Comprobante de domicilio') // como la API
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

  it('corregir un dato recalcula la recomendacion del documento, como la API (D3)', async () => {
    const token = await entrar('revisor.demo')
    const f2 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000002', { token })).cuerpo
    const id = f2.documentos[0].identificador_unico_documento // credencial, sin criticas ni bloqueantes
    const enEstado = estado.folios.get('ONB-2026-000002')!.documentos[0]
    enEstado.nivel_confianza_por_campo.nombre_completo = 0.5 // por debajo del minimo de la ficha
    enEstado.recomendacion = 'revision_manual'
    const r = await api<ResultadoDocumento>('PATCH', `/documentos/${id}/datos`, { token, cuerpo: { nombre_completo: 'Ana Ejemplo' } })
    expect(r.cuerpo.recomendacion).toBe('aprobar')
    expect((await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo.recomendacion).toBe('aprobar')
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
    const antes = await doc(b)
    const otro = await api<ResultadoDocumento>('POST', `/documentos/${b}/confirmar-clasificacion`, { token, cuerpo: { tipo_documental: 'credencial_elector' } })
    expect([otro.cuerpo.estado_analisis, otro.cuerpo.tipo_documental_confirmado]).toEqual(['pendiente', 'credencial_elector'])
    expect(estado.versionesPrevias.get(b)).toHaveLength(1)
    // Como la API: CLS-001 no se toca y, mientras esta pendiente, se ve la version anterior
    expect(otro.cuerpo.alertas_encontradas.find((x) => x.codigo === 'CLS-001')).toMatchObject({ aplica: null })
    expect(otro.cuerpo.datos_extraidos).toEqual(antes.datos_extraidos)
    t += MS_HASTA_COMPLETADO
    const reprocesado = await doc(b)
    expect(reprocesado.estado_analisis).toBe('completado')
    expect(reprocesado.datos_extraidos.curp).toBe('****XX01') // enmascarada (ADR-010)
    // Version nueva: las alertas del motor de la anterior (CLS-001 incluida) ya no se ven; DUP-001 (plataforma), si
    expect(codigos(reprocesado.alertas_encontradas)).not.toContain('CLS-001')
    expect(codigos(reprocesado.alertas_encontradas)).toContain('DUP-001')
    expect(codigos(reprocesado.alertas_encontradas)).not.toContain('VAL-001')
    expect(reprocesado.correcciones).toEqual([])
    const auditoria = estado.auditoria.filter((e) => e.accion === 'clasificacion_confirmada').map((e) => e.detalle)
    expect(auditoria).toEqual([{ tipo: 'pasaporte', reproceso: false }, { tipo: 'credencial_elector', reproceso: true }])
  })
})

// ------------------------------------------------------------------ reglas de la API del PR #9

describe('alineado con la API del PR #9', () => {
  const folio = async (token: string, id: string) => (await api<ResultadoExpediente>('GET', `/folios/${id}`, { token })).cuerpo
  const lista = async (token: string) => (await api<PaginaFolios>('GET', '/folios', { token })).cuerpo.elementos

  it('recomendacion global: revision_manual en un folio vacio y con un documento sin completar; no usa la del documento', async () => {
    const token = await entrar('revisor.demo')
    const { folio: nuevo } = (await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })).cuerpo
    expect((await folio(token, nuevo)).recomendacion_global).toBe('revision_manual') // antes, null
    expect((await lista(token)).find((f) => f.folio === nuevo)?.recomendacion_global).toBe('revision_manual')
    expect((await folio(token, 'ONB-2026-000002')).recomendacion_global).toBe('revision_manual') // tiene un pendiente
    expect((await folio(token, 'ONB-2026-000004')).recomendacion_global).toBe('aprobar')

    // La del documento la da el analisis y, como la API (D3), se recalcula al corregir: corregir el unico campo
    // con confianza baja quita su VAL-002 y la deja en aprobar. La global sigue sin usarla
    const credencial = (await folio(token, 'ONB-2026-000001')).documentos[1]
    expect([credencial.recomendacion, credencial.nivel_confianza_por_campo.clave_elector]).toEqual(['revision_manual', 0.62])
    const r = await api<ResultadoDocumento>('PATCH', `/documentos/${credencial.identificador_unico_documento}/datos`,
      { token, cuerpo: { clave_elector: 'EJPRLU85061599H102' } })
    expect([r.status, r.cuerpo.nivel_confianza_por_campo.clave_elector, r.cuerpo.recomendacion]).toEqual([200, 1, 'aprobar'])
    expect(codigos(r.cuerpo.alertas_encontradas)).not.toContain('VAL-002')
    expect((await folio(token, 'ONB-2026-000001')).recomendacion_global).toBe('revision_manual')
  })

  it.each([
    [false, 'se conserva el falso positivo'],
    [true, 'se borra la confirmada'],
  ])('CMP-001 al volver a coincidir con aplica=%s: %s', async (aplica, _caso) => {
    const token = await entrar('revisor.demo')
    const f2 = await folio(token, 'ONB-2026-000002')
    const [credencial, comprobante] = f2.documentos
    const [cmp] = f2.alertas_expediente
    expect([cmp.codigo, cmp.mensaje]).toEqual(['CMP-001', 'Los documentos no coinciden en domicilio']) // nunca los valores
    await api('POST', `/folios/ONB-2026-000002/alertas/${cmp.id}/resolver`, { token, cuerpo: { aplica } })
    await api('PATCH', `/documentos/${comprobante.identificador_unico_documento}/datos`,
      { token, cuerpo: { domicilio: credencial.datos_extraidos.domicilio } })
    const despues = await folio(token, 'ONB-2026-000002')
    expect(despues.comparaciones.find((c) => c.campo === 'domicilio')?.coincide).toBe(true)
    expect(despues.alertas_expediente).toEqual(aplica === false ? [expect.objectContaining({ id: cmp.id, aplica: false })] : [])
  })

  it('comparaciones como validacion.comparar: fechas en varios formatos y sin valores vacios', () => {
    const doc = (id: string, tipo: string, datos: Record<string, unknown>) => ({
      identificador_unico_documento: id, tipo_documental_declarado: tipo, tipo_documental_detectado: tipo,
      tipo_documental_confirmado: null, estado_analisis: 'completado', datos_extraidos: datos,
    }) as unknown as ResultadoDocumento
    const docs = [
      doc('cred', 'credencial_elector', { nombre_completo: 'Ana  Ejemplo Prueba', fecha_nacimiento: '1990-01-01', domicilio: null }),
      doc('pas', 'pasaporte', { nombre_completo: 'ANA EJEMPLO PRUEBA', fecha_nacimiento: '01/01/1990' }),
      doc('comp', 'comprobante_domicilio', { domicilio: 'Calle Ficticia 123' }),
    ]
    const comparaciones = compararCampos(estado, docs)
    expect(comparaciones.map((c) => [c.campo, c.coincide, Object.keys(c.valores)])).toEqual([
      // domicilio: la credencial no tiene valor, asi que el comprobante se queda solo y no se compara
      ['fecha_nacimiento', true, ['cred', 'pas']], // misma fecha en dos formatos
      ['nombre_completo', true, ['cred', 'pas']], // mayusculas y espacios normalizados
    ])
    expect(compararCampos(estado, [docs[0], { ...docs[1], estado_analisis: 'pendiente' } as ResultadoDocumento])).toEqual([])
  })

  it('las bloqueantes del listado son las de la version vigente: tras reprocesar desaparece la del analisis anterior', async () => {
    const token = await entrar('revisor.demo')
    const bloqueantes = async () => (await lista(token)).find((f) => f.folio === 'ONB-2026-000001')!.n_bloqueantes_sin_resolver
    const pasaporte = (await folio(token, 'ONB-2026-000001')).documentos[0]
    const reg = pasaporte.alertas_encontradas.find((a) => a.codigo === 'REG-vigencia_documento')!
    await api('POST', `/documentos/${pasaporte.identificador_unico_documento}/alertas/${reg.id}/resolver`, { token, cuerpo: { aplica: true } })
    expect(await bloqueantes()).toBe(1) // confirmada: sigue impidiendo aprobar
    await api('POST', `/documentos/${pasaporte.identificador_unico_documento}/confirmar-clasificacion`,
      { token, cuerpo: { tipo_documental: 'credencial_elector' } })
    expect(await bloqueantes()).toBe(1) // pendiente: se sigue viendo la version anterior
    t += MS_HASTA_COMPLETADO
    expect(await bloqueantes()).toBe(0) // version nueva: la REG de la anterior ya no se ve
    const decision = (await folio(token, 'ONB-2026-000001')).documentos[0].alertas_encontradas.map((a) => a.codigo)
    expect(decision).not.toContain('REG-vigencia_documento')
  })

  it('documento en error por fallo de S3 o del motor: sin SYS-00x, sin datos y sin documento_procesado', async () => {
    const token = await entrar('revisor.demo')
    const f3 = await folio(token, 'ONB-2026-000003')
    const errores = f3.documentos.filter((d) => d.estado_analisis === 'error')
    expect(errores.map((d) => codigos(d.alertas_encontradas))).toEqual([['SYS-001'], []])
    const sinCodigo = errores[1]
    expect([sinCodigo.tipo_documental_detectado, sinCodigo.datos_extraidos, sinCodigo.fecha_y_modelo_utilizado, sinCodigo.recomendacion])
      .toEqual([null, {}, null, null])
    const acciones = estado.auditoria.filter((e) => e.documento_id === sinCodigo.identificador_unico_documento).map((e) => e.accion)
    expect(acciones).toEqual(['documento_subido'])
    expect(codigos(f3.alertas_expediente)).toEqual(['EXP-001']) // un documento en error no cubre su tipo
    expect((await api('PATCH', `/documentos/${sinCodigo.identificador_unico_documento}/datos`, { token, cuerpo: { domicilio: 'x' } }))
      .cuerpo.codigo).toBe('DOCUMENTO_CON_ERROR')
  })

  it('detalle de la auditoria con la forma de la API', async () => {
    const token = await entrar('revisor.demo')
    const porAccion = (accion: string) => estado.auditoria.filter((e) => e.accion === accion).map((e) => e.detalle)
    expect(porAccion('documento_procesado').every((d) => JSON.stringify(d) === '{"proveedor":"ollama","respaldo_usado":false}')).toBe(true)
    expect(porAccion('dato_corregido')).toEqual([{ campos: ['nombre_completo'] }])
    const f1 = await folio(token, 'ONB-2026-000001')
    const alerta = f1.documentos[0].alertas_encontradas[0]
    await api('POST', `/documentos/${f1.documentos[0].identificador_unico_documento}/alertas/${alerta.id}/resolver`, { token, cuerpo: { aplica: false } })
    expect(porAccion('alerta_resuelta').at(-1)).toEqual({ alerta_id: alerta.id, codigo: alerta.codigo, aplica: false })
  })
})

// ------------------------------------------------------------------ EXP-002 (definida por PERSONA_1 en el PR #9)

describe('EXP-002: documento de un tipo que el proceso no pide', () => {
  // Con config/procesos.yaml los tres tipos estan previstos (pasaporte es opcional): para provocarla, el
  // pasaporte deja de ser opcional en el estado del mock
  const sinPasaporteOpcional = () => { estado.procesos.find((p) => p.nombre === 'onboarding')!.tipos_opcionales = [] }
  const exp002 = (d: ResultadoDocumento) => d.alertas_encontradas.filter((a) => a.codigo === 'EXP-002')

  async function preparar() {
    sinPasaporteOpcional()
    const token = await entrar('revisor.demo')
    const { folio } = (await api<{ folio: string }>('POST', '/folios', { token, cuerpo: { proceso: 'onboarding' } })).cuerpo
    const subir = async (nombre: string, tipo: string) => (await api<{ identificador_unico_documento: string }>(
      'POST', `/folios/${folio}/documentos`, { token, formulario: subida(nombre, original(nombre), tipo) })).cuerpo.identificador_unico_documento
    const doc = async (id: string) => (await api<ResultadoDocumento>('GET', `/documentos/${id}`, { token })).cuerpo
    const expediente = async () => (await api<ResultadoExpediente>('GET', `/folios/${folio}`, { token })).cuerpo
    /** Confirma el tipo y, si reprocesa, espera a que termine */
    const confirmar = async (id: string, tipo: string) => {
      const antes = exp002(await doc(id))
      const r = await api<ResultadoDocumento>('POST', `/documentos/${id}/confirmar-clasificacion`, { token, cuerpo: { tipo_documental: tipo } })
      expect(r.status).toBe(200)
      if (r.cuerpo.estado_analisis === 'pendiente') {
        // Mientras no esta completado no se toca: conserva las EXP-002 que tuviera (son de plataforma)
        expect(exp002(r.cuerpo)).toEqual(antes)
        t += MS_HASTA_COMPLETADO
      }
      return doc(id)
    }
    return { token, folio, subir, doc, expediente, confirmar }
  }

  it('aparece al confirmar un tipo no previsto, en el documento y no en el expediente, y desaparece al confirmar uno previsto', async () => {
    const { subir, doc, expediente, confirmar } = await preparar()
    const id = await subir('credencial_elector_sano_digital.pdf', 'credencial_elector')
    t += MS_HASTA_COMPLETADO
    expect(exp002(await doc(id))).toEqual([]) // credencial: requerida

    const pasaporte = await confirmar(id, 'pasaporte')
    expect(pasaporte.estado_analisis).toBe('completado')
    expect(exp002(pasaporte)).toEqual([expect.objectContaining({
      codigo: 'EXP-002', severidad: 'informativa', campo: 'pasaporte', aplica: null,
      mensaje: 'Tipo de documento no previsto en el proceso: Pasaporte',
    })])
    expect(codigos((await expediente()).alertas_expediente)).not.toContain('EXP-002')

    const credencial = await confirmar(id, 'credencial_elector')
    expect(exp002(credencial)).toEqual([])
  })

  it.each([
    [false, 'se conserva el falso positivo'],
    [true, 'se borra la confirmada'],
  ])('al pasar a un tipo previsto con aplica=%s: %s', async (aplica, _caso) => {
    const { token, subir, confirmar } = await preparar()
    const id = await subir('credencial_elector_sano_digital.pdf', 'credencial_elector')
    t += MS_HASTA_COMPLETADO
    const [alerta] = exp002(await confirmar(id, 'pasaporte'))
    const resuelta = await api<ResultadoDocumento>('POST', `/documentos/${id}/alertas/${alerta.id}/resolver`, { token, cuerpo: { aplica } })
    expect(resuelta.status).toBe(200)

    const despues = exp002(await confirmar(id, 'credencial_elector'))
    expect(despues).toEqual(aplica === false ? [expect.objectContaining({ id: alerta.id, aplica: false, campo: 'pasaporte' })] : [])
  })

  it('no bloquea la aprobacion ni cambia la recomendacion (es informativa)', async () => {
    const { token, folio, subir, doc, expediente } = await preparar()
    await subir('credencial_elector_sano_digital.pdf', 'credencial_elector')
    await subir('comprobante_domicilio_sano_digital.pdf', 'comprobante_domicilio')
    const idPasaporte = await subir('pasaporte_sano_digital.pdf', 'pasaporte')
    t += MS_HASTA_COMPLETADO
    const pasaporte = await doc(idPasaporte)
    expect(exp002(pasaporte)).toHaveLength(1)
    const antes = await expediente()
    expect(antes.alertas_expediente).toEqual([]) // ni EXP-001 ni CMP-001: el resto del folio esta sano
    expect(antes.documentos.every((d) => d.recomendacion === 'aprobar')).toBe(true)
    expect(antes.recomendacion_global).toBe('aprobar')
    const decision = await api<ResultadoExpediente>('POST', `/folios/${folio}/decision`, { token, cuerpo: { decision: 'aprobar' } })
    expect([decision.status, decision.cuerpo.estado_general]).toEqual([200, 'aprobado'])
  })
})

// ------------------------------------------------------------------ campos sin valor

describe('campos sin valor', () => {
  it('PATCH de datos: un campo opcional se vacia con null; "" o solo espacios dan 422 (como la API), nunca se guarda ""', async () => {
    const token = await entrar('revisor.demo')
    const f1 = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo
    const pasaporte = f1.documentos[0]
    const ruta = `/documentos/${pasaporte.identificador_unico_documento}/datos`
    for (const vacio of ['', '   ']) {
      const r = await api('PATCH', ruta, { token, cuerpo: { nacionalidad: vacio } })
      expect([r.status, r.cuerpo.mensaje]).toEqual([422, 'valor no valido para el campo nacionalidad'])
    }
    const r = await api<ResultadoDocumento>('PATCH', ruta, { token, cuerpo: { sexo: null, nacionalidad: null } })
    expect(r.status).toBe(200)
    expect([r.cuerpo.datos_extraidos.sexo, r.cuerpo.datos_extraidos.nacionalidad]).toEqual([null, null])
    expect(r.cuerpo.correcciones.slice(-2).map((c) => [c.campo, c.valor_nuevo])).toEqual([['sexo', null], ['nacionalidad', null]])
    // Una entrada de auditoria por PATCH, con los campos ordenados
    expect(estado.auditoria.filter((e) => e.accion === 'dato_corregido').at(-1)?.detalle).toEqual({ campos: ['nacionalidad', 'sexo'] })
  })

  it('PATCH de datos como la API: campo desconocido, fecha AAAA-MM-DD, patron y solo texto', async () => {
    const token = await entrar('revisor.demo')
    const pasaporte = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo.documentos[0]
    const ruta = `/documentos/${pasaporte.identificador_unico_documento}/datos`
    const patch = (cuerpo: Record<string, unknown>) => api<ResultadoDocumento & { codigo?: string; mensaje?: string }>('PATCH', ruta, { token, cuerpo })
    expect((await patch({ curp: 'X' })).cuerpo).toMatchObject({ codigo: 'PETICION_INVALIDA', mensaje: 'campo desconocido: curp' })
    for (const [cuerpo, campo] of [
      [{ fecha_nacimiento: '01/01/1985' }, 'fecha_nacimiento'], [{ fecha_nacimiento: '1985-02-30' }, 'fecha_nacimiento'],
      [{ numero_pasaporte: 'zx-1' }, 'numero_pasaporte'], [{ sexo: 1 }, 'sexo'], [{ nacionalidad: ['UTOPICA'] }, 'nacionalidad'],
    ] as const) {
      expect((await patch(cuerpo)).cuerpo.mensaje).toBe(`valor no valido para el campo ${campo}`)
    }
    const bien = await patch({ fecha_nacimiento: '1985-6-15', numero_pasaporte: 'ZX0000002' })
    expect([bien.status, bien.cuerpo.datos_extraidos.fecha_nacimiento]).toEqual([200, '1985-6-15']) // strptime admite 1 cifra
  })

  it('PATCH de datos: null en un obligatorio da 422 y no cambia nada (tampoco los otros campos del cuerpo)', async () => {
    const token = await entrar('revisor.demo')
    const pasaporte = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo.documentos[0]
    const ruta = `/documentos/${pasaporte.identificador_unico_documento}/datos`
    for (const vacio of [null, '', '   ']) {
      const r = await api('PATCH', ruta, { token, cuerpo: { nombre_completo: vacio, sexo: 'F' } })
      expect([r.status, r.cuerpo.codigo]).toEqual([422, 'PETICION_INVALIDA'])
      expect(String(r.cuerpo.mensaje)).toContain('nombre_completo')
    }
    const despues = (await api<ResultadoDocumento>('GET', `/documentos/${pasaporte.identificador_unico_documento}`, { token })).cuerpo
    expect([despues.datos_extraidos.nombre_completo, despues.datos_extraidos.sexo]).toEqual(
      [pasaporte.datos_extraidos.nombre_completo, pasaporte.datos_extraidos.sexo])
    expect(despues.correcciones).toEqual(pasaporte.correcciones)
    // null en un opcional se acepta
    const opcional = await api<ResultadoDocumento>('PATCH', ruta, { token, cuerpo: { nacionalidad: null } })
    expect([opcional.status, opcional.cuerpo.datos_extraidos.nacionalidad]).toEqual([200, null])
  })

  it('PATCH de datos: anio como entero de 4 cifras o "AAAA" se guarda como entero; otro formato, 422', async () => {
    const token = await entrar('revisor.demo')
    const credencial = (await api<ResultadoExpediente>('GET', '/folios/ONB-2026-000001', { token })).cuerpo.documentos[1]
    const ruta = `/documentos/${credencial.identificador_unico_documento}/datos`
    // Como _valor_corregido de la API: "0999" pasa (y se guarda 999); los espacios no se recortan
    for (const [enviado, guardado] of [[2030, 2030], ['2031', 2031], ['0999', 999], ['2032', 2032]] as const) {
      const r = await api<ResultadoDocumento>('PATCH', ruta, { token, cuerpo: { vigencia: enviado } })
      expect([JSON.stringify(enviado), r.status, r.cuerpo.datos_extraidos?.vigencia]).toEqual([JSON.stringify(enviado), 200, guardado])
    }
    for (const malo of [30, 999, 20300, 2030.5, '30', ' 2032 ', '20a9', 'AAAA', true, [2030], null]) {
      const r = await api('PATCH', ruta, { token, cuerpo: { vigencia: malo } }) // vigencia es obligatoria: null tambien da 422
      expect([JSON.stringify(malo), r.status, r.cuerpo.mensaje]).toEqual([JSON.stringify(malo), 422, 'valor no valido para el campo vigencia'])
    }
    const despues = (await api<ResultadoDocumento>('GET', `/documentos/${credencial.identificador_unico_documento}`, { token })).cuerpo
    expect(despues.datos_extraidos.vigencia).toBe(2032)
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
    // Cuatro informativas, todas posibles con la configuracion por defecto (sin SYS-005: ADR-003); la EXP-002
    // es la del documento no reconocido de ONB-2026-000003 (ADR-009)
    const informativas = documentos.flatMap((d) => d.alertas_encontradas).filter((a) => a.severidad === 'informativa')
    expect(informativas.map((a) => [a.codigo, a.campo]).sort()).toEqual([
      ['EXP-002', 'desconocido'], ['VAL-003', 'nacionalidad'], ['VAL-003', 'sexo'], ['VAL-004', 'proveedor']])
  })
})

describe('antecedentes (ADR-010 C, H16)', () => {
  it('folio 2: el folio 4 cerrado de la misma referencia, con su fragmento; folio 3 sin referencia', async () => {
    const revisor = await entrar('revisor.demo')
    const r = await api<{ permitido: boolean; motivo: string | null; elementos: Record<string, unknown>[] }>(
      'GET', '/folios/ONB-2026-000002/antecedentes', { token: revisor })
    expect([r.status, r.cuerpo.permitido, r.cuerpo.motivo]).toEqual([200, true, null])
    expect(r.cuerpo.elementos.map((e) => e.folio)).toEqual(['ONB-2026-000004'])
    expect(r.cuerpo.elementos[0]).toMatchObject({ estado_general: 'aprobado', decision_humana: 'aprobar' })
    expect(Object.keys(r.cuerpo.elementos[0]).sort()).toEqual(
      ['decision_humana', 'estado_general', 'fecha_decision', 'fecha_solicitud', 'folio', 'fragmento_resumen'])
    expect(String(r.cuerpo.elementos[0].fragmento_resumen)).toContain('Expediente ONB-2026-000004')
    const sinReferencia = await api('GET', '/folios/ONB-2026-000003/antecedentes', { token: revisor })
    expect(sinReferencia.cuerpo).toEqual({ permitido: false, motivo: 'folio_sin_referencia', elementos: [] })
  })

  it('proceso sin antecedentes, caducidad, admin si e integrador 403', async () => {
    const admin = await entrar('admin.demo')
    expect((await api('GET', '/folios/ONB-2026-000002/antecedentes', { token: admin })).status).toBe(200)
    const integrador = await entrar('integrador.demo')
    const r403 = await api('GET', '/folios/ONB-2026-000002/antecedentes', { token: integrador })
    expect([r403.status, r403.cuerpo.codigo]).toEqual([403, 'SIN_PERMISO'])
    t += 400 * 24 * 60 * 60 * 1000 // mas alla de caducidad_antecedentes_dias (365); el token tambien caduca
    const otraVez = await entrar('admin.demo')
    expect((await api('GET', '/folios/ONB-2026-000002/antecedentes', { token: otraVez })).cuerpo)
      .toEqual({ permitido: true, motivo: null, elementos: [] })
    estado.procesos.find((p) => p.nombre === 'onboarding')!.permitir_antecedentes = false
    expect((await api('GET', '/folios/ONB-2026-000002/antecedentes', { token: otraVez })).cuerpo)
      .toEqual({ permitido: false, motivo: 'proceso_sin_antecedentes', elementos: [] })
  })
})

describe('enmascaramiento y revelar (ADR-010 A2-A5)', () => {
  /** Documento completado de los datos con valor en un campo sensible, y su folio */
  function conSensible() {
    for (const folio of estado.folios.values()) {
      const doc = folio.documentos.find((d) => d.estado_analisis === 'completado' && typeof d.datos_extraidos.curp === 'string')
      if (doc) return { folio, doc, curp: doc.datos_extraidos.curp as string }
    }
    throw new Error('los datos no tienen una curp')
  }
  const sensibles = () => [...estado.folios.values()].flatMap((f) => f.documentos).flatMap((d) =>
    ['curp', 'clave_elector', 'numero_pasaporte'].map((c) => d.datos_extraidos[c]).filter((v): v is string => typeof v === 'string'))

  it('mascara como la API: **** + 4 ultimos; 4 o menos, ****; null sigue null', () => {
    expect([mascara('ABCDEFGH1234'), mascara('12345'), mascara('1234'), mascara(''), mascara(null), mascara(123456)])
      .toEqual(['****1234', '****2345', '****', '****', null, '****3456'])
  })

  it('ninguna respuesta (documento, expediente, resumen, lista, auditoria) lleva un sensible completo, con ningun rol', async () => {
    const valores = sensibles()
    expect(valores.length).toBeGreaterThan(0)
    for (const usuario of ['admin.demo', 'revisor.demo', 'integrador.demo'] as const) {
      const token = await entrar(usuario)
      for (const folio of estado.folios.values()) {
        const textos = [(await api('GET', `/folios/${folio.folio}`, { token })).texto,
          (await api('GET', `/folios/${folio.folio}/resumen.md`, { token })).texto]
        for (const d of folio.documentos) textos.push((await api('GET', `/documentos/${d.identificador_unico_documento}`, { token })).texto)
        if (usuario === 'admin.demo') textos.push((await api('GET', `/auditoria?folio=${folio.folio}&tamano_pagina=100`, { token })).texto)
        if (usuario !== 'integrador.demo') textos.push((await api('GET', '/folios?tamano_pagina=100', { token })).texto)
        for (const texto of textos) for (const v of valores) expect(texto.includes(v), `${usuario} ${folio.folio}`).toBe(false)
      }
    }
  })

  it('el estado guarda el valor real y la respuesta del PATCH sale enmascarada', async () => {
    const { folio, doc } = conSensible()
    folio.estado_general = 'en_revision'
    const token = await entrar('revisor.demo')
    const r = await api<ResultadoDocumento>('PATCH', `/documentos/${doc.identificador_unico_documento}/datos`,
      { token, cuerpo: { curp: 'XEXX010101HNEXXXA4' } })
    expect(r.status).toBe(200)
    expect(r.cuerpo.datos_extraidos.curp).toBe('****XXA4')
    expect(r.texto).not.toContain('XEXX010101HNEXXXA4')
    expect(r.cuerpo.evidencia_por_campo.curp).toBe('correccion_revisor')
    expect(doc.datos_extraidos.curp).toBe('XEXX010101HNEXXXA4') // por dentro, el valor real
  })

  it('evidencias: ubicacion conservada, otro texto tapado, literales y linea 2 de la MRZ', () => {
    const { doc, curp } = conSensible()
    const prueba = structuredClone(doc)
    prueba.evidencia_por_campo = {
      curp: 'pagina_1', clave_elector: `texto ${curp}`, nombre_completo: `pagina_1:${curp}`,
      sexo: 'pagina_1:P<MEXEJEMPLO<<ANA<<<<<<<<<<<<<<<<<<<<<<<<<<<\nG12345678<0MEX0101014F3001017<<<<<<<<<<<<<<02',
    }
    expect(enmascararDocumento(estado, prueba).evidencia_por_campo).toEqual({
      curp: 'pagina_1', clave_elector: '****', nombre_completo: `pagina_1:${mascara(curp)}`,
      sexo: 'pagina_1:P<MEXEJEMPLO<<ANA<<<<<<<<<<<<<<<<<<<<<<<<<<<\n****',
    })
    expect(prueba.evidencia_por_campo.curp).toBe('pagina_1') // no muta la entrada
  })

  it('revelar: revisor y admin reciben el valor con no-store y dejan dato_revelado sin el valor', async () => {
    const { doc, curp } = conSensible()
    const id = doc.identificador_unico_documento
    for (const usuario of ['revisor.demo', 'admin.demo'] as const) {
      const token = await entrar(usuario)
      const r = await fetch(`${API}/documentos/${id}/revelar`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ campo: 'curp' }),
      })
      expect(r.status).toBe(200)
      expect(r.headers.get('Cache-Control')).toBe('no-store')
      expect(await r.json()).toEqual({ campo: 'curp', valor: curp })
    }
    const entradas = estado.auditoria.filter((e) => e.accion === 'dato_revelado')
    expect(entradas.map((e) => [e.usuario, e.documento_id, e.detalle])).toEqual([
      ['revisor.demo', id, { campo: 'curp' }], ['admin.demo', id, { campo: 'curp' }]])
    expect(JSON.stringify(entradas)).not.toContain(curp)
  })

  it('revelar: integrador 403, 422 por campo o cuerpo, 404, 409 y funciona con el folio cerrado', async () => {
    const { folio, doc, curp } = conSensible()
    const id = doc.identificador_unico_documento
    const revelar = async (usuario: keyof typeof CONTRASENAS, docId: string, cuerpo: unknown) =>
      api('POST', `/documentos/${docId}/revelar`, { token: await entrar(usuario), cuerpo })
    const r403 = await revelar('integrador.demo', id, { campo: 'curp' })
    expect([r403.status, r403.cuerpo.codigo]).toEqual([403, 'SIN_PERMISO'])
    for (const cuerpo of [{ campo: 'no_existe' }, { campo: 'nombre_completo' }, { campo: 'numero_pasaporte' }, {}, { campo: 'curp', extra: 1 }]) {
      const r = await revelar('revisor.demo', id, cuerpo)
      expect([r.status, r.cuerpo.codigo], JSON.stringify(cuerpo)).toEqual([422, 'PETICION_INVALIDA'])
    }
    const r404 = await revelar('revisor.demo', 'no-existe', { campo: 'curp' })
    expect([r404.status, r404.cuerpo.codigo]).toEqual([404, 'DOCUMENTO_NO_ENCONTRADO'])
    const conError = [...estado.folios.values()].flatMap((f) => f.documentos).find((d) => d.estado_analisis === 'error')!
    const r409 = await revelar('revisor.demo', conError.identificador_unico_documento, { campo: 'curp' })
    expect([r409.status, r409.cuerpo.codigo]).toEqual([409, 'DOCUMENTO_CON_ERROR'])
    doc.estado_analisis = 'procesando'
    const enProceso = await revelar('revisor.demo', id, { campo: 'curp' })
    expect([enProceso.status, enProceso.cuerpo.codigo]).toEqual([409, 'DOCUMENTO_EN_PROCESO'])
    doc.estado_analisis = 'completado'
    folio.estado_general = 'rechazado'
    const cerrado = await revelar('revisor.demo', id, { campo: 'curp' })
    expect([cerrado.status, cerrado.cuerpo]).toEqual([200, { campo: 'curp', valor: curp }])
    expect(estado.auditoria.filter((e) => e.accion === 'dato_revelado')).toHaveLength(1) // solo la correcta
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
