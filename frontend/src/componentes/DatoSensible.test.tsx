// @vitest-environment jsdom
// "Mostrar" de los datos sensibles (H17, ADR-010 A4) contra los mocks, que implementan revelar como la API.
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { abrirDocumento, esperarExpediente, montarExpediente, volverALaLista } from '../pruebas/expediente'
import { SEGUNDOS_DATO_REVELADO } from '../utilidades/etiquetas'
import { DatoSensible } from './DatoSensible'

const mock = usarServidorMock()
const CREDENCIAL = 'credencial_elector_vencido_foto.jpg'
const PASAPORTE = 'pasaporte_vencido_escaneado.pdf'

afterEach(() => { vi.useRealTimers() })

/** El documento de los datos del mock por su nombre de fichero, con sus valores REALES (el estado no enmascara) */
function documentoMock(folio: string, nombre: string) {
  return mock.estado.folios.get(folio)!.documentos.find((d) => d.referencia_archivo_original.nombre_archivo === nombre)!
}

async function abrir(folio: string, nombre: string) {
  montarExpediente(`/folios/${folio}`)
  await esperarExpediente(folio)
  await abrirDocumento(userEvent.setup(), nombre)
  return screen.findByRole('region', { name: 'Datos leídos' })
}
const fila = (datos: HTMLElement, campo: string) => within(datos).getByRole('rowheader', { name: campo }).closest('tr')!

