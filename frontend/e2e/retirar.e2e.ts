// Retirar y restaurar un documento subido por error (ADR-013): no cuenta para el folio y nada se borra.
import { expect, test } from '@playwright/test'
import { abrirDocumento, abrirFolio, entrar, volverALaLista } from './ayudas'

const COMPROBANTE = 'comprobante_domicilio_domicilio_distinto_foto.jpg'

test('revisor: retira el comprobante con motivo, aparece EXP-001, y al restaurarlo vuelve CMP-001', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000002')
  const documentos = page.getByRole('region', { name: 'Documentos del folio' })
  const alertas = page.getByRole('region', { name: 'Alertas del expediente' })
  await expect(alertas.getByText('CMP-001').first()).toBeVisible()

  await abrirDocumento(page, COMPROBANTE)
  await page.getByText('Retirar este documento del expediente').click()
  await page.getByRole('button', { name: 'Retirar', exact: true }).click()
  await page.getByLabel(/Motivo de la retirada/).fill('Comprobante de otra persona (e2e)')
  await page.getByRole('button', { name: 'Retirar documento' }).click()
  await page.getByRole('alertdialog', { name: 'Confirmar la retirada' }).getByRole('button', { name: 'Sí, retirar' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Documento retirado del folio.')
  await expect(page.getByRole('region', { name: 'Documento retirado' })).toContainText('Comprobante de otra persona (e2e)')

  await volverALaLista(page)
  await expect(documentos.getByRole('article').last()).toContainText('Retirado') // al final de la rejilla
  await expect(alertas.getByText('EXP-001').first()).toBeVisible()
  await expect(alertas.getByText('CMP-001')).toHaveCount(0)

  await documentos.getByRole('button', { name: `Restaurar ${COMPROBANTE}` }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Documento restaurado.')
  await expect(documentos.getByText('Retirado')).toHaveCount(0)
  await expect(alertas.getByText('CMP-001').first()).toBeVisible()
  await expect(alertas.getByText('EXP-001')).toHaveCount(0)
})
