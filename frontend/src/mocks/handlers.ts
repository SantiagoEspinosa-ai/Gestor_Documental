// Handlers msw de TODOS los endpoints de docs/contratos/endpoints.md, sobre el estado en memoria.
// Cada ruta se declara con su rol del contrato; handlers.test.ts compara esta lista con el contrato.
import { http, HttpResponse, type HttpHandler } from 'msw'
import {
  DECISIONES_HUMANAS, ESTADOS_GENERALES, ROLES, type PaginaAuditoria, type ProcesoRevisor, type ResultadoDocumento,
  type ResultadoExpediente, type Rol,
} from '../tipos/contrato'
import { auditar, buscarDocumento, fechaIso, siguiente, type EstadoMock, type SesionMock } from './estado'
import {
  avanzarProcesamiento, bloqueantesSinResolver, enProceso, ficha, nuevaAlerta, recalcularExpediente, recalcularTiposDelProceso,
  resumenFolio,
  resumenMarkdown, tipoExtraccion, valorOnull,
} from './logica'
import { error, FalloApi, leerJson } from './respuestas'
import { USUARIOS_DEMO } from './usuarios'

export type Metodo = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export interface RutaMock {
  metodo: Metodo
  /** Ruta tal como aparece en el contrato, p. ej. /folios/{folio}/documentos */
  ruta: string
  /** null = sin autenticacion (login) */
  roles: readonly Rol[] | null
}

interface Contexto {
  request: Request
  params: Record<string, string>
  usuario: SesionMock
}

const TODOS = ROLES
const MAX_BYTES = 20 * 1024 * 1024
const ORIGEN_FRONT = () => globalThis.location?.origin ?? 'http://localhost:5173'
/** Zona horaria del negocio: decide el anio del folio, como ZONA_HORARIA en la API real */
const ZONA_NEGOCIO = 'America/Mexico_City'
/** Primeros bytes de cada formato: la API real rechaza con 415 un contenido que no es de su extension */
const FIRMAS: Record<string, readonly number[]> = {
  pdf: [0x25, 0x50, 0x44, 0x46, 0x2d], // %PDF-
  jpg: [0xff, 0xd8, 0xff],
  jpeg: [0xff, 0xd8, 0xff],
  png: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
}

function anioNegocio(ms: number): number {
  return Number(new Intl.DateTimeFormat('en-US', { timeZone: ZONA_NEGOCIO, year: 'numeric' }).format(ms))
}

function paginacion(q: URLSearchParams, tamanoPorDefecto: number): { pagina: number; tamano: number } {
  const pagina = Number(q.get('pagina') ?? 1)
  const tamano = Number(q.get('tamano_pagina') ?? tamanoPorDefecto)
  if (!Number.isInteger(pagina) || pagina < 1 || !Number.isInteger(tamano) || tamano < 1 || tamano > 100) {
    throw new FalloApi('PETICION_INVALIDA', '`pagina` >= 1 y `tamano_pagina` entre 1 y 100')
  }
  return { pagina, tamano }
}

function autenticar(estado: EstadoMock, request: Request): SesionMock {
  const cabecera = request.headers.get('Authorization') ?? ''
  const token = cabecera.startsWith('Bearer ') ? cabecera.slice(7) : ''
  const sesion = estado.sesiones.get(token)
  if (!sesion) throw new FalloApi('NO_AUTENTICADO', 'Falta el token de acceso o no es valido')
  if (sesion.expiraEn <= estado.ahora()) throw new FalloApi('TOKEN_CADUCADO', 'El token ha caducado')
  return sesion
}

function folioOError(estado: EstadoMock, id: string): ResultadoExpediente {
  const folio = estado.folios.get(id)
  if (!folio) throw new FalloApi('FOLIO_NO_ENCONTRADO', `No existe el folio ${id}`)
  avanzarProcesamiento(estado, folio)
  return folio
}

