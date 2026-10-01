// Utilidades de los e2e. Usuarios ficticios de src/mocks/usuarios.ts; ficheros de public/mock-originales.
import { expect, type Page } from '@playwright/test'
import { join } from 'node:path'

export const ORIGINALES = join(import.meta.dirname, '..', 'public', 'mock-originales')

const CONTRASENAS = { 'admin.demo': 'demo-admin', 'revisor.demo': 'demo-revisor', 'integrador.demo': 'demo-integrador' } as const
export type UsuarioDemo = keyof typeof CONTRASENAS

export async function entrar(page: Page, usuario: UsuarioDemo) {
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(usuario)
  await page.getByLabel('Contraseña', { exact: true }).fill(CONTRASENAS[usuario])
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).toHaveURL(/\/folios$/)
}

/** Cierra la sesion y entra con otro usuario desde el formulario, sin recargar: conserva el estado de los mocks */
export async function cambiarDeUsuario(page: Page, usuario: UsuarioDemo) {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Usuario').fill(usuario)
  await page.getByLabel('Contraseña', { exact: true }).fill(CONTRASENAS[usuario])
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByTestId('usuario-actual')).toContainText(usuario)
}

/** Crea un folio onboarding desde "Nuevo folio" y deja la pagina en su carga de documentos */
export async function nuevoFolio(page: Page): Promise<string> {
  await page.getByRole('button', { name: 'Nuevo folio' }).click()
  await page.locator('#nuevo-folio').getByLabel('Proceso').selectOption('onboarding')
  await page.getByRole('button', { name: 'Crear folio' }).click()
  await expect(page).toHaveURL(/\/folios\/ONB-\d{4}-\d{6}\/carga$/)
  return page.url().match(/(ONB-\d{4}-\d{6})/)![1]
}

/** Sube los ficheros de public/mock-originales desde la pantalla de carga */
export async function subir(page: Page, ...nombres: string[]) {
  await page.getByLabel('Elegir archivos').setInputFiles(nombres.map((n) => join(ORIGINALES, n)))
  await page.getByRole('button', { name: new RegExp(`^Subir ${nombres.length} archivos?$`) }).click()
}

/** Fila de un documento en la tabla de la carga */
export const filaCarga = (page: Page, nombre: string) =>
  page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: nombre, exact: true }) })

/** Abre un folio desde la lista (sin recargar: el estado de los mocks esta en la pagina) */
export async function abrirFolio(page: Page, folio: string) {
  await page.getByRole('link', { name: folio, exact: true }).click()
  await expect(page.getByRole('heading', { name: new RegExp(`Expediente ${folio}`) })).toBeVisible()
}
