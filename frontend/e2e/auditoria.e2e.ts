// Pantalla de auditoria del admin (ADR-008). El revisor decide ONB-2026-000001 y el admin lo ve en la
// auditoria. Todo en la misma pagina: el estado de los mocks vive en ella.
import { expect, test } from '@playwright/test'
import { abrirFolio, cambiarDeUsuario, entrar } from './ayudas'

test('admin: abre la auditoria, filtra por ONB-2026-000001 y ve la decision del revisor', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await expect(page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Auditoría' })).toHaveCount(0)
  await abrirFolio(page, 'ONB-2026-000001')
  const decision = page.getByRole('region', { name: 'Decisión del revisor' })
  await decision.getByLabel('Comentario de la decisión').fill('Pasaporte vencido (e2e auditoria)')
  await decision.getByRole('button', { name: 'Rechazar' }).click()
  await decision.getByRole('alertdialog', { name: 'Confirmar la decisión' }).getByRole('button', { name: 'Sí, rechazar' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Folio rechazado.')

  await cambiarDeUsuario(page, 'admin.demo')
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Auditoría' }).click()
  await expect(page).toHaveURL(/\/auditoria$/)
  await expect(page.getByRole('heading', { name: 'Auditoría' })).toBeVisible()

  await page.getByLabel('Folio', { exact: true }).fill('ONB-2026-000001')
  await page.getByRole('button', { name: 'Filtrar' }).click()
  await expect(page).toHaveURL(/\/auditoria\?folio=ONB-2026-000001$/)
  await expect(page.getByText(/^Página 1 de 1 \(\d+ entradas\)$/)).toBeVisible()
  const filas = page.getByRole('row').filter({ has: page.getByRole('link', { name: 'ONB-2026-000001' }) })
  await expect(filas.first()).toBeVisible()
  expect(await page.getByRole('row').count() - 1).toBe(await filas.count()) // solo ese folio

  // La mas reciente es la decision: accion legible, usuario y detalle sin JSON
  const fila = filas.filter({ has: page.getByRole('rowheader', { name: 'Decisión del folio' }) })
  await expect(fila).toHaveCount(1)
  await expect(fila).toContainText('revisor.demo')
  await expect(fila).toContainText('Decisión: Rechazado')
  await expect(filas.first()).toContainText('Decisión del folio')

  // Desde la auditoria se abre el expediente
  await fila.getByRole('link', { name: 'ONB-2026-000001' }).click()
  await expect(page.getByRole('heading', { name: /Expediente ONB-2026-000001/ })).toBeVisible()
  await expect(page.getByText(/Decisión: Rechazado · “Pasaporte vencido \(e2e auditoria\)”/)).toBeVisible()
})

test('revisor: entra en /auditoria por URL y ve "Sin permiso"', async ({ page }) => {
  // Sin sesion, la URL lleva al login y, tras entrar, vuelve a /auditoria (recargar con sesion no sirve con
  // los mocks: su estado, y con el los tokens, se reinicia en cada carga)
  await page.goto('/auditoria')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Usuario').fill('revisor.demo')
  await page.getByLabel('Contraseña', { exact: true }).fill('demo-revisor')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).toHaveURL(/\/auditoria$/)
  await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible()
  await expect(page.getByRole('table')).toHaveCount(0)
})
