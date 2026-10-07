// @vitest-environment jsdom
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { describe, expect, it } from 'vitest'
import { corregirDatos } from '../api/revision'
import { error } from '../mocks/respuestas'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'

const mock = usarServidorMock()

const filas = () => screen.getAllByRole('row').slice(1) // sin la cabecera
const folios = () => filas().map((f) => within(f).queryByRole('link')?.textContent ?? null)
const consultasAuditoria = () => mock.consultas.filter((c) => c.startsWith('GET /auditoria'))

describe('pantalla de auditoría (admin)', () => {
  it('lista 50 por página, del más reciente al más antiguo, con el total', async () => {
    await entrarComo('admin.demo') // su login es la entrada mas reciente
    montar('/auditoria')
    expect(await screen.findByText('Cargando auditoría…')).toBeTruthy()
    expect(await screen.findByText('Página 1 de 1 (34 entradas)')).toBeTruthy()
    expect(consultasAuditoria()).toEqual(['GET /auditoria?pagina=1&tamano_pagina=50'])
    expect(screen.getByRole('table').getAttribute('aria-busy')).toBe('false')
    expect(filas()).toHaveLength(34)
    expect(within(filas()[0]).getByRole('rowheader').textContent).toContain('Inicio de sesión')
    expect(filas()[0].textContent).toContain('admin.demo')
    expect(filas()[0].textContent).toContain('Acceso correcto')
    expect(within(filas()[33]).getByRole('rowheader').textContent).toContain('Folio creado') // la primera de todas
    const cabeceras = screen.getAllByRole('columnheader').map((c) => c.textContent)
    expect(cabeceras).toEqual(['Fecha', 'Usuario', 'Acción', 'Folio', 'Documento', 'Detalle', 'Modelo'])
  })

  it('pagina con Anterior y Siguiente y cambia el tamaño de página', async () => {
    await entrarComo('admin.demo')
    montar('/auditoria?tamano_pagina=20')
    expect(await screen.findByText('Página 1 de 2 (34 entradas)')).toBeTruthy()
    expect(filas()).toHaveLength(20)
    const u = userEvent.setup()
    expect((screen.getByRole('button', { name: 'Anterior' }) as HTMLButtonElement).disabled).toBe(true)
    await u.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByText('Página 2 de 2 (34 entradas)')).toBeTruthy()
    expect(filas()).toHaveLength(14)
    expect((screen.getByRole('button', { name: 'Siguiente' }) as HTMLButtonElement).disabled).toBe(true)
    expect(consultasAuditoria()).toContain('GET /auditoria?pagina=2&tamano_pagina=20')
    // cambiar el tamano vuelve a la pagina 1
    await u.selectOptions(screen.getByLabelText('Entradas por página'), '100')
    expect(await screen.findByText('Página 1 de 1 (34 entradas)')).toBeTruthy()
    expect(consultasAuditoria().at(-1)).toBe('GET /auditoria?pagina=1&tamano_pagina=100')
  })

  it('filtra por folio (normalizado), enlaza al expediente y quita el filtro', async () => {
    await entrarComo('admin.demo')
    montar('/auditoria')
    await screen.findByText('Página 1 de 1 (34 entradas)')
    const u = userEvent.setup()
    await u.type(screen.getByLabelText('Folio'), ' onb-2026-000004 ')
    await u.click(screen.getByRole('button', { name: 'Filtrar' }))
    expect(await screen.findByText('Página 1 de 1 (9 entradas)')).toBeTruthy()
    expect(consultasAuditoria().at(-1)).toBe('GET /auditoria?folio=ONB-2026-000004&pagina=1&tamano_pagina=50')
    expect(new Set(folios())).toEqual(new Set(['ONB-2026-000004']))
    expect(within(filas()[0]).getByRole('link', { name: 'ONB-2026-000004' }).getAttribute('href')).toBe('/folios/ONB-2026-000004')
    expect(screen.getByText(/Mostrando solo el folio/).textContent).toContain('ONB-2026-000004')
    await u.click(screen.getByRole('button', { name: 'Quitar filtro' }))
    expect(await screen.findByText('Página 1 de 1 (34 entradas)')).toBeTruthy()
    expect((screen.getByLabelText('Folio') as HTMLInputElement).value).toBe('')
  })

  it('muestra el detalle legible por acción, sin JSON en bruto', async () => {
    await entrarComo('admin.demo')
    montar('/auditoria?folio=ONB-2026-000004')
    await screen.findByText('Página 1 de 1 (9 entradas)')
    const fila = (accion: string) => filas().filter((f) => within(f).getByRole('rowheader').textContent === accion)
    expect(fila('Decisión del folio')[0].textContent).toContain('Decisión: Aprobado')
    expect(fila('Decisión del folio')[0].textContent).toContain('revisor.demo')
    const subida = fila('Documento subido').at(-1)!
    expect(subida.textContent).toContain('SHA-256 44a92b42e7d1…')
    expect(subida.textContent).toContain('No duplicado')
    expect(subida.textContent).toContain('00000000…') // documento_id abreviado
    const procesado = fila('Documento analizado')[0]
    expect(procesado.textContent).toContain('Proveedor: ollama') // forma del PR #9: {proveedor, respaldo_usado}
    expect(procesado.textContent).toContain('Sin respaldo')
    expect(procesado.textContent).toContain('Sistema') // sin usuario: tarea en segundo plano
    expect(procesado.textContent).toMatch(/gemma4:e2b · extraccion_[a-z_]+@v3/) // un prompt por tipo, como el motor real
    expect(screen.getByRole('table').textContent).not.toMatch(/[{}"]/)
  })

  it('formatea correcciones, alertas y clasificación con la forma del PR #9', async () => {
    await entrarComo('admin.demo')
    const entradas = mock.estado.auditoria
    const base = { usuario: 'revisor.demo', folio: 'ONB-2026-000002', documento_id: null, modelo: null, version_prompt: null,
      creado_en: '2026-10-01T09:59:00Z' }
    entradas.push(
      { ...base, id: 900, accion: 'clasificacion_confirmada', detalle: { tipo: 'credencial_elector', reproceso: false } },
      { ...base, id: 901, accion: 'alerta_resuelta', detalle: { alerta_id: 'alr-000007', codigo: 'VAL-004', aplica: false } },
      // valor_nuevo no es de la forma de la API: si llegara, sale enmascarado
      { ...base, id: 902, accion: 'dato_corregido', detalle: { campos: ['curp', 'domicilio'], valor_nuevo: 'AEPA900101MDFXXX09' } },
    )
    montar('/auditoria?folio=ONB-2026-000002')
    const tabla = await screen.findByRole('table')
    await waitFor(() => expect(tabla.textContent).toContain('Tipo confirmado: Credencial de elector')) // nombre_visible
    expect(tabla.textContent).toContain('Sin volver a analizar')
    expect(tabla.textContent).toContain('Alerta VAL-004: falso positivo')
    expect(tabla.textContent).not.toContain('alr-000007') // el id interno no se enmascara: no se muestra
    expect(tabla.textContent).toContain('Campos: curp, domicilio')
    expect(tabla.textContent).toContain('valor nuevo: ****XX09')
    expect(tabla.textContent).not.toContain('AEPA900101MDFXXX09')
  })

  it('muestra las acciones hechas en la sesión con la forma real del mock (una corrección por PATCH)', async () => {
    await entrarComo('revisor.demo')
    const pasaporte = mock.estado.folios.get('ONB-2026-000001')!.documentos[0]
    await corregirDatos(pasaporte.identificador_unico_documento, { sexo: 'F', nacionalidad: null })
    await entrarComo('admin.demo')
    montar('/auditoria?folio=ONB-2026-000001')
    const tabla = await screen.findByRole('table')
    await waitFor(() => expect(tabla.textContent).toContain('Campos: nacionalidad, sexo'))
    expect(filas().filter((f) => within(f).getByRole('rowheader').textContent === 'Dato corregido')).toHaveLength(1)
  })

  it('estado vacío con un folio sin entradas', async () => {
    await entrarComo('admin.demo')
    montar('/auditoria?folio=ONB-2099-999999')
    expect(await screen.findByText('No hay entradas de auditoría del folio ONB-2099-999999.')).toBeTruthy()
    expect(screen.getByText('Página 1 de 1 (0 entradas)')).toBeTruthy()
  })

  it('422 PETICION_INVALIDA con un tamaño fuera de rango en la URL, con salida a la auditoría sin filtros', async () => {
    await entrarComo('admin.demo')
    montar('/auditoria?tamano_pagina=500')
    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain('Los datos enviados no son válidos.')
    expect(screen.queryByRole('table')).toBeNull()
    await userEvent.setup().click(within(alerta).getByRole('link', { name: 'Volver a la auditoría sin filtros' }))
    expect(await screen.findByText('Página 1 de 1 (34 entradas)')).toBeTruthy()
  })

  it('403 SIN_PERMISO de la API', async () => {
    await entrarComo('admin.demo')
    mock.servidor.use(http.get('*/api/v1/auditoria', () => error('SIN_PERMISO', 'El rol no tiene acceso')))
    montar('/auditoria')
    expect((await screen.findByRole('alert')).textContent).toContain('Tu rol no tiene permiso para esta acción.')
  })
})

describe('auditoría y roles', () => {
  it('el enlace de la cabecera solo lo ve el admin', async () => {
    await entrarComo('admin.demo')
    const { unmount } = montar('/folios')
    const nav = await screen.findByRole('navigation', { name: 'Principal' })
    expect(within(nav).getByRole('link', { name: 'Auditoría' }).getAttribute('href')).toBe('/auditoria')
    unmount()
    for (const usuario of ['revisor.demo', 'integrador.demo'] as const) {
      await entrarComo(usuario)
      const montado = montar('/folios')
      const navOtro = await screen.findByRole('navigation', { name: 'Principal' })
      await screen.findByTestId('usuario-actual')
      expect(within(navOtro).queryByRole('link', { name: 'Auditoría' })).toBeNull()
      montado.unmount()
    }
  })

  it.each(['revisor.demo', 'integrador.demo'] as const)('%s entra por URL: "Sin permiso" y no se pide la auditoría', async (usuario) => {
    await entrarComo(usuario)
    montar('/auditoria')
    expect(await screen.findByRole('heading', { name: 'Sin permiso' })).toBeTruthy()
    expect(mock.peticiones).not.toContain('GET /auditoria')
  })
})