function documentoOError(estado: EstadoMock, id: string) {
  const encontrado = buscarDocumento(estado, id)
  if (!encontrado) throw new FalloApi('DOCUMENTO_NO_ENCONTRADO', `No existe el documento ${id}`)
  avanzarProcesamiento(estado, encontrado.folio)
  return encontrado
}

function exigirAbierto(folio: ResultadoExpediente): void {
  if (folio.estado_general !== 'en_revision') {
    throw new FalloApi('FOLIO_CERRADO', `El folio ${folio.folio} esta ${folio.estado_general}: solo lectura`)
  }
}

function exigirAnalizado(doc: ResultadoDocumento): void {
  if (enProceso(doc)) throw new FalloApi('DOCUMENTO_EN_PROCESO', 'El documento aun se esta analizando')
  if (doc.estado_analisis === 'error') {
    throw new FalloApi('DOCUMENTO_CON_ERROR', 'El documento termino en error: no se puede corregir ni reclasificar (reprocesar queda fuera del MVP)')
  }
}

function sha256Hex(datos: ArrayBuffer): Promise<string> {
  return crypto.subtle.digest('SHA-256', datos).then((h) =>
    [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, '0')).join(''))
}

function resolverAlerta(estado: EstadoMock, usuario: SesionMock, alerta: { aplica: boolean | null; comentario_revisor: string | null;
  resuelta_por_revisor: boolean; resuelta_por: string | null; resuelta_en: string | null }, cuerpo: Record<string, unknown>) {
  if (typeof cuerpo.aplica !== 'boolean') throw new FalloApi('PETICION_INVALIDA', '`aplica` debe ser true o false')
  if (cuerpo.comentario !== undefined && typeof cuerpo.comentario !== 'string') {
    throw new FalloApi('PETICION_INVALIDA', '`comentario` debe ser texto')
  }
  Object.assign(alerta, {
    aplica: cuerpo.aplica, comentario_revisor: (cuerpo.comentario as string | undefined) ?? null, resuelta_por_revisor: true,
    resuelta_por: usuario.usuario, resuelta_en: fechaIso(estado),
  })
}

