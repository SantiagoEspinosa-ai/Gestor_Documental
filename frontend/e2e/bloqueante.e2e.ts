// Regla 2.2 del ADR-006 con el folio de los mocks que tiene una bloqueante (ONB-2026-000001).
import { expect, test } from '@playwright/test'
import { abrirDocumento, abrirFolio, entrar, volverALaLista } from './ayudas'

test('bloqueante confirmada: Aprobar sigue deshabilitado con el motivo y se rechaza con confirmacion', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000001')
  await abrirDocumento(page, 'pasaporte_vencido_escaneado.pdf')

  const avisos = page.getByRole('region', { name: 'Avisos de este documento' })
  await avisos.getByRole('button', { name: 'REG-vigencia_documento: sí, es un problema' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Alerta REG-vigencia_documento revisada.')
  await expect(avisos.locator('li').filter({ hasText: 'REG-vigencia_documento' })).toContainText('Aplica (confirmada por el revisor)')

  // La decision esta al final de la lista de documentos
  await volverALaLista(page)
  await expect(page.getByTestId('estado-revision')).toContainText('solo puedes rechazar')
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
  await expect(page.getByTestId('fase-decision')).toContainText('Rechazado')
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
})
