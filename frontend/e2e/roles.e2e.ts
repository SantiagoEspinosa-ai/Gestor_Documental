// Control de roles en la UI (la API vuelve a comprobarlo).
import { expect, test } from '@playwright/test'
import { abrirDocumento, abrirFolio, entrar } from './ayudas'

test('admin: ve la lista y el expediente con el original, pero sin acciones del revisor', async ({ page }) => {
  await entrar(page, 'admin.demo')
  await expect(page.getByRole('link', { name: 'ONB-2026-000001', exact: true })).toBeVisible()
  await abrirFolio(page, 'ONB-2026-000001')
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
  await expect(page.getByText('La decisión la toma un revisor.')).toBeVisible()
  await abrirDocumento(page, 'pasaporte_vencido_escaneado.pdf')
  await expect(page.getByTitle('Original: pasaporte_vencido_escaneado.pdf')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Corregir |^Escribir el valor/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /: (sí, es un problema|no, es un falso aviso)$/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Cambiar tipo' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Confirmar clasificación' })).toHaveCount(0)
})

test('integrador: sin lista de folios; abre un folio por su numero y no ve el original', async ({ page }) => {
  await entrar(page, 'integrador.demo')
  await expect(page.getByRole('link', { name: 'ONB-2026-000001', exact: true })).toHaveCount(0)
  await expect(page.getByRole('table')).toHaveCount(0)
  await page.getByLabel('Número de folio').fill('ONB-2026-000002')
  await page.getByLabel('Número de folio').press('Enter')
  // El integrador abre el folio en la carga de documentos; desde ahi, el expediente
  await expect(page.getByRole('heading', { name: 'Carga de documentos' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Expediente ONB-2026-000002' })).toBeVisible()
  await page.getByRole('navigation', { name: 'Secciones del expediente' }).getByRole('link', { name: /^Documentos · / }).click()
  await abrirDocumento(page, 'credencial_elector_domicilio_distinto_escaneado.pdf')
  await expect(page.getByText('Tu rol no puede ver el original del documento.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
})

test('integrador: un folio de otro integrador no existe para el (ADR-012)', async ({ page }) => {
  await entrar(page, 'integrador.demo')
  await page.getByLabel('Número de folio').fill('ONB-2026-000003')
  await page.getByLabel('Número de folio').press('Enter')
  await expect(page.getByRole('alert')).toContainText('El folio no existe.')
})
