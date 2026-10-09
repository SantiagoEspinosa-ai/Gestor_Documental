// Utilidades de los e2e reales (copiadas de e2e/ayudas.ts y adaptadas: usuarios reales por entorno).
// No se importa nada de e2e/ para que cada proyecto de Playwright recoja solo sus tests.
import { expect, test, type Page } from '@playwright/test'
import { join } from 'node:path'

export const ORIGINALES = join(import.meta.dirname, '..', 'public', 'mock-originales')
export const CREDENCIAL = 'credencial_elector_sano_digital.pdf'
export const COMPROBANTE = 'comprobante_domicilio_sano_digital.pdf'
/** Con el stub cada documento tarda segundos; el limite es el del motor real (5 min por documento) */
export const ESPERA_ANALISIS_MS = 5 * 60_000

export type Rol = 'revisor' | 'admin' | 'integrador'

/** Usuario y contrasena de E2E_<ROL>_USUARIO y E2E_<ROL>_CLAVE. Nunca se imprimen */
function credenciales(rol: Rol): { usuario: string; clave: string } | null {
  const usuario = process.env[`E2E_${rol.toUpperCase()}_USUARIO`]
  const clave = process.env[`E2E_${rol.toUpperCase()}_CLAVE`]
  return usuario && clave ? { usuario, clave } : null
}

/** Salta el test si falta alguna de las variables de esos roles */
export function exigirUsuarios(...roles: Rol[]) {
  const faltan = roles.filter((r) => !credenciales(r)).map((r) => `E2E_${r.toUpperCase()}_USUARIO/CLAVE`)
  test.skip(faltan.length > 0, `Faltan variables de entorno: ${faltan.join(', ')}`)
}

export async function entrar(page: Page, rol: Rol) {
  const { usuario, clave } = credenciales(rol)!
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(usuario)
  await page.getByLabel('Contraseña', { exact: true }).fill(clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByTestId('usuario-actual')).toContainText(usuario)
}

/** Referencia externa unica por test: el folio no depende de datos que ya existan */
export const referenciaE2E = () => `E2E-${Date.now()}`

/** Crea un folio onboarding con referencia desde "Nuevo folio" y deja la pagina en su carga */
export async function nuevoFolio(page: Page, referencia: string): Promise<string> {
  await page.getByRole('button', { name: 'Nuevo folio' }).click()
  const formulario = page.locator('#nuevo-folio')
  await formulario.getByLabel('Proceso').selectOption('onboarding')
  await formulario.getByLabel('Referencia externa (opcional)').fill(referencia)
  await page.getByRole('button', { name: 'Crear folio' }).click()
  await expect(page).toHaveURL(/\/folios\/ONB-\d{4}-\d{6}\/carga$/)
  return page.url().match(/(ONB-\d{4}-\d{6})/)![1]
}

/** Sube ficheros de public/mock-originales, cada uno con su tipo declarado: {nombre: tipo} */
export async function subir(page: Page, ficheros: Record<string, string>) {
  const nombres = Object.keys(ficheros)
  await page.getByLabel('Elegir archivos').setInputFiles(nombres.map((n) => join(ORIGINALES, n)))
  for (const [nombre, tipo] of Object.entries(ficheros)) {
    await page.getByLabel(`Tipo declarado de ${nombre}`).selectOption(tipo)
  }
  await page.getByRole('button', { name: new RegExp(`^Subir ${nombres.length} archivos?$`) }).click()
  for (const nombre of nombres) await expect(filaCarga(page, nombre)).toBeVisible()
}

/** Fila de un documento en la tabla de la carga */
export const filaCarga = (page: Page, nombre: string) =>
  page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: nombre, exact: true }) })

/** Espera a que el documento llegue a "Completado" (el sondeo de la pantalla refresca solo) */
export async function esperarCompletado(page: Page, nombre: string) {
  await expect.poll(async () => (await filaCarga(page, nombre).textContent()) ?? '', {
    timeout: ESPERA_ANALISIS_MS, intervals: [2_000, 5_000, 10_000],
    message: `${nombre} no ha llegado a "Completado"`,
  }).toContain('Completado')
}

/** De la pestana de carga a la de Documentos del expediente */
export async function irADocumentos(page: Page) {
  await page.getByRole('navigation', { name: 'Secciones del expediente' }).getByRole('link', { name: /^Documentos · / }).click()
  await expect(page.getByRole('region', { name: 'Documentos del folio' })).toBeVisible()
}

/** "Abrir y revisar" (o "Abrir") de un documento en la rejilla del expediente */
export async function abrirDocumento(page: Page, nombre: string) {
  await page.getByRole('region', { name: 'Documentos del folio' })
    .getByRole('link', { name: new RegExp(`^Abrir( y revisar)? ${nombre.replaceAll('.', '[.]')}$`) }).click()
  await expect(page.getByRole('link', { name: /Todos los documentos/ })).toBeVisible()
}
