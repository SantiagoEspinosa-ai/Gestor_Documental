// Antecedentes del folio (H16, ADR-010 C): el folio 2 de los mocks tiene como antecedente el folio 4, cerrado y
// con la misma referencia externa.
import { expect, test } from '@playwright/test'
import { abrirFolio, entrar } from './ayudas'

test('revisor: ve el antecedente del folio y lo abre', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000002')
  const seccion = page.getByRole('region', { name: 'Antecedentes' })
  const elemento = seccion.getByRole('listitem', { name: /^Antecedente / })
  await expect(elemento).toHaveCount(1)
  await expect(elemento).toContainText('Decisión: Aprobado')
  await expect(elemento.getByRole('heading', { name: /Expediente ONB-2026-000004/ })).toBeVisible()
  await elemento.getByRole('link', { name: 'ONB-2026-000004' }).click()
  await expect(page.getByRole('heading', { name: /Expediente ONB-2026-000004/ }).first()).toBeVisible()
  await expect(page).toHaveURL(/\/folios\/ONB-2026-000004$/)
})
