// "Mostrar" de un dato sensible (H17, ADR-010 A4): los mocks enmascaran como la API y revelan con
// POST /documentos/{id}/revelar.
import { expect, test } from '@playwright/test'
import { abrirFolio, entrar } from './ayudas'

test('revisor: muestra y oculta la CURP de la credencial', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000001')
  await page.getByRole('button', { name: /credencial_elector_vencido_foto\.jpg/ }).click()
  const curp = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Curp', exact: true }) })
  const valor = curp.locator('td').first()
  await expect(valor).toContainText('****')
  const enmascarado = (await valor.textContent())!

  await curp.getByRole('button', { name: 'Mostrar Curp' }).click()
  await expect(curp.getByRole('button', { name: 'Ocultar Curp' })).toBeVisible()
  await expect(valor).not.toContainText('****')
  // CURP ficticia completa de 18 caracteres, con los 4 ultimos de la mascara
  const completo = (await valor.textContent())!.match(/[A-Z]{4}\d{6}[HM][A-Z0-9]{7}/)![0]
  expect(enmascarado).toContain(completo.slice(-4))

  await curp.getByRole('button', { name: 'Ocultar Curp' }).click()
  await expect(valor).toContainText('****')
  await expect(valor).not.toContainText(completo)
  await expect(curp.getByRole('button', { name: 'Mostrar Curp' })).toBeVisible()
})
