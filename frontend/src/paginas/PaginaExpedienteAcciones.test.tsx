// @vitest-environment jsdom
// Acciones del revisor en el expediente (bloque H): solo rol revisor y folio abierto. Datos ficticios del mock.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { MS_HASTA_COMPLETADO } from '../mocks/logica'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { MENSAJES_ERROR } from '../utilidades/mensajes'
import { MOTIVO_ANIO, MOTIVO_OBLIGATORIO } from '../utilidades/valores'
import { PaginaExpediente } from './PaginaExpediente'

const mock = usarServidorMock()

async function abrir(folio: string, usuario: 'revisor.demo' | 'admin.demo' | 'integrador.demo' = 'revisor.demo') {
  await entrarComo(usuario)
  montar(`/folios/${folio}`, <Routes><Route path="/folios/:folio" element={<PaginaExpediente tiemposSondeo={{ inicialMs: 30, maximoMs: 30 }} />} /></Routes>)
  await screen.findByRole('heading', { name: new RegExp(`Expediente ${folio}`) })
  return userEvent.setup()
}
const fila = (campo: string) => screen.getByRole('rowheader', { name: campo }).closest('tr')!
const aviso = () => screen.getByTestId('aviso')
const folioMock = (folio: string) => mock.estado.folios.get(folio)!
const aprobar = () => screen.getByRole('button', { name: 'Aprobar' }) as HTMLButtonElement
const posts = (ruta: string) => mock.peticiones.filter((p) => p === ruta).length

