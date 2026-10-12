// @vitest-environment jsdom
// Estructura de la pagina del expediente (feat/expediente-intuitivo): leyenda, rejilla con semaforo,
// comparaciones, barra de fase, pestanas y la decision como ultima seccion. Datos ficticios del mock.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import { abrirDocumento, esperarExpediente, montarExpediente, rejilla, tarjeta } from '../pruebas/expediente'

const mock = usarServidorMock()

async function abrir(folio: string, usuario: 'revisor.demo' | 'admin.demo' | 'integrador.demo' = 'revisor.demo') {
  await entrarComo(usuario)
  montarExpediente(`/folios/${folio}`)
  await esperarExpediente(folio)
  return userEvent.setup()
}
const color = (nombre: string) => within(tarjeta(nombre)).getByTestId(/^semaforo-/).getAttribute('data-color')

describe('lista de documentos', () => {
  it('leyenda de los colores, con el texto de cada uno', async () => {
    await abrir('ONB-2026-000001')
    const leyenda = screen.getByRole('region', { name: 'Qué significan los colores' })
    expect(leyenda.textContent).toContain('Verde: Se leyeron todos los datos.')
    expect(leyenda.textContent).toContain('Amarillo: falta algo o hay un aviso; revísalo o tenlo en cuenta al decidir.')
    expect(leyenda.textContent).toContain('Rojo: No se pudo leer nada o hubo un error; vuelve a subirlo.')
  })

  it('rejilla con todos los documentos y su semáforo (icono + texto); "Volver a subir" en los rojos', async () => {
    await abrir('ONB-2026-000003')
    expect(within(rejilla()).getAllByRole('article')).toHaveLength(4)
    expect(color('credencial_elector_sano_digital.pdf')).toBe('verde')
    expect(color('pasaporte_sano_foto.jpg')).toBe('rojo')
    expect(color('comprobante_domicilio_sano_escaneado.pdf')).toBe('rojo')
    expect(color('pasaporte_sano_escaneado.pdf')).toBe('amarillo')
    for (const semaforo of within(rejilla()).getAllByTestId(/^semaforo-/)) {
      expect(semaforo.querySelector('svg'), 'icono').toBeTruthy()
      expect(semaforo.textContent!.trim().length, 'texto').toBeGreaterThan(0)
    }
    expect(within(tarjeta('pasaporte_sano_foto.jpg')).getByRole('link', { name: /Volver a subir/ })).toBeTruthy()
    expect(within(tarjeta('credencial_elector_sano_digital.pdf')).queryByRole('link', { name: /Volver a subir/ })).toBeNull()
    expect(within(tarjeta('credencial_elector_sano_digital.pdf')).getByRole('link', { name: /^Abrir y revisar / })).toBeTruthy()
  })

  it('folio 1: los avisos sin revisar del documento lo ponen en amarillo; sin avisos, verde; el retirado, gris', async () => {
    await abrir('ONB-2026-000001')
    const insignia = (nombre: string) => within(tarjeta(nombre)).getByTestId(/^semaforo-/)
    // Pasaporte: REG-vigencia_documento (bloqueante) y REG-vigencia_proxima (preventiva) sin revisar; las VAL-003 son informativas
    expect(insignia('pasaporte_vencido_escaneado.pdf').getAttribute('data-color')).toBe('amarillo')
    expect(insignia('pasaporte_vencido_escaneado.pdf').textContent).toBe('1 aviso impide aprobar · 1 aviso por revisar')
    expect(insignia('credencial_elector_vencido_foto.jpg').textContent).toBe('1 aviso por revisar') // VAL-002
    const comprobantes = within(rejilla()).getAllByRole('article').filter((a) => a.textContent!.includes('comprobante_domicilio_vencido_digital.pdf'))
    expect(comprobantes.map((a) => within(a).getByTestId(/^semaforo-/).textContent)).toEqual(['Todo detectado', 'Retirado'])
  })

  it('con solo avisos confirmados no bloqueantes: amarillo en el documento y "Todo revisado. Ya puedes decidir"', async () => {
    const folio = mock.estado.folios.get('ONB-2026-000002')!
    folio.alertas_expediente.forEach((a) => { a.aplica = false; a.resuelta_por_revisor = true }) // CMP-001 como falso aviso
    folio.documentos[2].estado_analisis = 'completado' // sin documentos en analisis
    const credencial = folio.documentos[0]
    credencial.alertas_encontradas.push({ ...folio.alertas_expediente[0], id: 'alr-confirmada', codigo: 'VAL-002', severidad: 'preventiva',
      campo: 'curp', aplica: true, resuelta_por_revisor: true })
    await abrir('ONB-2026-000002')
    expect(within(tarjeta('credencial_elector_domicilio_distinto_escaneado.pdf')).getByTestId(/^semaforo-/).textContent)
      .toBe('Aviso confirmado · no impide aprobar')
    expect(screen.getByTestId('estado-revision').textContent).toBe('Todo revisado. Ya puedes decidir.')
  })

  it('en proceso: gris con la fase corta (ADR-014)', async () => {
    mock.estado.folios.get('ONB-2026-000002')!.documentos[2].fase_analisis = 'ocr'
    await abrir('ONB-2026-000002')
    const semaforo = within(tarjeta('pasaporte_domicilio_distinto_digital.pdf')).getByTestId(/^semaforo-/)
    expect(semaforo.getAttribute('data-color')).toBe('en_proceso')
    expect(semaforo.textContent).toBe('Leyendo el texto')
  })

  it('"Volver a subir" solo para quien puede subir (integrador y revisor) y nunca con el folio cerrado', async () => {
    await abrir('ONB-2026-000003', 'admin.demo')
    expect(within(tarjeta('pasaporte_sano_foto.jpg')).queryByRole('link', { name: /Volver a subir/ })).toBeNull()
    expect(within(tarjeta('pasaporte_sano_foto.jpg')).getByText('No se pudo leer')).toBeTruthy() // el rojo con su texto
    cleanup()
    // El integrador solo ve sus folios (ADR-012): un documento en error del folio 2
    mock.estado.folios.get('ONB-2026-000002')!.documentos[1].estado_analisis = 'error'
    await abrir('ONB-2026-000002', 'integrador.demo')
    expect(within(tarjeta('comprobante_domicilio_domicilio_distinto_foto.jpg')).getByRole('link', { name: /Volver a subir/ })).toBeTruthy()
    cleanup()
    const folio = mock.estado.folios.get('ONB-2026-000003')!
    Object.assign(folio, { estado_general: 'rechazado', decision_humana: 'rechazar', usuario_decision: 'revisor.demo' })
    await abrir('ONB-2026-000003', 'revisor.demo')
    expect(within(tarjeta('pasaporte_sano_foto.jpg')).queryByRole('link', { name: /Volver a subir/ })).toBeNull()
  })
})

