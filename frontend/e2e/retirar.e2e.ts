// Retirar y restaurar un documento subido por error (ADR-013): no cuenta para el folio y nada se borra.
import { expect, test } from '@playwright/test'
import { abrirFolio, entrar } from './ayudas'

test('revisor: retira el comprobante con motivo, aparece EXP-001, y al restaurarlo vuelve CMP-001', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000002')
  const documentos = page.getByRole('navigation', { name: 'Documentos del folio' })
  const alertas = page.getByRole('region', { name: 'Alertas del expediente' })
  await documentos.getByRole('button', { name: /comprobante_domicilio/ }).click()
  await expect(alertas.getByText('CMP-001').first()).toBeVisible()

  await page.getByRole('button', { name: 'Retirar', exact: true }).click()
  await page.getByLabel(/Motivo de la retirada/).fill('Comprobante de otra persona (e2e)')
  await page.getByRole('button', { name: 'Retirar documento' }).click()
  await page.getByRole('alertdialog', { name: 'Confirmar la retirada' }).getByRole('button', { name: 'Sí, retirar' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Documento retirado del folio.')
  await expect(page.getByRole('region', { name: 'Documento retirado' })).toContainText('Comprobante de otra persona (e2e)')
  await expect(documentos.getByText('Retirado')).toBeVisible()
  await expect(alertas.getByText('EXP-001').first()).toBeVisible()
  await expect(alertas.getByText('CMP-001')).toHaveCount(0)

  await page.getByRole('region', { name: 'Documento retirado' }).getByRole('button', { name: 'Restaurar' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Documento restaurado.')
  await expect(documentos.getByText('Retirado')).toHaveCount(0)
  await expect(alertas.getByText('CMP-001').first()).toBeVisible()
  await expect(alertas.getByText('EXP-001')).toHaveCount(0)
})
