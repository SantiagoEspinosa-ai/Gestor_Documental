// Humo real (H6): controles del rol integrador en la UI contra la API real (la API los vuelve a comprobar).
import { expect, test } from '@playwright/test'
import { COMPROBANTE, entrar, esperarCompletado, exigirUsuarios, nuevoFolio, referenciaE2E, subir } from './ayudas'

test('integrador_roles: sin lista de folios, "Sin permiso" en auditoría y procesos, y sin ver el original', async ({ page }) => {
  exigirUsuarios('integrador')
  test.setTimeout(6 * 60_000)
  await entrar(page, 'integrador')

  // Sin lista de folios: abre uno por su numero
  await expect(page.getByLabel('Número de folio')).toBeVisible()
  await expect(page.getByRole('table')).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Auditoría' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Procesos' })).toHaveCount(0)

  for (const ruta of ['/auditoria', '/procesos']) {
    await page.goto(ruta)
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible()
  }

  // Su propio folio con un documento: en el expediente no puede ver el original
  await page.goto('/folios')
  const folio = await nuevoFolio(page, referenciaE2E())
  await subir(page, { [COMPROBANTE]: 'comprobante_domicilio' })
  await esperarCompletado(page, COMPROBANTE)
  await page.getByRole('link', { name: 'Ver expediente' }).click()
  await expect(page.getByRole('heading', { name: new RegExp(`Expediente ${folio}`) })).toBeVisible()
  await expect(page.getByText('Tu rol no puede ver el original del documento.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
})