describe('comparaciones entre documentos', () => {
  it('si coinciden: solo el campo y "Coincide", sin valores; arriba "X de Y coinciden"', async () => {
    await abrir('ONB-2026-000001')
    expect(screen.getByTestId('resumen-comparaciones').textContent).toBe('3 de 3 coinciden')
    const nombre = screen.getByTestId('comparacion-nombre_completo')
    expect(within(nombre).getByText('Coincide')).toBeTruthy()
    expect(nombre.querySelector('dl')).toBeNull()
    expect(nombre.textContent).not.toContain('ANA')
  })

  it('si no coinciden: "No coincide entre <Tipo A> y <Tipo B>" y los valores de cada documento', async () => {
    await abrir('ONB-2026-000002')
    expect(screen.getByTestId('resumen-comparaciones').textContent).toBe('0 de 1 coinciden')
    const domicilio = screen.getByTestId('comparacion-domicilio')
    expect(within(domicilio).getByText('No coincide')).toBeTruthy()
    expect(within(domicilio).getByText('No coincide entre Credencial de elector y Comprobante de domicilio')).toBeTruthy()
    expect(domicilio.querySelectorAll('dd')).toHaveLength(2)
  })
})

describe('decisión al final', () => {
  it('la decisión es la última sección; antes, las alertas del expediente y la línea de estado', async () => {
    await abrir('ONB-2026-000002')
    const decision = screen.getByTestId('seccion-decision')
    expect(decision.nextElementSibling).toBeNull()
    const alertas = screen.getByRole('region', { name: 'Alertas del expediente' })
    expect(alertas.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Comparaciones entre documentos' }).compareDocumentPosition(decision)
      & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(decision).getByRole('region', { name: 'Decisión del revisor' })).toBeTruthy()
    // CMP-001 sin revisar (la VAL-004 informativa no cuenta)
    expect(within(decision).getByTestId('estado-revision').textContent).toBe('Antes de decidir: te queda 1 cosa por revisar.')
  })

  it('al revisar lo pendiente: "Todo revisado. Ya puedes decidir"', async () => {
    const u = await abrir('ONB-2026-000002')
    await u.click(within(screen.getByRole('region', { name: 'Alertas del expediente' })).getByRole('button', { name: 'CMP-001: no, es un falso aviso' }))
    await waitFor(() => expect(screen.getByTestId('estado-revision').textContent).toBe('Todo revisado. Ya puedes decidir.'))
  })

  it('en el detalle de un documento no hay decisión', async () => {
    const u = await abrir('ONB-2026-000002')
    await abrirDocumento(u, 'credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(screen.queryByTestId('seccion-decision')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Decisión del revisor' })).toBeNull()
  })

  it('admin e integrador ven el estado pero no deciden', async () => {
    await abrir('ONB-2026-000002', 'admin.demo')
    const decision = screen.getByTestId('seccion-decision')
    expect(within(decision).getByTestId('estado-revision')).toBeTruthy()
    expect(within(decision).getByText('La decisión la toma un revisor.')).toBeTruthy()
    expect(within(decision).queryByRole('region', { name: 'Decisión del revisor' })).toBeNull()
  })
})

