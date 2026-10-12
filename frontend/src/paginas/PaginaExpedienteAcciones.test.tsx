// @vitest-environment jsdom
// Acciones del revisor en el expediente (bloque H): solo rol revisor y folio abierto. Datos ficticios del mock.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MS_HASTA_COMPLETADO, nuevaAlerta } from '../mocks/logica'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { abrirDocumento, esperarExpediente, montarExpediente, volverALaLista } from '../pruebas/expediente'
import { MENSAJES_ERROR } from '../utilidades/mensajes'
import { MOTIVO_ANIO, MOTIVO_OBLIGATORIO } from '../utilidades/valores'

const mock = usarServidorMock()

const PASAPORTE = 'pasaporte_vencido_escaneado.pdf'
const CREDENCIAL = 'credencial_elector_vencido_foto.jpg'

async function abrir(folio: string, usuario: 'revisor.demo' | 'admin.demo' | 'integrador.demo' = 'revisor.demo') {
  await entrarComo(usuario)
  montarExpediente(`/folios/${folio}`)
  await esperarExpediente(folio)
  return userEvent.setup()
}
const fila = (campo: string) => within(screen.getByRole('region', { name: 'Datos leídos' })).getByRole('rowheader', { name: campo }).closest('tr')!
const aviso = () => screen.getByTestId('aviso')
const folioMock = (folio: string) => mock.estado.folios.get(folio)!
const aprobar = () => screen.getByRole('button', { name: 'Aprobar' }) as HTMLButtonElement
const posts = (ruta: string) => mock.peticiones.filter((p) => p === ruta).length

