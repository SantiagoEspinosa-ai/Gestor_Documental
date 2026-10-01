// Control de roles en la UI (la API vuelve a comprobarlo).
import { expect, test } from '@playwright/test'
import { abrirFolio, entrar } from './ayudas'

test('admin: ve la lista y el expediente con el original, pero sin acciones del revisor', async ({ page }) => {
  await entrar(page, 'admin.demo')
  await expect(page.getByRole('link', { name: 'ONB-2026-000001', exact: true })).toBeVisible()
  await abrirFolio(page, 'ONB-2026-000001')
  await expect(page.getByTitle('Original: pasaporte_vencido_escaneado.pdf')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Corregir / })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /: (aplica|falso positivo)$/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Confirmar clasificación' })).toHaveCount(0)
})

test('integrador: sin lista de folios; abre un folio por su numero y no ve el original', async ({ page }) => {
  await entrar(page, 'integrador.demo')
  await expect(page.getByRole('link', { name: 'ONB-2026-000001', exact: true })).toHaveCount(0)
  await expect(page.getByRole('table')).toHaveCount(0)
  await page.getByLabel('Número de folio').fill('ONB-2026-000002')
  await page.getByLabel('Número de folio').press('Enter')
  // El integrador abre el folio en la carga de documentos; desde ahi, el expediente
  await expect(page.getByRole('heading', { name: /Carga de documentos — ONB-2026-000002/ })).toBeVisible()
  await page.getByRole('link', { name: 'Ver expediente' }).click()
  await expect(page.getByRole('heading', { name: /Expediente ONB-2026-000002/ })).toBeVisible()
  await expect(page.getByText('Tu rol no puede ver el original del documento.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
})