describe('barra de fase del expediente', () => {
  const actual = () => screen.getAllByRole('listitem').find((li) => li.getAttribute('aria-current') === 'step')

  it('análisis: algún documento en proceso; los anteriores hechos y los siguientes pendientes', async () => {
    await abrir('ONB-2026-000002')
    expect(actual()?.getAttribute('data-testid')).toBe('fase-analisis')
    expect(actual()!.textContent).toContain('Fase actual')
    expect(screen.getByTestId('fase-carga').textContent).toContain('Hecho')
    expect(screen.getByTestId('fase-revision').textContent).toContain('Pendiente')
  })

  it('revisión: en revisión y nada en proceso', async () => {
    await abrir('ONB-2026-000001')
    expect(actual()?.getAttribute('data-testid')).toBe('fase-revision')
  })

  it('decisión: los 4 hechos, con "Aprobado", fecha y usuario; ninguno es el actual', async () => {
    await abrir('ONB-2026-000004')
    expect(actual()).toBeUndefined()
    const decision = screen.getByTestId('fase-decision').textContent!
    expect(decision).toContain('Aprobado')
    expect(decision).toContain('revisor.demo')
    expect(decision).toMatch(/\d{2}\/\d{2}\/\d{4}/)
  })

  it('carga: el folio no tiene documentos', async () => {
    await entrarComo('revisor.demo')
    const token = JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!).token as string
    const { folio } = await (await fetch('http://localhost:8000/api/v1/folios', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ proceso: 'onboarding' }),
    })).json()
    montarExpediente(`/folios/${folio}`)
    await esperarExpediente(folio)
    expect(actual()?.getAttribute('data-testid')).toBe('fase-carga')
    expect(within(screen.getByRole('region', { name: 'Documentos del folio' })).getByText(/Aún no hay documentos/)).toBeTruthy()
  })
})
