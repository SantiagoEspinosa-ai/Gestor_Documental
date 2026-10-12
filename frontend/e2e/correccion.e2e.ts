// Corregir datos (PATCH /documentos/{id}/datos), con la regla decidida con PERSONA_1 en el PR #10:
// un obligatorio no se vacia, un opcional vaciado queda en null y el anio va como entero de 4 cifras.
import { expect, test } from '@playwright/test'
import { abrirDocumento, abrirFolio, entrar, filaDato, volverALaLista } from './ayudas'

test('revisor: no puede vaciar un campo obligatorio, si uno opcional, y el anio se valida antes de enviar', async ({ page }) => {
  await entrar(page, 'revisor.demo')
  await abrirFolio(page, 'ONB-2026-000001')
  await abrirDocumento(page, 'pasaporte_vencido_escaneado.pdf')
  const fila = (campo: string) => filaDato(page, campo)

  // Obligatorio: vacio -> Guardar deshabilitado y el motivo a la vista; Cancelar lo deja como estaba
  const nombre = fila('Nombre completo')
  await nombre.getByRole('button', { name: 'Corregir Nombre completo' }).click()
  await nombre.getByLabel('Nuevo valor de Nombre completo').fill('')
  await expect(nombre.getByRole('button', { name: 'Guardar corrección' })).toBeDisabled()
  await expect(nombre).toContainText('Este campo es obligatorio: no se puede dejar vacío.')
  await nombre.getByRole('button', { name: 'Cancelar' }).click()
  await expect(nombre).toContainText('LUIS DEMO PRUEBAS') // caso vencido (persona ficticia 2)
  await expect(nombre).not.toContainText('Corregido por')

  // Opcional: vacio -> se guarda como null ("No detectado") y el boton pasa a "Escribir el valor"
  const nacionalidad = fila('Nacionalidad')
  await nacionalidad.getByRole('button', { name: 'Corregir Nacionalidad' }).click()
  await nacionalidad.getByLabel('Nuevo valor de Nacionalidad').fill('')
  await nacionalidad.getByRole('button', { name: 'Guardar corrección' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Nacionalidad corregido.')
  await expect(nacionalidad).toContainText('No detectado · míralo en el original')
  await expect(nacionalidad).toContainText('Corregido por ti (antes: UTOPICA)')
  await expect(nacionalidad.getByRole('button', { name: 'Escribir el valor de Nacionalidad' })).toBeVisible()

  // anio: 4 cifras; con menos no se puede guardar
  await volverALaLista(page)
  await abrirDocumento(page, 'credencial_elector_vencido_foto.jpg')
  const vigencia = fila('Vigencia')
  await vigencia.getByRole('button', { name: 'Corregir Vigencia' }).click()
  const entrada = vigencia.getByLabel('Nuevo valor de Vigencia')
  await entrada.fill('203')
  await expect(vigencia.getByRole('button', { name: 'Guardar corrección' })).toBeDisabled()
  await expect(vigencia).toContainText('El año debe tener 4 cifras (AAAA)')
  await entrada.fill('2030')
  await vigencia.getByRole('button', { name: 'Guardar corrección' }).click()
  await expect(page.getByTestId('aviso')).toHaveText('Vigencia corregido.')
  await expect(vigencia).toContainText('2030')
  await expect(vigencia).toContainText('Corregido por ti (antes: 2029)')
})