describe('botón Mostrar de los datos sensibles', () => {
  it.each(['revisor.demo', 'admin.demo'] as const)('%s ve "Mostrar" en los campos sensibles con valor, y solo en ellos', async (usuario) => {
    await entrarComo(usuario)
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    expect(within(fila(datos, 'Curp')).getByRole('button', { name: 'Mostrar Curp' })).toBeTruthy()
    expect(within(fila(datos, 'Clave elector')).getByRole('button', { name: 'Mostrar Clave elector' })).toBeTruthy()
    expect(within(fila(datos, 'Nombre completo')).queryByRole('button', { name: /Mostrar/ })).toBeNull()
    expect(within(datos).getAllByRole('button', { name: /^Mostrar / })).toHaveLength(2)
  })

  it('el integrador ve el valor enmascarado y nunca el botón', async () => {
    await entrarComo('integrador.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    expect(within(fila(datos, 'Curp')).getByText(/^\*\*\*\*/)).toBeTruthy()
    expect(within(datos).queryByRole('button', { name: /Mostrar/ })).toBeNull()
  })

  it('mostrar llama a revelar y enseña el valor; ocultar vuelve a la máscara; sin storage', async () => {
    const curp = documentoMock('ONB-2026-000001', CREDENCIAL).datos_extraidos.curp as string
    const escrituras = vi.spyOn(Storage.prototype, 'setItem')
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    const celda = fila(datos, 'Curp')
    expect(celda.textContent).not.toContain(curp)
    escrituras.mockClear()
    await userEvent.setup().click(within(celda).getByRole('button', { name: 'Mostrar Curp' }))
    expect(await within(celda).findByText(curp)).toBeTruthy()
    expect(mock.peticiones.filter((p) => p.endsWith('/revelar'))).toHaveLength(1)
    expect(screen.getByText(/Se muestra Curp/)).toBeTruthy() // aria-live
    expect(mock.estado.auditoria.at(-1)).toMatchObject({ accion: 'dato_revelado', detalle: { campo: 'curp' } })
    // Nada se guarda en el navegador
    expect(escrituras).not.toHaveBeenCalled()
    for (const almacen of [sessionStorage, localStorage]) {
      for (let i = 0; i < almacen.length; i++) expect(almacen.getItem(almacen.key(i)!)).not.toContain(curp)
    }
    // Las comparaciones, la evidencia y la correccion no cambian: "Mostrar" es solo la tabla de datos
    expect(document.body.textContent!.split(curp)).toHaveLength(2)
    await userEvent.setup().click(within(celda).getByRole('button', { name: 'Ocultar Curp' }))
    expect(celda.textContent).not.toContain(curp)
    expect(within(celda).getByRole('button', { name: 'Mostrar Curp' })).toBeTruthy()
    escrituras.mockRestore()
  })

  it('el motivo es opcional y no bloquea: se envia si tiene 3 caracteres o mas y se vacia tras mostrar', async () => {
    const curp = documentoMock('ONB-2026-000001', CREDENCIAL).datos_extraidos.curp as string
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    const celda = fila(datos, 'Curp')
    const u = userEvent.setup()
    // Muy corto: se muestra igual, sin motivo
    await u.type(within(celda).getByRole('textbox', { name: 'Motivo para mostrar Curp (opcional)' }), 'ab')
    await u.click(within(celda).getByRole('button', { name: 'Mostrar Curp' }))
    expect(await within(celda).findByText(curp)).toBeTruthy()
    expect(mock.estado.auditoria.at(-1)!.detalle).toEqual({ campo: 'curp' })
    await u.click(within(celda).getByRole('button', { name: 'Ocultar Curp' }))
    const motivo = within(celda).getByRole('textbox', { name: 'Motivo para mostrar Curp (opcional)' }) as HTMLInputElement
    expect(motivo.value).toBe('') // al mostrar se vacio
    expect(motivo.maxLength).toBe(200)
    await u.type(motivo, '  Lo pide el cliente  ')
    await u.click(within(celda).getByRole('button', { name: 'Mostrar Curp' }))
    expect(await within(celda).findByText(curp)).toBeTruthy()
    expect(mock.estado.auditoria.at(-1)!.detalle).toEqual({ campo: 'curp', motivo: 'Lo pide el cliente' })
  })

  it('al cambiar de documento se oculta', async () => {
    const curp = documentoMock('ONB-2026-000001', CREDENCIAL).datos_extraidos.curp as string
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    const usuario = userEvent.setup()
    await usuario.click(within(fila(datos, 'Curp')).getByRole('button', { name: 'Mostrar Curp' }))
    expect(await screen.findByText(curp)).toBeTruthy()
    await volverALaLista(usuario)
    await abrirDocumento(usuario, PASAPORTE)
    await screen.findByRole('rowheader', { name: 'Numero pasaporte' })
    await volverALaLista(usuario)
    await abrirDocumento(usuario, CREDENCIAL)
    const otraVez = await screen.findByRole('region', { name: 'Datos leídos' })
    await waitFor(() => expect(within(otraVez).queryByRole('rowheader', { name: 'Curp' })).toBeTruthy())
    expect(screen.queryByText(curp)).toBeNull()
    expect(within(fila(otraVez, 'Curp')).getByRole('button', { name: 'Mostrar Curp' })).toBeTruthy()
  })

  it('también con el folio cerrado', async () => {
    const curp = documentoMock('ONB-2026-000004', 'credencial_elector_sano_digital.pdf').datos_extraidos.curp as string
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000004', 'credencial_elector_sano_digital.pdf')
    await userEvent.setup().click(within(fila(datos, 'Curp')).getByRole('button', { name: 'Mostrar Curp' }))
    expect(await within(datos).findByText(curp)).toBeTruthy()
  })

  it(`se oculta solo a los ${SEGUNDOS_DATO_REVELADO} s`, async () => {
    const doc = documentoMock('ONB-2026-000001', CREDENCIAL)
    const curp = doc.datos_extraidos.curp as string
    await entrarComo('revisor.demo')
    vi.useFakeTimers({ shouldAdvanceTime: true })
    montar('/', <DatoSensible documentoId={doc.identificador_unico_documento} campo="curp"><span>****máscara</span></DatoSensible>)
    const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await usuario.click(screen.getByRole('button', { name: 'Mostrar Curp' }))
    expect(await screen.findByText(curp)).toBeTruthy()
    act(() => { vi.advanceTimersByTime((SEGUNDOS_DATO_REVELADO - 1) * 1000) })
    expect(screen.getByText(curp)).toBeTruthy()
    act(() => { vi.advanceTimersByTime(1000) })
    expect(screen.queryByText(curp)).toBeNull()
    expect(screen.getByText('****máscara')).toBeTruthy()
  })

  it.each([
    [409, 'DOCUMENTO_EN_PROCESO', /aún se está analizando/],
    [409, 'DOCUMENTO_CON_ERROR', /terminó en error/],
    [403, 'SIN_PERMISO', /no puede ver datos sensibles/],
    [422, 'PETICION_INVALIDA', /no se puede mostrar/],
  ] as const)('error %i %s: mensaje y el valor sigue enmascarado', async (estado, codigo, mensaje) => {
    const curp = documentoMock('ONB-2026-000001', CREDENCIAL).datos_extraidos.curp as string
    mock.servidor.use(http.post('*/api/v1/documentos/:id/revelar', () => HttpResponse.json({ codigo, mensaje: 'x' }, { status: estado })))
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    const celda = fila(datos, 'Curp')
    await userEvent.setup().click(within(celda).getByRole('button', { name: 'Mostrar Curp' }))
    expect((await within(celda).findByRole('alert')).textContent).toMatch(mensaje)
    expect(celda.textContent).not.toContain(curp)
    expect(within(celda).getByRole('button', { name: 'Mostrar Curp' })).toHaveProperty('disabled', false)
  })

  it('mientras carga, el botón queda deshabilitado', async () => {
    let soltar = () => {}
    mock.servidor.use(http.post('*/api/v1/documentos/:id/revelar', async () => {
      await new Promise<void>((r) => { soltar = r })
      return HttpResponse.json({ campo: 'curp', valor: 'XEXX010101HNEXXXA4' }, { headers: { 'Cache-Control': 'no-store' } })
    }))
    await entrarComo('revisor.demo')
    const datos = await abrir('ONB-2026-000001', CREDENCIAL)
    const celda = fila(datos, 'Curp')
    await userEvent.setup().click(within(celda).getByRole('button', { name: 'Mostrar Curp' }))
    await waitFor(() => expect(within(celda).getByRole('button', { name: 'Mostrar Curp' })).toHaveProperty('disabled', true))
    soltar()
    expect(await within(celda).findByText('XEXX010101HNEXXXA4')).toBeTruthy()
  })
})
