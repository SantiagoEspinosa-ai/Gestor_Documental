// @vitest-environment jsdom
// Pantalla de procesos en solo lectura (H8): solo admin, nombres visibles de los tipos y webhook sin la URL.
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { error } from '../mocks/respuestas'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import type { ProcesoCompleto } from '../tipos/contrato'
import { describirWebhook } from '../utilidades/procesos'

const mock = usarServidorMock()

const fila = (proceso: string) => screen.getByRole('rowheader', { name: proceso }).closest('tr')!

function conProcesos(procesos: ProcesoCompleto[]) {
  mock.servidor.use(http.get('*/api/v1/procesos', () => HttpResponse.json(procesos)))
}

const ALTA: ProcesoCompleto = {
  nombre: 'alta_ficticia', prefijo_folio: 'ALT', tipos_requeridos: ['pasaporte'], tipos_opcionales: [],
  permitir_antecedentes: false, caducidad_antecedentes_dias: 30, modelos: null,
  webhook_url: 'https://usuario:clave@hooks.ejemplo.test/ruta/secreta?token=abc',
}

describe('pantalla de procesos (admin)', () => {
  it('lista los procesos con los nombres visibles de los tipos y la nota de solo lectura', async () => {
    await entrarComo('admin.demo')
    montar('/procesos')
    expect(await screen.findByText('Cargando procesos…')).toBeTruthy()
    const onboarding = within(await screen.findByRole('rowheader', { name: 'onboarding' }).then((c) => c.closest('tr')!))
    expect(onboarding.getByText('ONB')).toBeTruthy()
    expect(onboarding.getByText('Credencial de elector, Comprobante de domicilio')).toBeTruthy()
    expect(onboarding.getByText('Pasaporte')).toBeTruthy()
    expect(onboarding.getByText('Sí')).toBeTruthy()
    expect(onboarding.getByText('365 días')).toBeTruthy()
    expect(onboarding.getByText('default')).toBeTruthy()
    expect(onboarding.getByText('Sin webhook')).toBeTruthy() // webhook_url null en los datos del mock
    expect(screen.getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Proceso', 'Prefijo de folio', 'Tipos requeridos', 'Tipos opcionales', 'Antecedentes',
      'Caducidad de antecedentes', 'Modelos', 'Webhook'])
    expect(screen.getByText(/Solo lectura: los procesos se cambian en config\/procesos.yaml/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Procesos' })).toBeTruthy()
  })

  it('del webhook solo muestra el host: ni la ruta, ni la query, ni las credenciales', async () => {
    conProcesos([ALTA])
    await entrarComo('admin.demo')
    montar('/procesos')
    const alta = within(await screen.findByRole('rowheader', { name: 'alta_ficticia' }).then((c) => c.closest('tr')!))
    expect(alta.getByText('Configurado (hooks.ejemplo.test)')).toBeTruthy()
    expect(alta.getByText('Por defecto')).toBeTruthy() // modelos null
    expect(alta.getByText('No')).toBeTruthy()
    const html = document.body.innerHTML
    for (const fragmento of ['secreta', 'token', 'abc', 'usuario:clave', '/ruta']) expect(html).not.toContain(fragmento)
  })

  it('un tipo sin ficha se muestra con su nombre técnico', async () => {
    conProcesos([{ ...ALTA, tipos_requeridos: ['tipo_sin_ficha'], webhook_url: null }])
    await entrarComo('admin.demo')
    montar('/procesos')
    await screen.findByRole('rowheader', { name: 'alta_ficticia' })
    expect(within(fila('alta_ficticia')).getByText('tipo_sin_ficha')).toBeTruthy()
    expect(within(fila('alta_ficticia')).getByText('Sin webhook')).toBeTruthy()
  })

  it('sin procesos: mensaje de lista vacía', async () => {
    conProcesos([])
    await entrarComo('admin.demo')
    montar('/procesos')
    expect(await screen.findByText('No hay procesos configurados.')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('error de la API: el mensaje del código', async () => {
    mock.servidor.use(http.get('*/api/v1/procesos', () => error('ERROR_INTERNO', 'detalle interno')))
    await entrarComo('admin.demo')
    montar('/procesos')
    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toBe('Error interno del servidor. Inténtalo de nuevo más tarde.') // nunca el detalle
    expect(screen.queryByRole('table')).toBeNull()
  })

  it.each(['revisor.demo', 'integrador.demo'] as const)('%s: "Sin permiso", sin enlace y sin pedir los procesos', async (usuario) => {
    await entrarComo(usuario)
    montar('/procesos')
    expect(await screen.findByRole('heading', { name: 'Sin permiso' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Procesos' })).toBeNull()
    expect(mock.peticiones).not.toContain('GET /procesos')
  })
})

describe('describirWebhook', () => {
  it.each([
    [null, 'Sin webhook'],
    ['', 'Sin webhook'],
    ['https://hooks.ejemplo.test:8443/x?token=1', 'Configurado (hooks.ejemplo.test:8443)'],
    ['no es una url', 'Configurado'],
  ])('%s -> %s', (url, esperado) => {
    expect(describirWebhook(url)).toBe(esperado)
  })
})
