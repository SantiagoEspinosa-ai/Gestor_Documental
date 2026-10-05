// Humo real (H6): el revisor completa un folio contra la API real (motor stub) y el admin ve su auditoria.
// En serie: el admin revisa el folio que acaba de cerrar el revisor.
import { expect, test } from '@playwright/test'
import { COMPROBANTE, CREDENCIAL, entrar, esperarCompletado, exigirUsuarios, nuevoFolio, referenciaE2E, subir } from './ayudas'

test.describe.configure({ mode: 'serial' })

let folio = ''

test('revisor_flujo: nuevo folio, subir credencial y comprobante, esperar el análisis y aprobar', async ({ page }) => {
  exigirUsuarios('revisor')
  test.setTimeout(10 * 60_000)
  await entrar(page, 'revisor')
  const referencia = referenciaE2E()
  folio = await nuevoFolio(page, referencia)

  // Folio nuevo: EXP-001 por cada tipo requerido, visibles en el expediente
  await page.getByRole('link', { name: 'Ver expediente' }).click()
  const alertasExpediente = page.getByRole('region', { name: 'Alertas del expediente' })
  await expect(alertasExpediente.getByRole('listitem').filter({ hasText: 'EXP-001' })).toHaveCount(2)
  await page.goto(`/folios/${folio}/carga`)

  await subir(page, { [CREDENCIAL]: 'credencial_elector', [COMPROBANTE]: 'comprobante_domicilio' })
  for (const nombre of [CREDENCIAL, COMPROBANTE]) await esperarCompletado(page, nombre)
  await expect(page.getByText('Están todos los tipos requeridos por el proceso.')).toBeVisible()

  await page.getByRole('link', { name: 'Ver expediente' }).click()
  await expect(page.getByRole('heading', { name: `Expediente ${folio}` })).toBeVisible()
  await expect(alertasExpediente).toContainText('Sin alertas.') // las EXP-001 han desaparecido

  const decision = page.getByRole('region', { name: 'Decisión del revisor' })
  await decision.getByLabel('Comentario de la decisión').fill('Documentacion completa (e2e real)')
  await decision.getByRole('button', { name: 'Aprobar' }).click()
  await decision.getByRole('alertdialog', { name: 'Confirmar la decisión' }).getByRole('button', { name: 'Sí, aprobar' }).click()

  await expect(page.getByTestId('aviso')).toHaveText('Folio aprobado.')
  const cabecera = page.locator('header').filter({ has: page.getByRole('heading', { name: `Expediente ${folio}` }) })
  await expect(cabecera.getByRole('status')).toContainText('Decisión: Aprobado · “Documentacion completa (e2e real)”')
  await expect(cabecera.getByRole('status')).toContainText('Folio cerrado: solo lectura')
  await expect(page.getByRole('region', { name: 'Decisión del revisor' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Corregir / })).toHaveCount(0)

  // resumen.md regenerado tras la decision: folio y referencia; nunca el nombre en la cabecera
  await page.getByRole('button', { name: 'Ver resumen' }).click()
  const resumen = page.getByRole('region', { name: 'Resumen del expediente' })
  await expect(resumen.getByRole('heading', { level: 1 })).toHaveText(`Expediente ${folio}`)
  await expect(resumen).toContainText(`Referencia: ${referencia}`)
  await expect(resumen).toContainText('Decision: Aprobado')
  const cabeceraResumen = (await resumen.textContent())!.split('Documentos')[0]
  expect(cabeceraResumen).not.toMatch(/Nombre|nombre_completo/)
})

test('admin_auditoria: la auditoría del folio tiene la creación, las subidas, los análisis y la decisión', async ({ page }) => {
  exigirUsuarios('admin')
  test.skip(!folio, 'Depende de revisor_flujo, que no ha creado el folio')
  await entrar(page, 'admin')
  await page.goto(`/auditoria?folio=${folio}`)
  await expect(page.getByText(/^Página 1 de 1 \(\d+ entradas?\)$/)).toBeVisible()
  const acciones = page.getByRole('rowheader')
  await expect(acciones.filter({ hasText: 'Folio creado' })).toHaveCount(1)
  await expect(acciones.filter({ hasText: 'Documento subido' })).toHaveCount(2)
  await expect(acciones.filter({ hasText: 'Documento analizado' })).toHaveCount(2)
  await expect(acciones.filter({ hasText: 'Decisión del folio' })).toHaveCount(1)
})