describe('acciones del revisor', () => {
  it('un campo obligatorio no se puede guardar vacío: botón deshabilitado y motivo visible, sin PATCH', async () => {
    const u = await abrir('ONB-2026-000001') // pasaporte: nombre_completo es obligatorio
    await abrirDocumento(u, PASAPORTE)
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
    await abrirDocumento(u, CREDENCIAL)
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
    expect(within(fila('Vigencia')).getByText('Corregido por ti (antes: 2029)')).toBeTruthy()
  })

  it('corrige un dato mostrando el valor anterior; vaciar un opcional lo deja "No detectado" y se puede volver a escribir', async () => {
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, PASAPORTE)
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Corregir Sexo' }))
    expect(within(fila('Sexo')).getByText('M')).toBeTruthy() // "Valor actual: M"
    const entrada = within(fila('Sexo')).getByLabelText('Nuevo valor de Sexo')
    await u.clear(entrada)
    await u.type(entrada, 'F')
    await u.click(within(fila('Sexo')).getByRole('button', { name: 'Guardar corrección' }))
    await waitFor(() => expect(aviso().textContent).toBe('Sexo corregido.'))
    expect(within(fila('Sexo')).getByText('F')).toBeTruthy()
    expect(within(fila('Sexo')).getByText('Corregido por ti (antes: M)')).toBeTruthy()

    await u.click(within(fila('Nacionalidad')).getByRole('button', { name: 'Corregir Nacionalidad' }))
    await u.clear(within(fila('Nacionalidad')).getByLabelText('Nuevo valor de Nacionalidad'))
    await u.click(within(fila('Nacionalidad')).getByRole('button', { name: 'Guardar corrección' }))
    await waitFor(() => expect(within(fila('Nacionalidad')).getByText('No detectado · míralo en el original')).toBeTruthy())
    expect(within(fila('Nacionalidad')).getByText('Corregido por ti (antes: UTOPICA)')).toBeTruthy()
    // Sin valor: el boton pasa a "Escribir el valor" (la misma llamada)
    expect(within(fila('Nacionalidad')).getByRole('button', { name: 'Escribir el valor de Nacionalidad' }).textContent).toContain('Escribir el valor')
    const pasaporte = folioMock('ONB-2026-000001').documentos[0]
    expect(pasaporte.correcciones.at(-1)).toMatchObject({ campo: 'nacionalidad', valor_nuevo: null })
  })

  it('una corrección de otra persona dice quién la hizo', async () => {
    folioMock('ONB-2026-000001').documentos[0].correcciones.push(
      { campo: 'sexo', valor_anterior: 'F', valor_nuevo: 'M', usuario: 'otro.revisor', fecha: '2026-10-01T09:00:00Z' })
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, PASAPORTE)
    expect(within(fila('Sexo')).getByText('Corregido por otro.revisor (antes: F)')).toBeTruthy()
  })

  it('cambia el tipo: vuelve a analizarse y el sondeo sigue el nuevo análisis', async () => {
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, CREDENCIAL)
    expect(screen.queryByLabelText('Tipo documental correcto')).toBeNull() // plegado tras "Cambiar tipo"
    await u.click(screen.getByRole('button', { name: 'Cambiar tipo' }))
    await u.selectOptions(screen.getByLabelText('Tipo documental correcto'), 'comprobante_domicilio')
    expect(screen.getByText(/se volverá a analizar/)).toBeTruthy()
    await u.click(screen.getByRole('button', { name: 'Confirmar clasificación' }))
    const id = '00000000-0000-4000-8000-000001000002'
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).toBe('en_proceso'))
    expect(aviso().textContent).toBe('Clasificación confirmada.')
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).not.toBe('en_proceso'))
  })

  it('EXP-002 se ve en los avisos del documento (no en los del expediente) y no impide aprobar', async () => {
    const folio = folioMock('ONB-2026-000003')
    folio.alertas_expediente.forEach((a) => { a.aplica = false; a.resuelta_por_revisor = true }) // sin la EXP-001 que bloquea
    folio.documentos[0].alertas_encontradas.push(nuevaAlerta(mock.estado, 'EXP-002',
      'Tipo de documento no previsto en el proceso: Credencial de elector', 'informativa', 'credencial_elector'))
    const u = await abrir('ONB-2026-000003')
    expect(within(screen.getByRole('region', { name: 'Alertas del expediente' })).queryByText('EXP-002')).toBeNull()
    expect(aprobar().disabled).toBe(false)
    expect(screen.queryByRole('note')?.textContent ?? '').not.toContain('EXP-002')
    await abrirDocumento(u, 'credencial_elector_sano_digital.pdf')
    const delDocumento = screen.getByRole('region', { name: 'Avisos de este documento' })
    const exp002 = within(delDocumento).getByText('EXP-002').closest('li')!.textContent!
    expect(exp002).toContain('Tipo de documento no previsto en el proceso: Credencial de elector')
    expect(exp002).toContain('Informativa')
  })

  it('"No, es un falso aviso" en una alerta del expediente, con comentario, y entonces se puede aprobar con confirmación', async () => {
    const u = await abrir('ONB-2026-000003')
    expect(aprobar().disabled).toBe(true)
    const nota = screen.getByRole('note')
    expect(nota.textContent).toContain('EXP-001')
    const expediente = screen.getByRole('region', { name: 'Alertas del expediente' })
    expect(within(expediente).getByText('¿Es un problema real del documento?')).toBeTruthy()
    await u.type(within(expediente).getByLabelText('Comentario sobre EXP-001'), 'Llega por otra via')
    await u.click(within(expediente).getByRole('button', { name: 'EXP-001: no, es un falso aviso' }))
    await waitFor(() => expect(aviso().textContent).toBe('Alerta EXP-001 revisada.'))
    const revisada = within(screen.getByRole('region', { name: 'Alertas del expediente' })).getByText('EXP-001').closest('li')!.textContent!
    expect(revisada).toContain('Revisado: Falso positivo')
    expect(revisada).toContain('“Llega por otra via”')
    expect(revisada).toContain('revisor.demo')

    expect(aprobar().disabled).toBe(false)
    await u.type(screen.getByLabelText('Comentario de la decisión'), 'Revisado a mano')
    await u.click(aprobar())
    const dialogo = screen.getByRole('alertdialog', { name: 'Confirmar la decisión' })
    expect(posts('POST /folios/ONB-2026-000003/decision')).toBe(0) // nada sin confirmar
    await u.click(within(dialogo).getByRole('button', { name: 'Sí, aprobar' }))
    await waitFor(() => expect(aviso().textContent).toBe('Folio aprobado.'))
    expect(within(screen.getByTestId('seccion-decision')).getByRole('status').textContent).toContain('Decisión: Aprobado · “Revisado a mano”')
    expect(screen.getByTestId('fase-decision').textContent).toContain('Aprobado')
    // Cerrado: ya no hay acciones
    expect(screen.queryByRole('region', { name: 'Decisión del revisor' })).toBeNull()
    expect(screen.queryByRole('button', { name: /falso aviso/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Cambiar la revisión/ })).toBeNull()
  })

  it('una alerta ya revisada se puede cambiar ("Cambiar la revisión")', async () => {
    const u = await abrir('ONB-2026-000003')
    const expediente = () => screen.getByRole('region', { name: 'Alertas del expediente' })
    await u.click(within(expediente()).getByRole('button', { name: 'EXP-001: no, es un falso aviso' }))
    await waitFor(() => expect(within(expediente()).getByText(/Revisado: Falso positivo/)).toBeTruthy())
    await u.click(within(expediente()).getByRole('button', { name: 'Cambiar la revisión de EXP-001' }))
    await u.click(within(expediente()).getByRole('button', { name: 'EXP-001: sí, es un problema' }))
    await waitFor(() => expect(within(expediente()).getByText(/Revisado: Aplica/)).toBeTruthy())
  })

  it('aprobar deshabilitado mientras una bloqueante aplique; rechazar pide confirmación y se puede cancelar', async () => {
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, PASAPORTE)
    const avisos = screen.getByRole('region', { name: 'Avisos de este documento' })
    await u.click(within(avisos).getByRole('button', { name: 'REG-vigencia_documento: sí, es un problema' }))
    await waitFor(() => expect(within(within(avisos).getByText('REG-vigencia_documento').closest('li')!).getByText('Aplica (confirmada por el revisor)')).toBeTruthy())
    // La decision no esta en el detalle: esta al final de la lista
    expect(screen.queryByRole('region', { name: 'Decisión del revisor' })).toBeNull()
    await volverALaLista(u)
    expect(aprobar().disabled).toBe(true) // aplica=true confirma el problema: solo se puede rechazar
    expect(screen.getByRole('note').textContent).toContain('REG-vigencia_documento')
    expect(screen.getByTestId('estado-revision').textContent).toContain('solo puedes rechazar')

    await u.click(screen.getByRole('button', { name: 'Rechazar' }))
    await u.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancelar' }))
    expect(posts('POST /folios/ONB-2026-000001/decision')).toBe(0)
    await u.click(screen.getByRole('button', { name: 'Rechazar' }))
    await u.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Sí, rechazar' }))
    await waitFor(() => expect(aviso().textContent).toBe('Folio rechazado.'))
    expect(folioMock('ONB-2026-000001')).toMatchObject({ estado_general: 'rechazado', decision_humana: 'rechazar', usuario_decision: 'revisor.demo' })
  })

  it('solo el revisor y con el folio abierto: admin, integrador y un folio cerrado no ven acciones', async () => {
    for (const [folio, usuario, nombre] of [
      ['ONB-2026-000001', 'admin.demo', PASAPORTE], ['ONB-2026-000001', 'integrador.demo', PASAPORTE],
      ['ONB-2026-000004', 'revisor.demo', 'pasaporte_sano_digital.pdf'],
    ] as const) {
      const u = await abrir(folio, usuario)
      expect(screen.queryByRole('region', { name: 'Decisión del revisor' }), `${usuario} ${folio}`).toBeNull()
      expect(screen.queryByRole('button', { name: /falso aviso$|es un problema$/ })).toBeNull()
      await abrirDocumento(u, nombre)
      expect(screen.queryByRole('button', { name: /^Corregir |^Escribir el valor/ })).toBeNull()
      expect(screen.queryByRole('button', { name: /falso aviso$|es un problema$/ })).toBeNull()
      expect(screen.queryByRole('button', { name: 'Cambiar tipo' })).toBeNull()
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

  it('FOLIO_CERRADO: otro revisor lo decidió; pasa a solo lectura', async () => {
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, PASAPORTE)
    Object.assign(folioMock('ONB-2026-000001'), { estado_general: 'rechazado', decision_humana: 'rechazar', usuario_decision: 'otro.revisor' })
    await corregirSexo(u)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.FOLIO_CERRADO))
    expect(aviso().getAttribute('role')).toBe('alert')
    await waitFor(() => expect(screen.queryByRole('button', { name: /^Corregir / })).toBeNull())
    expect(screen.getByText(/Folio cerrado: solo lectura/)).toBeTruthy()
  })

  it('DOCUMENTO_EN_PROCESO y DOCUMENTO_CON_ERROR: el documento cambió de estado', async () => {
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, PASAPORTE)
    const pasaporte = folioMock('ONB-2026-000001').documentos[0]
    pasaporte.estado_analisis = 'procesando'
    await corregirSexo(u)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.DOCUMENTO_EN_PROCESO))
    await waitFor(() => expect(screen.getByTestId(`semaforo-${pasaporte.identificador_unico_documento}`).getAttribute('data-color')).toBe('en_proceso'))

    cleanup()
    pasaporte.estado_analisis = 'completado'
    const u2 = await abrir('ONB-2026-000001')
    await abrirDocumento(u2, PASAPORTE)
    folioMock('ONB-2026-000001').documentos[0].estado_analisis = 'error'
    await corregirSexo(u2)
    await waitFor(() => expect(aviso().textContent).toContain(MENSAJES_ERROR.DOCUMENTO_CON_ERROR))
    await waitFor(() => expect(screen.getByText('El análisis de este documento falló.')).toBeTruthy())
  })

  it('DECISION_BLOQUEADA: apareció una bloqueante después de cargar la vista', async () => {
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