describe('acciones del revisor', () => {
  it('un campo obligatorio no se puede guardar vacío: botón deshabilitado y motivo visible, sin PATCH', async () => {
    const u = await abrir('ONB-2026-000001') // pasaporte: nombre_completo es obligatorio
    await u.click(within(fila('Nombre completo')).getByRole('button', { name: 'Corregir Nombre completo' }))
    const entrada = within(fila('Nombre completo')).getByLabelText('Nuevo valor de Nombre completo') as HTMLInputElement
    const guardar = () => within(fila('Nombre completo')).getByRole('button', { name: 'Guardar corrección' }) as HTMLButtonElement
    expect(guardar().disabled).toBe(false) // empieza con el valor actual
    expect(within(fila('Nombre completo')).getByText('Campo obligatorio de la ficha: escribe el valor correcto.')).toBeTruthy()
    await u.clear(entrada)
    expect(guardar().disabled).toBe(true)
    expect(within(fila('Nombre completo')).getByText(MOTIVO_OBLIGATORIO)).toBeTruthy()
    expect(entrada.getAttribute('aria-invalid')).toBe('true')
    await u.type(entrada, '   {Enter}') // solo espacios e Intro: tampoco envia
    expect(guardar().disabled).toBe(true)
    expect(mock.peticiones.filter((p) => p.startsWith('PATCH '))).toEqual([])
    await u.type(entrada, 'ANA EJEMPLO PRUEBA')
    expect(guardar().disabled).toBe(false)
    expect(within(fila('Nombre completo')).queryByText(MOTIVO_OBLIGATORIO)).toBeNull()
  })

  it('anio: valida las 4 cifras antes de enviar y lo envía como entero', async () => {
    const u = await abrir('ONB-2026-000001')
    await u.click(screen.getByRole('button', { name: /credencial_elector_vencido_foto\.jpg/ }))
    await u.click(within(fila('Vigencia')).getByRole('button', { name: 'Corregir Vigencia' }))
    const entrada = within(fila('Vigencia')).getByLabelText('Nuevo valor de Vigencia')
    const guardar = () => within(fila('Vigencia')).getByRole('button', { name: 'Guardar corrección' }) as HTMLButtonElement
    await u.clear(entrada)
    await u.type(entrada, '203')
    expect(guardar().disabled).toBe(true)
    expect(within(fila('Vigencia')).getByText(MOTIVO_ANIO)).toBeTruthy()
    await u.type(entrada, '0')
    expect(guardar().disabled).toBe(false)
    await u.click(guardar())
    await waitFor(() => expect(aviso().textContent).toBe('Vigencia corregido.'))
    const credencial = folioMock('ONB-2026-000001').documentos[1]
    expect(credencial.datos_extraidos.vigencia).toBe(2030) // entero, no "2030"
    expect(credencial.correcciones.at(-1)).toMatchObject({ campo: 'vigencia', valor_anterior: 2029, valor_nuevo: 2030 })
  })

  it('corrige un dato inline mostrando el valor anterior; vaciar un campo opcional lo deja en null ("no detectado")', async () => {
    const u = await abrir('ONB-2026-000001') // pasaporte seleccionado
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Corregir Sexo' }))
    expect(within(fila('Sexo')).getByText('M')).toBeTruthy() // "Valor actual: M"
    const entrada = within(fila('Sexo')).getByLabelText('Nuevo valor de Sexo')
    await u.clear(entrada)
    await u.type(entrada, 'F')
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Guardar corrección' }))
    await waitFor(() => expect(aviso().textContent).toBe('Sexo corregido.'))
    expect(within(fila('Sexo')).getByText('F')).toBeTruthy()
    expect(within(fila('Sexo')).getByText('Corregido por revisor (antes: M)')).toBeTruthy()

    await u.click(within(fila('Nacionalidad')).getByRole('button', { name: 'Corregir Nacionalidad' }))
    await u.clear(within(fila('Nacionalidad')).getByLabelText('Nuevo valor de Nacionalidad'))
    await u.click(within(fila('Nacionalidad')).getByRole('button', { name: 'Guardar corrección' }))
    await waitFor(() => expect(within(fila('Nacionalidad')).getByText('no detectado')).toBeTruthy())
    expect(within(fila('Nacionalidad')).getByText('Corregido por revisor (antes: UTOPICA)')).toBeTruthy()
    const pasaporte = folioMock('ONB-2026-000001').documentos[0]
    expect(pasaporte.correcciones.at(-1)).toMatchObject({ campo: 'nacionalidad', valor_nuevo: null })
  })

  it('confirma una clasificacion distinta: vuelve a pendiente y el sondeo sigue el nuevo analisis', async () => {
    const u = await abrir('ONB-2026-000001')
    await u.click(screen.getByRole('button', { name: /credencial_elector_vencido_foto\.jpg/ }))
    await u.selectOptions(screen.getByLabelText('Tipo documental correcto'), 'comprobante_domicilio')
    expect(screen.getByText(/se volverá a analizar/)).toBeTruthy()
    await u.click(screen.getByRole('button', { name: 'Confirmar clasificación' }))
    const id = '00000000-0000-4000-8000-000001000002'
    await waitFor(() => expect(screen.getByTestId(`estado-${id}`).textContent).toBe('Pendiente'))
    expect(aviso().textContent).toBe('Clasificación confirmada.')
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`estado-${id}`).textContent).toBe('Completado'))
  })

  it('marca una alerta de expediente como falso positivo con comentario y entonces se puede aprobar, con confirmacion', async () => {
    const u = await abrir('ONB-2026-000003')
    expect(aprobar().disabled).toBe(true)
    const nota = screen.getByRole('note')
    expect(nota.textContent).toContain('EXP-001')
    const expediente = screen.getByRole('region', { name: 'Alertas del expediente' })
    await u.type(within(expediente).getByLabelText('Comentario sobre EXP-001'), 'Llega por otra via')
    await u.click(within(expediente).getByRole('button', { name: 'EXP-001: falso positivo' }))
    await waitFor(() => expect(aviso().textContent).toBe('Alerta EXP-001 revisada.'))
    const revisada = within(screen.getByRole('region', { name: 'Alertas del expediente' })).getByText('EXP-001').closest('li')!.textContent!
    expect(revisada).toContain('Falso positivo')
    expect(revisada).toContain('“Llega por otra via”')
    expect(revisada).toContain('revisor.demo')

    expect(aprobar().disabled).toBe(false)
    await u.type(screen.getByLabelText('Comentario de la decisión'), 'Revisado a mano')
    await u.click(aprobar())
    const dialogo = screen.getByRole('alertdialog', { name: 'Confirmar la decisión' })
    expect(posts('POST /folios/ONB-2026-000003/decision')).toBe(0) // nada sin confirmar
    await u.click(within(dialogo).getByRole('button', { name: 'Sí, aprobar' }))
    await waitFor(() => expect(aviso().textContent).toBe('Folio aprobado.'))
    const cabecera = screen.getByRole('heading', { name: /Expediente/ }).closest('header')!
    expect(within(cabecera).getByRole('status').textContent).toContain('Decisión: Aprobado · “Revisado a mano”')
    // Cerrado: ya no hay acciones
    expect(screen.queryByRole('region', { name: 'Decisión del revisor' })).toBeNull()
    expect(screen.queryByRole('button', { name: /falso positivo/ })).toBeNull()
  })

  it('aprobar deshabilitado mientras una bloqueante aplique; rechazar pide confirmacion y se puede cancelar', async () => {
    const u = await abrir('ONB-2026-000001')
    const alertasDoc = screen.getByRole('region', { name: 'Alertas del documento seleccionado' })
    await u.click(within(alertasDoc).getByRole('button', { name: 'REG-vigencia_documento: aplica' }))
    await waitFor(() => expect(within(within(alertasDoc).getByText('REG-vigencia_documento').closest('li')!).getByText('Aplica (confirmada por el revisor)')).toBeTruthy())
    expect(aprobar().disabled).toBe(true) // aplica=true confirma el problema: solo se puede rechazar
    expect(screen.getByRole('note').textContent).toContain('REG-vigencia_documento')

    await u.click(screen.getByRole('button', { name: 'Rechazar' }))
    await u.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancelar' }))
    expect(posts('POST /folios/ONB-2026-000001/decision')).toBe(0)
    await u.click(screen.getByRole('button', { name: 'Rechazar' }))
    await u.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Sí, rechazar' }))
    await waitFor(() => expect(aviso().textContent).toBe('Folio rechazado.'))
    expect(folioMock('ONB-2026-000001')).toMatchObject({ estado_general: 'rechazado', decision_humana: 'rechazar', usuario_decision: 'revisor.demo' })
  })

  it('solo el revisor y con el folio abierto: admin, integrador y un folio cerrado no ven acciones', async () => {
    for (const [folio, usuario] of [['ONB-2026-000001', 'admin.demo'], ['ONB-2026-000001', 'integrador.demo'], ['ONB-2026-000004', 'revisor.demo']] as const) {
      await abrir(folio, usuario)
      expect(screen.queryByRole('region', { name: 'Decisión del revisor' }), `${usuario} ${folio}`).toBeNull()
      expect(screen.queryByRole('button', { name: /^Corregir / })).toBeNull()
      expect(screen.queryByRole('button', { name: /aplica$/ })).toBeNull()
      expect(screen.queryByRole('button', { name: 'Confirmar clasificación' })).toBeNull()
      cleanup()
    }
  })
})

