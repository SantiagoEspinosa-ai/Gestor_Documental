// DUP-001: el mismo SHA-256 dos veces en un folio no bloquea la subida, pero se avisa.
import { expect, test } from '@playwright/test'
import { entrar, filaCarga, nuevoFolio, subir } from './ayudas'

const FICHERO = 'credencial_elector_sano_digital.pdf'

test('subir dos veces el mismo fichero en un folio da DUP-001; el revisor lo marca como falso positivo', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  const folio = await nuevoFolio(page)
  await subir(page, FICHERO)
  await expect(filaCarga(page, FICHERO)).toHaveCount(1)
  await subir(page, FICHERO)
  await expect(filaCarga(page, FICHERO)).toHaveCount(2)
  await expect(filaCarga(page, FICHERO).nth(0)).not.toContainText('DUP-001')
  await expect(filaCarga(page, FICHERO).nth(1)).toContainText('Duplicado (DUP-001)')

  // En el expediente, la alerta del segundo documento se revisa con comentario
  await expect(filaCarga(page, FICHERO).nth(1)).toContainText('Completado', { timeout: 30_000 })
  await page.getByRole('link', { name: 'Ver expediente' }).click()
  await expect(page.getByRole('heading', { name: `Expediente ${folio}` })).toBeVisible()
  await page.getByRole('navigation', { name: 'Documentos del folio' }).getByRole('button').nth(1).click()
  const alertas = page.getByRole('region', { name: 'Alertas del documento seleccionado' })
  await alertas.getByLabel('Comentario sobre DUP-001').fill('Se subio dos veces por error (e2e)')
  await alertas.getByRole('button', { name: 'DUP-001: falso positivo' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Alerta DUP-001 revisada.')
  const dup = alertas.locator('li').filter({ hasText: 'DUP-001' })
  await expect(dup).toContainText('Falso positivo')
  await expect(dup).toContainText('“Se subio dos veces por error (e2e)”')
  await expect(dup).toContainText('revisor.demo')
})
