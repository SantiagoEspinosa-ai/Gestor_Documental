// Flujo completo del revisor sobre los mocks: crear folio, subir, esperar el analisis, revisar y aprobar.
import { expect, test } from '@playwright/test'
import { entrar, filaCarga, nuevoFolio, subir } from './ayudas'

const CREDENCIAL = 'credencial_elector_sano_digital.pdf'
const COMPROBANTE = 'comprobante_domicilio_sano_digital.pdf'

test('revisor: nuevo folio, subir credencial y comprobante, revisar alertas y aprobar con comentario', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  const folio = await nuevoFolio(page)
  await expect(page.getByText(/Faltan tipos requeridos por el proceso/)).toBeVisible()

  await subir(page, CREDENCIAL, COMPROBANTE)
  // El mock tarda 9 s en analizar cada documento; el sondeo empieza a 3 s y va espaciandose
  for (const nombre of [CREDENCIAL, COMPROBANTE]) {
    await expect(filaCarga(page, nombre)).toContainText('Completado', { timeout: 30_000 })
  }
  await expect(page.getByText('Están todos los tipos requeridos por el proceso.')).toBeVisible()

  await page.getByRole('link', { name: 'Ver expediente' }).click()
  await expect(page.getByRole('heading', { name: `Expediente ${folio}` })).toBeVisible()

  // Revisar las alertas que haya: todas como falso positivo con comentario (la decision sigue siendo humana).
  // Con el caso sano los mocks no dejan ninguna: las EXP-001 del folio nuevo desaparecen al llegar los dos
  // tipos requeridos. La resolucion de alertas se prueba en bloqueante.e2e.ts y duplicado.e2e.ts.
  await expect(page.getByRole('region', { name: 'Alertas del expediente' })).toContainText('Sin alertas.')
  const revisar = page.getByRole('button', { name: /: falso positivo$/ })
  for (let pendientes = await revisar.count(); pendientes > 0; pendientes = await revisar.count()) {
    const comentario = page.getByPlaceholder('Comentario (opcional)').first()
    await comentario.fill('Revisado en el e2e')
    await revisar.first().click()
    await expect(page.getByTestId('aviso')).toContainText('revisada')
  }
  await expect(page.getByRole('region', { name: 'Resultado global' })).toContainText('Bloqueantes sin descartar: 0')

  const decision = page.getByRole('region', { name: 'Decisión del revisor' })
  await decision.getByLabel('Comentario de la decisión').fill('Documentacion completa (e2e)')
  await decision.getByRole('button', { name: 'Aprobar' }).click()
  await decision.getByRole('alertdialog', { name: 'Confirmar la decisión' }).getByRole('button', { name: 'Sí, aprobar' }).click()

  // Folio cerrado: decision visible y sin acciones
  await expect(page.getByTestId('aviso')).toHaveText('Folio aprobado.')
  const cabecera = page.locator('header').filter({ has: page.getByRole('heading', { name: `Expediente ${folio}` }) })
  await expect(cabecera.getByRole('status')).toContainText('Decisión: Aprobado · “Documentacion completa (e2e)” · revisor.demo')
  await expect(cabecera.getByRole('status')).toContainText('Folio cerrado: solo lectura')
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Corregir / })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Confirmar clasificación' })).toHaveCount(0)
})