describe('409 de las acciones: mensaje claro y la vista se recarga', () => {
  async function corregirSexo(u: ReturnType<typeof userEvent.setup>) {
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Corregir Sexo' }))
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Guardar corrección' }))
  }

  it('FOLIO_CERRADO: otro revisor lo decidio; pasa a solo lectura', async () => {
    const u = await abrir('ONB-2026-000001')
    Object.assign(folioMock('ONB-2026-000001'), { estado_general: 'rechazado', decision_humana: 'rechazar', usuario_decision: 'otro.revisor' })
    await corregirSexo(u)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.FOLIO_CERRADO))
    expect(aviso().getAttribute('role')).toBe('alert')
    await waitFor(() => expect(screen.queryByRole('button', { name: /^Corregir / })).toBeNull())
    expect(screen.getByText(/Folio cerrado: solo lectura/)).toBeTruthy()
  })

  it('DOCUMENTO_EN_PROCESO y DOCUMENTO_CON_ERROR: el documento cambio de estado', async () => {
    const u = await abrir('ONB-2026-000001')
    const pasaporte = folioMock('ONB-2026-000001').documentos[0]
    pasaporte.estado_analisis = 'procesando'
    await corregirSexo(u)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.DOCUMENTO_EN_PROCESO))
    await waitFor(() => expect(screen.getByTestId(`estado-${pasaporte.identificador_unico_documento}`).textContent).toBe('Procesando'))

    cleanup()
    pasaporte.estado_analisis = 'completado'
    const u2 = await abrir('ONB-2026-000001')
    folioMock('ONB-2026-000001').documentos[0].estado_analisis = 'error'
    await corregirSexo(u2)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.DOCUMENTO_CON_ERROR))
    await waitFor(() => expect(screen.getByText('El análisis de este documento falló.')).toBeTruthy())
  })

  it('DECISION_BLOQUEADA: aparecio una bloqueante despues de cargar la vista', async () => {
    const f3 = mock.estado.folios.get('ONB-2026-000003')!
    f3.alertas_expediente[0].aplica = false // EXP-001 ya descartada: se puede aprobar
    const u = await abrir('ONB-2026-000003')
    expect(aprobar().disabled).toBe(false)
    f3.alertas_expediente.push({ ...f3.alertas_expediente[0], id: 'alr-nueva', aplica: null, mensaje: 'Falta otro documento' })
    await u.click(aprobar())
    await u.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Sí, aprobar' }))
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.DECISION_BLOQUEADA))
    await waitFor(() => expect(screen.getByRole('note').textContent).toContain('Falta otro documento'))
    expect(aprobar().disabled).toBe(true)
  })
})