export function crearHandlers(estado: EstadoMock): { handlers: HttpHandler[]; rutas: RutaMock[] } {
  const rutas: RutaMock[] = []
  const handlers: HttpHandler[] = []

  function ruta(metodo: Metodo, rutaContrato: string, roles: readonly Rol[] | null,
    manejador: (c: Contexto) => Response | Promise<Response>) {
    rutas.push({ metodo, ruta: rutaContrato, roles })
    const patron = `*/api/v1${rutaContrato.replace(/\{(\w+)\}/g, ':$1')}`
    const metodoMsw = metodo.toLowerCase() as 'get' | 'post' | 'patch' | 'put' | 'delete'
    handlers.push(http[metodoMsw](patron, async ({ request, params }) => {
      try {
        let usuario = null as unknown as SesionMock
        if (roles) {
          usuario = autenticar(estado, request)
          if (!roles.includes(usuario.rol)) return error('SIN_PERMISO', `El rol ${usuario.rol} no tiene acceso`)
        }
        return await manejador({ request, params: params as Record<string, string>, usuario })
      } catch (causa) {
        if (causa instanceof FalloApi) return error(causa.codigo, causa.message)
        console.error('[mocks] error no controlado', causa)
        return error('ERROR_INTERNO', 'Error interno')
      }
    }))
  }

  // ---------------------------------------------------------------- auth
  ruta('POST', '/auth/login', null, async ({ request }) => {
    const cuerpo = await leerJson(request, ['usuario', 'contrasena'])
    if (typeof cuerpo.usuario !== 'string' || typeof cuerpo.contrasena !== 'string') {
      throw new FalloApi('PETICION_INVALIDA', 'Se esperaba {usuario, contrasena}')
    }
    const usuario = USUARIOS_DEMO.find((u) => u.usuario === cuerpo.usuario && u.contrasena === cuerpo.contrasena)
    auditar(estado, String(cuerpo.usuario), 'login', null, null, { resultado: usuario ? 'ok' : 'fallido' })
    if (!usuario) return error('CREDENCIALES_INVALIDAS', 'Usuario o contrasena incorrectos')
    const token = `mock.${usuario.usuario}.${siguiente(estado)}`
    estado.sesiones.set(token, { usuario: usuario.usuario, rol: usuario.rol, expiraEn: estado.ahora() + estado.duracionSesionS * 1000 })
    return HttpResponse.json({ access_token: token, rol: usuario.rol, expires_in: estado.duracionSesionS })
  })

  ruta('GET', '/auth/yo', TODOS, ({ usuario }) => HttpResponse.json({ usuario: usuario.usuario, rol: usuario.rol }))

  // ---------------------------------------------------------------- procesos y folios
  ruta('GET', '/procesos', ['admin', 'integrador', 'revisor'], ({ usuario }) =>
    HttpResponse.json(usuario.rol === 'revisor'
      ? estado.procesos.map(({ webhook_url: _w, modelos: _m, ...resto }): ProcesoRevisor => resto)
      : estado.procesos))

  ruta('POST', '/folios', ['integrador', 'revisor'], async ({ request, usuario }) => {
    const cuerpo = await leerJson(request, ['proceso', 'referencia_externa'])
    const proceso = estado.procesos.find((p) => p.nombre === cuerpo.proceso)
    if (typeof cuerpo.proceso !== 'string') throw new FalloApi('PETICION_INVALIDA', 'Falta `proceso`')
    if (!proceso) throw new FalloApi('PROCESO_NO_ENCONTRADO', `No existe el proceso ${cuerpo.proceso}`)
    const referencia = cuerpo.referencia_externa ?? null
    if (referencia !== null && (typeof referencia !== 'string' || referencia.length > 100)) {
      throw new FalloApi('PETICION_INVALIDA', '`referencia_externa` debe ser texto de hasta 100 caracteres')
    }
    const anio = anioNegocio(estado.ahora())
    const prefijo = `${proceso.prefijo_folio}-${anio}-`
    const secuencia = Math.max(0, ...[...estado.folios.keys()].filter((f) => f.startsWith(prefijo)).map((f) => Number(f.slice(-6)))) + 1
    const folio: ResultadoExpediente = {
      folio: `${prefijo}${String(secuencia).padStart(6, '0')}`, proceso: proceso.nombre, referencia_externa: referencia as string | null,
      fecha_solicitud: fechaIso(estado), estado_general: 'en_revision', documentos: [], comparaciones: [], alertas_expediente: [],
      recomendacion_global: null, decision_humana: null, comentario_decision: null, usuario_decision: null, fecha_decision: null,
      ruta_resumen_md: null,
    }
    recalcularTiposDelProceso(estado, folio) // EXP-001 por cada tipo requerido que falta
    estado.folios.set(folio.folio, folio)
    auditar(estado, usuario.usuario, 'folio_creado', folio.folio, null, {})
    return HttpResponse.json({ folio: folio.folio, estado_general: folio.estado_general }, { status: 201 })
  })

  ruta('GET', '/folios', ['revisor', 'admin'], ({ request }) => {
    const q = new URL(request.url).searchParams
    const { pagina, tamano } = paginacion(q, 20)
    const estadoGeneral = q.get('estado_general')
    if (estadoGeneral && !(ESTADOS_GENERALES as readonly string[]).includes(estadoGeneral)) {
      throw new FalloApi('PETICION_INVALIDA', `estado_general no valido: ${estadoGeneral}`)
    }
    const lista = [...estado.folios.values()]
      .filter((f) => !q.get('proceso') || f.proceso === q.get('proceso'))
      .filter((f) => !estadoGeneral || f.estado_general === estadoGeneral)
      .map((f) => { avanzarProcesamiento(estado, f); return resumenFolio(f) })
      .sort((a, b) => (b.fecha_solicitud ?? '').localeCompare(a.fecha_solicitud ?? ''))
    return HttpResponse.json({ elementos: lista.slice((pagina - 1) * tamano, pagina * tamano), total: lista.length, pagina, tamano_pagina: tamano })
  })

  ruta('GET', '/folios/{folio}', TODOS, ({ params }) => HttpResponse.json(folioOError(estado, params.folio)))

  // ---------------------------------------------------------------- documentos
  ruta('POST', '/folios/{folio}/documentos', ['integrador', 'revisor'], async ({ request, params, usuario }) => {
    const folio = folioOError(estado, params.folio)
    exigirAbierto(folio)
    let formulario: FormData
    try {
      formulario = await request.formData()
    } catch {
      throw new FalloApi('PETICION_INVALIDA', 'Se esperaba multipart con `archivo`')
    }
    // Sin instanceof: en los tests (jsdom) el File de la peticion no es del mismo "mundo" que el Blob global
    const archivo = formulario.get('archivo') as File | string | null
    if (typeof archivo !== 'object' || archivo === null || typeof archivo.arrayBuffer !== 'function' || !archivo.name) {
      throw new FalloApi('PETICION_INVALIDA', 'Falta `archivo`')
    }
    const nombre = String(archivo.name)
    const declarado = (formulario.get('tipo_declarado') as string | null) || null
    if (declarado && !ficha(estado, declarado)) throw new FalloApi('PETICION_INVALIDA', `tipo_declarado desconocido: ${declarado}`)
    if (archivo.size > MAX_BYTES) throw new FalloApi('ARCHIVO_DEMASIADO_GRANDE', 'El archivo supera 20 MB')
    if (archivo.size === 0) throw new FalloApi('PETICION_INVALIDA', 'El archivo esta vacio')
    const extension = nombre.includes('.') ? nombre.split('.').pop()!.toLowerCase() : ''
    const permitidos = declarado ? ficha(estado, declarado)!.formatos_permitidos : estado.tipos.flatMap((t) => t.formatos_permitidos)
    if (!permitidos.includes(extension)) {
      throw new FalloApi('FORMATO_NO_PERMITIDO', `Formato .${extension} no permitido (${[...new Set(permitidos)].join(', ')})`)
    }
    const bytes = await archivo.arrayBuffer()
    const firma = FIRMAS[extension] ?? []
    const inicio = new Uint8Array(bytes.slice(0, firma.length))
    if (!firma.every((b, i) => inicio[i] === b)) {
      throw new FalloApi('FORMATO_NO_PERMITIDO', 'El contenido del archivo no corresponde a su extension')
    }

    const hash = await sha256Hex(bytes)
    const id = `00000000-0000-4000-9000-${String(siguiente(estado)).padStart(12, '0')}`
    const repetido = folio.documentos.find((d) => d.referencia_archivo_original.hash === hash)
    // Clasificador simulado: mismo SHA-256 que un documento de los datos, o por el nombre del fichero
    const origen = [...estado.folios.values()].flatMap((f) => f.documentos)
      .find((d) => d.referencia_archivo_original.hash === hash && d.estado_analisis === 'completado')
    const porNombre = [...estado.tipos].sort((a, b) => b.nombre.length - a.nombre.length).find((t) => nombre.startsWith(t.nombre))?.nombre
    const tipoContenido = origen?.tipo_documental_detectado ?? porNombre ?? declarado ?? estado.tipos[0].nombre
    const confianza = origen || porNombre ? 0.93 : 0.55
    const doc: ResultadoDocumento = {
      folio_solicitud: folio.folio, identificador_unico_documento: id, tipo_documental_declarado: declarado,
      tipo_documental_detectado: null, tipo_documental_confirmado: null, confianza_clasificacion: null, datos_extraidos: {},
      nivel_confianza_por_campo: {}, evidencia_por_campo: {}, reglas_cumplidas_e_incumplidas: { cumplidas: [], incumplidas: [] },
      alertas_encontradas: repetido
        ? [nuevaAlerta(estado, 'DUP-001', `Mismo SHA-256 que el documento ${repetido.identificador_unico_documento} del folio`, 'critica')]
        : [],
      correcciones: [], recomendacion: null, estado_analisis: 'pendiente', fecha_y_modelo_utilizado: null,
      referencia_archivo_original: {
        nombre_archivo: nombre, ruta: `${folio.proceso}/${folio.folio.split('-')[1]}/${folio.folio.slice(-6)}/${id}.${extension}`, hash,
      },
    }
    folio.documentos.push(doc)
    estado.archivos.set(id, archivo)
    estado.procesamientos.set(id, {
      inicio: estado.ahora(), tipoExtraccion: declarado ?? tipoContenido, tipoContenido, confianzaClasificacion: confianza, origen,
    })
    recalcularExpediente(estado, folio)
    // Sin nombre_archivo, como la API real: los nombres de fichero suelen llevar el nombre de la persona
    auditar(estado, usuario.usuario, 'documento_subido', folio.folio, id,
      { hash_sha256: hash, tamano_bytes: archivo.size, duplicado: Boolean(repetido) })
    return HttpResponse.json({ identificador_unico_documento: id, estado_analisis: 'pendiente' }, { status: 202 })
  })

  ruta('GET', '/documentos/{id}', TODOS, ({ params }) => HttpResponse.json(documentoOError(estado, params.id).doc))

  ruta('GET', '/documentos/{id}/original', ['revisor', 'admin'], ({ params }) => {
    const { doc } = documentoOError(estado, params.id)
    const id = doc.identificador_unico_documento
    const archivo = estado.archivos.get(id)
    // Como la URL prefirmada real (caduca a los 300 s): una nueva en cada peticion y la anterior deja de valer,
    // para que la UI la pida cada vez que abre el visor y no la guarde
    const anterior = estado.urls.get(id)
    if (anterior?.startsWith('blob:')) URL.revokeObjectURL(anterior)
    // Subidos en esta sesion: URL local del propio fichero; datos iniciales: copia en public/mock-originales
    const url = archivo ? URL.createObjectURL(archivo)
      : `${ORIGEN_FRONT()}/mock-originales/${encodeURIComponent(doc.referencia_archivo_original.nombre_archivo)}?firma=${siguiente(estado)}`
    estado.urls.set(id, url)
    return HttpResponse.json({ url })
  })

  ruta('PATCH', '/documentos/{id}/datos', ['revisor'], async ({ request, params, usuario }) => {
    const { folio, doc } = documentoOError(estado, params.id)
    exigirAbierto(folio)
    exigirAnalizado(doc)
    const cuerpo = await leerJson(request)
    const campos = ficha(estado, tipoExtraccion(doc))?.campos ?? {}
    const desconocidos = Object.keys(cuerpo).filter((c) => !(c in campos))
    if (!Object.keys(cuerpo).length || desconocidos.length) {
      throw new FalloApi('PETICION_INVALIDA', `Campos no validos para ${tipoExtraccion(doc)}: ${desconocidos.join(', ') || '(ninguno)'}`)
    }
    for (const [campo, recibido] of Object.entries(cuerpo)) {
      const valor = valorOnull(recibido) // "" o solo espacios: el campo queda sin valor (null)
      doc.correcciones.push({ campo, valor_anterior: doc.datos_extraidos[campo] ?? null, valor_nuevo: valor, usuario: usuario.usuario, fecha: fechaIso(estado) })
      doc.datos_extraidos[campo] = valor
      doc.nivel_confianza_por_campo[campo] = 1
      doc.evidencia_por_campo[campo] = 'correccion_revisor'
      auditar(estado, usuario.usuario, 'dato_corregido', folio.folio, doc.identificador_unico_documento, { campo })
    }
    recalcularExpediente(estado, folio)
    return HttpResponse.json(doc)
  })

  ruta('POST', '/documentos/{id}/confirmar-clasificacion', ['revisor'], async ({ request, params, usuario }) => {
    const { folio, doc } = documentoOError(estado, params.id)
    exigirAbierto(folio)
    exigirAnalizado(doc)
    const { tipo_documental: tipo } = await leerJson(request, ['tipo_documental'])
    if (typeof tipo !== 'string' || !ficha(estado, tipo)) throw new FalloApi('PETICION_INVALIDA', `tipo_documental no valido: ${String(tipo)}`)
    const cls = doc.alertas_encontradas.filter((a) => a.codigo === 'CLS-001')
    auditar(estado, usuario.usuario, 'clasificacion_confirmada', folio.folio, doc.identificador_unico_documento, { tipo_documental: tipo })
    if (tipo === tipoExtraccion(doc)) {
      // Mismo tipo con el que se extrajo: CLS-001 era un falso positivo
      doc.tipo_documental_confirmado = tipo
      cls.forEach((a) => resolverAlerta(estado, usuario, a, { aplica: false, comentario: 'Clasificacion confirmada por el revisor' }))
    } else {
      // Tipo distinto: se guarda la version previa y se reprocesa con la ficha confirmada
      estado.versionesPrevias.set(doc.identificador_unico_documento,
        [...(estado.versionesPrevias.get(doc.identificador_unico_documento) ?? []), structuredClone(doc)])
      cls.forEach((a) => resolverAlerta(estado, usuario, a, { aplica: true, comentario: `Reclasificado como ${tipo}` }))
      Object.assign(doc, {
        tipo_documental_confirmado: tipo, estado_analisis: 'pendiente', datos_extraidos: {}, nivel_confianza_por_campo: {},
        evidencia_por_campo: {}, reglas_cumplidas_e_incumplidas: { cumplidas: [], incumplidas: [] }, recomendacion: null,
        fecha_y_modelo_utilizado: null,
        alertas_encontradas: doc.alertas_encontradas.filter((a) => a.codigo === 'DUP-001' || a.codigo === 'CLS-001'),
      })
      const origen = [...estado.folios.values()].flatMap((f) => f.documentos).find((d) =>
        d !== doc && d.referencia_archivo_original.hash === doc.referencia_archivo_original.hash && d.estado_analisis === 'completado')
      estado.procesamientos.set(doc.identificador_unico_documento, {
        inicio: estado.ahora(), tipoExtraccion: tipo, tipoContenido: tipo, confianzaClasificacion: 1, origen,
      })
    }
    recalcularTiposDelProceso(estado, folio) // el tipo efectivo puede haber cambiado
    return HttpResponse.json(doc)
  })

  ruta('POST', '/documentos/{id}/alertas/{alerta_id}/resolver', ['revisor'], async ({ request, params, usuario }) => {
    const { folio, doc } = documentoOError(estado, params.id)
    exigirAbierto(folio)
    if (enProceso(doc)) throw new FalloApi('DOCUMENTO_EN_PROCESO', 'El documento aun se esta analizando')
    const alerta = doc.alertas_encontradas.find((a) => a.id === params.alerta_id)
    if (!alerta) throw new FalloApi('ALERTA_NO_ENCONTRADA', `No existe la alerta ${params.alerta_id} en el documento`)
    resolverAlerta(estado, usuario, alerta, await leerJson(request, ['aplica', 'comentario']))
    auditar(estado, usuario.usuario, 'alerta_resuelta', folio.folio, doc.identificador_unico_documento, { codigo: alerta.codigo, aplica: alerta.aplica })
    recalcularExpediente(estado, folio)
    return HttpResponse.json(doc)
  })

  ruta('POST', '/folios/{folio}/alertas/{alerta_id}/resolver', ['revisor'], async ({ request, params, usuario }) => {
    const folio = folioOError(estado, params.folio)
    exigirAbierto(folio)
    const alerta = folio.alertas_expediente.find((a) => a.id === params.alerta_id)
    if (!alerta) throw new FalloApi('ALERTA_NO_ENCONTRADA', `No existe la alerta ${params.alerta_id} en el expediente`)
    resolverAlerta(estado, usuario, alerta, await leerJson(request, ['aplica', 'comentario']))
    auditar(estado, usuario.usuario, 'alerta_resuelta', folio.folio, null, { codigo: alerta.codigo, aplica: alerta.aplica })
    recalcularExpediente(estado, folio)
    return HttpResponse.json(folio)
  })

  ruta('POST', '/folios/{folio}/decision', ['revisor'], async ({ request, params, usuario }) => {
    const folio = folioOError(estado, params.folio)
    exigirAbierto(folio)
    const cuerpo = await leerJson(request, ['decision', 'comentario'])
    if (!(DECISIONES_HUMANAS as readonly unknown[]).includes(cuerpo.decision)) {
      throw new FalloApi('PETICION_INVALIDA', '`decision` debe ser aprobar o rechazar')
    }
    if (cuerpo.comentario !== undefined && typeof cuerpo.comentario !== 'string') {
      throw new FalloApi('PETICION_INVALIDA', '`comentario` debe ser texto')
    }
    if (folio.documentos.some(enProceso)) throw new FalloApi('DOCUMENTO_EN_PROCESO', 'Hay documentos que aun se estan analizando')
    const bloqueantes = bloqueantesSinResolver(folio)
    if (cuerpo.decision === 'aprobar' && bloqueantes.length) {
      throw new FalloApi('DECISION_BLOQUEADA', `No se puede aprobar: bloqueantes sin descartar (${bloqueantes.map((a) => a.codigo).join(', ')})`)
    }
    Object.assign(folio, {
      estado_general: cuerpo.decision === 'aprobar' ? 'aprobado' : 'rechazado', decision_humana: cuerpo.decision,
      comentario_decision: (cuerpo.comentario as string | undefined) ?? null, usuario_decision: usuario.usuario, fecha_decision: fechaIso(estado),
    })
    auditar(estado, usuario.usuario, 'decision_tomada', folio.folio, null, { decision: cuerpo.decision })
    return HttpResponse.json(folio)
  })

  // ---------------------------------------------------------------- expediente, RAG y catalogos
  ruta('GET', '/folios/{folio}/resumen.md', TODOS, ({ params }) => {
    const folio = folioOError(estado, params.folio)
    if (!folio.ruta_resumen_md) throw new FalloApi('RESUMEN_NO_DISPONIBLE', 'El resumen de este folio aun no existe')
    return new HttpResponse(resumenMarkdown(folio), { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } })
  })

  // Forma pendiente de un ADR de la etapa 3: de momento, lista vacia
  ruta('GET', '/folios/{folio}/antecedentes', ['revisor'], ({ params }) => {
    folioOError(estado, params.folio)
    return HttpResponse.json([])
  })

  ruta('GET', '/tipos-documentales', TODOS, () => HttpResponse.json(estado.tipos))

  // Paginada (ADR-008, punto 1)
  ruta('GET', '/auditoria', ['admin'], ({ request }) => {
    const q = new URL(request.url).searchParams
    const { pagina, tamano } = paginacion(q, 50)
    const folio = q.get('folio')
    const lista = estado.auditoria.filter((e) => !folio || e.folio === folio)
      .sort((a, b) => b.creado_en.localeCompare(a.creado_en) || b.id - a.id)
    const respuesta: PaginaAuditoria = {
      elementos: lista.slice((pagina - 1) * tamano, pagina * tamano), total: lista.length, pagina, tamano_pagina: tamano,
    }
    return HttpResponse.json(respuesta)
  })

  // ---------------------------------------------------------------- resto de /api/v1: 404 o 405
  const patrones = rutas.map((r) => ({ ...r, regex: new RegExp(`^${r.ruta.replace(/\./g, '\\.').replace(/\{\w+\}/g, '[^/]+')}$`) }))
  handlers.push(http.all('*/api/v1/*', ({ request }) => {
    const camino = new URL(request.url).pathname.replace(/^.*?\/api\/v1/, '')
    return patrones.some((p) => p.regex.test(camino))
      ? error('METODO_NO_PERMITIDO', `${request.method} no esta permitido en ${camino}`)
      : error('RUTA_NO_ENCONTRADA', `No existe la ruta ${camino}`)
  }))

  return { handlers, rutas }
}
