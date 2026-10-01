// Regla 2.2 del ADR-006 con el folio de los mocks que tiene una bloqueante (ONB-2026-000001).
import { expect, test } from '@playwright/test'
import { abrirFolio, entrar } from './ayudas'

test('bloqueante confirmada: Aprobar sigue deshabilitado con el motivo y se rechaza con confirmacion', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000001')

  const alertas = page.getByRole('region', { name: 'Alertas del documento seleccionado' })
  await alertas.getByRole('button', { name: 'REG-vigencia_documento: aplica' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Alerta REG-vigencia_documento revisada.')
  await expect(alertas.locator('li').filter({ hasText: 'REG-vigencia_documento' })).toContainText('Aplica (confirmada por el revisor)')

  const decision = page.getByRole('region', { name: 'Decisión del revisor' })
  await expect(decision.getByRole('button', { name: 'Aprobar' })).toBeDisabled()
  await expect(decision.getByRole('note')).toContainText('No se puede aprobar')
  await expect(decision.getByRole('note')).toContainText('REG-vigencia_documento')

  await decision.getByLabel('Comentario de la decisión').fill('Pasaporte vencido (e2e)')
  await decision.getByRole('button', { name: 'Rechazar' }).click()
  const dialogo = decision.getByRole('alertdialog', { name: 'Confirmar la decisión' })
  await expect(dialogo).toContainText('rechazar')
  await dialogo.getByRole('button', { name: 'Sí, rechazar' }).click()

  await expect(page.getByTestId('aviso')).toHaveText('Folio rechazado.')
  await expect(page.getByText(/Decisión: Rechazado · “Pasaporte vencido \(e2e\)”/)).toBeVisible()
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
})
