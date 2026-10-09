// "Mostrar" real (H17, ADR-010 A4): el revisor revela un dato sensible contra la API real y el admin ve
// "Dato revelado" en la auditoria del folio. Con el motor stub no se extraen datos, asi que el revisor
// escribe antes una CURP ficticia (sale enmascarada) y despues la muestra.
import { expect, test } from '@playwright/test'
import { abrirDocumento, CREDENCIAL, entrar, esperarCompletado, exigirUsuarios, irADocumentos, nuevoFolio, referenciaE2E, subir } from './ayudas'

test.describe.configure({ mode: 'serial' })

const CURP_FICTICIA = 'XEXX010101HNEXXXA4'
let folio = ''

test('revisor_mostrar: corrige la CURP, sale enmascarada, la muestra y la oculta', async ({ page }) => {
  exigirUsuarios('revisor')
  test.setTimeout(10 * 60_000)
  await entrar(page, 'revisor')
  folio = await nuevoFolio(page, referenciaE2E())
  await subir(page, { [CREDENCIAL]: 'credencial_elector' })
  await esperarCompletado(page, CREDENCIAL)
  await irADocumentos(page)
  await expect(page.getByRole('heading', { name: `Expediente ${folio}` })).toBeVisible()
  await abrirDocumento(page, CREDENCIAL)

  const curp = page.getByRole('region', { name: 'Datos leídos' }).getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Curp', exact: true }) })
  await curp.getByRole('button', { name: 'Corregir Curp' }).click()
  await curp.getByLabel('Nuevo valor de Curp').fill(CURP_FICTICIA)
  await curp.getByRole('button', { name: 'Guardar corrección' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Curp corregido.')
  const valor = curp.locator('td').first()
  await expect(valor).toContainText('****XXA4')
  await expect(valor).not.toContainText(CURP_FICTICIA)

  await curp.getByRole('button', { name: 'Mostrar Curp' }).click()
  await expect(valor).toContainText(CURP_FICTICIA)
  await curp.getByRole('button', { name: 'Ocultar Curp' }).click()
  await expect(valor).not.toContainText(CURP_FICTICIA)
})

test('admin_auditoria_revelado: "Dato revelado" con el campo, nunca el valor', async ({ page }) => {
  exigirUsuarios('admin')
  test.skip(!folio, 'Depende de revisor_mostrar, que no ha creado el folio')
  await entrar(page, 'admin')
  await page.goto(`/auditoria?folio=${folio}`)
  const revelado = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Dato revelado' }) })
  await expect(revelado).toHaveCount(1)
  await expect(revelado).toContainText('Campo: curp')
  await expect(page.getByRole('table')).not.toContainText(CURP_FICTICIA)
})
