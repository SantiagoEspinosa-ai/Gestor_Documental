// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { MS_HASTA_COMPLETADO, MS_HASTA_PROCESANDO } from '../mocks/logica'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { PaginaCarga } from './PaginaCarga'

const mock = usarServidorMock()
// En jsdom, import.meta.url no es file://: se parte del directorio de trabajo (frontend/)
const ORIGINALES = join(process.cwd(), 'public', 'mock-originales')
const fixture = (nombre: string) => new File([readFileSync(join(ORIGINALES, nombre))], nombre)

function montarCarga(folio: string) {
  return montar(`/folios/${folio}/carga`, (
    <Routes><Route path="/folios/:folio/carga" element={<PaginaCarga intervaloSondeoMs={30} />} /></Routes>
  ))
}

async function nuevoFolio(): Promise<string> {
  const r = await fetch('http://localhost:8000/api/v1/folios', {
    method: 'POST', body: JSON.stringify({ proceso: 'onboarding' }),
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!).token}` },
  })
  return (await r.json()).folio
}

const aviso = () => screen.getByText(/Faltan tipos requeridos|Están todos los tipos requeridos/).textContent
const filaDocumento = (nombre: string) => screen.getByRole('rowheader', { name: nombre }).closest('tr')!

describe('pantalla de carga', () => {
  it('sube con tipo declarado, sigue pendiente -> procesando -> completado y actualiza los tipos que faltan', async () => {
    await entrarComo('integrador.demo')
    const folio = await nuevoFolio()
    montarCarga(folio)
    await screen.findByRole('heading', { name: new RegExp(folio) })
    expect(aviso()).toContain('Credencial de elector, Comprobante de domicilio')

    const u = userEvent.setup()
    await u.upload(screen.getByLabelText('Elegir archivos'), fixture('credencial_elector_sano_digital.pdf'))
    await u.selectOptions(screen.getByLabelText('Tipo declarado de credencial_elector_sano_digital.pdf'), 'credencial_elector')
    await u.click(screen.getByRole('button', { name: 'Subir 1 archivo' }))

    const fila = await waitFor(() => filaDocumento('credencial_elector_sano_digital.pdf'))
    expect(within(fila).getByText('Pendiente')).toBeTruthy()
    mock.t += MS_HASTA_PROCESANDO
    await within(fila).findByText('Procesando')
    mock.t += MS_HASTA_COMPLETADO - MS_HASTA_PROCESANDO
    await within(filaDocumento('credencial_elector_sano_digital.pdf')).findByText('Completado')
    await waitFor(() => expect(aviso()).toContain('Faltan tipos requeridos por el proceso: Comprobante de domicilio.'))
    expect(screen.getByTestId('anuncio').textContent).toContain('credencial_elector_sano_digital.pdf: completado')
  })

  it('valida la extensión contra formatos_permitidos del tipo elegido y no sube lo inválido', async () => {
    await entrarComo('revisor.demo')
    montarCarga('ONB-2026-000002')
    await screen.findByRole('heading', { name: /ONB-2026-000002/ })
    const u = userEvent.setup({ applyAccept: false })
    await u.upload(screen.getByLabelText('Elegir archivos'), new File(['x'], 'notas.txt'))
    expect(screen.getByRole('alert').textContent).toBe('Formato .txt no permitido. Permitidos: pdf, jpg, jpeg, png.')
    expect((screen.getByRole('button', { name: 'Subir 0 archivos' }) as HTMLButtonElement).disabled).toBe(true)
    await u.selectOptions(screen.getByLabelText('Tipo declarado de notas.txt'), 'pasaporte')
    expect(screen.getByRole('alert').textContent).toContain('no permitido para Pasaporte')
    expect(mock.peticiones.some((p) => p.startsWith('POST /folios/'))).toBe(false) // nada se ha subido
  })

  it('arrastrar y soltar añade archivos; un fichero repetido en el folio muestra DUP-001', async () => {
    await entrarComo('revisor.demo')
    montarCarga('ONB-2026-000003')
    await screen.findByRole('heading', { name: /ONB-2026-000003/ })
    fireEvent.drop(screen.getByTestId('zona-carga'), { dataTransfer: { files: [fixture('credencial_elector_sano_digital.pdf')], types: ['Files'] } })
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Subir 1 archivo' }))
    await waitFor(() => expect(screen.getAllByRole('rowheader', { name: 'credencial_elector_sano_digital.pdf' })).toHaveLength(2))
    expect(screen.getByText(/Duplicado \(DUP-001\): Mismo SHA-256 que el documento/)).toBeTruthy()
  })

  it('el documento en error y los tipos que faltan se muestran al abrir', async () => {
    await entrarComo('revisor.demo')
    montarCarga('ONB-2026-000003')
    await screen.findByRole('heading', { name: /ONB-2026-000003/ })
    expect(aviso()).toContain('Comprobante de domicilio')
    expect(within(filaDocumento('pasaporte_sano_foto.jpg')).getByText(/El análisis falló \(SYS-001\)/)).toBeTruthy()
  })

  it('folio cerrado: solo lectura y sin subida', async () => {
    await entrarComo('revisor.demo')
    montarCarga('ONB-2026-000004')
    expect(await screen.findByText(/El folio está aprobado: solo lectura/)).toBeTruthy()
    expect((screen.getByLabelText('Elegir archivos') as HTMLInputElement).disabled).toBe(true)
  })

  it('el admin consulta pero no sube', async () => {
    await entrarComo('admin.demo')
    montarCarga('ONB-2026-000001')
    expect(await screen.findByText('Tu rol puede consultar los documentos, pero no subirlos.')).toBeTruthy()
    expect((screen.getByLabelText('Elegir archivos') as HTMLInputElement).disabled).toBe(true)
  })

  it('el sondeo se para al salir de la pantalla', async () => {
    await entrarComo('revisor.demo')
    const { unmount } = montarCarga('ONB-2026-000002') // tiene un documento pendiente
    await screen.findByRole('heading', { name: /ONB-2026-000002/ })
    const sondeos = () => mock.peticiones.filter((p) => p.startsWith('GET /documentos/')).length
    await waitFor(() => expect(sondeos()).toBeGreaterThan(0))
    unmount()
    const alSalir = sondeos()
    await new Promise((r) => setTimeout(r, 150)) // 5 intervalos
    expect(sondeos()).toBe(alSalir)
  })

  it('folio inexistente: mensaje del código', async () => {
    await entrarComo('revisor.demo')
    montarCarga('ONB-2026-999999')
    expect((await screen.findByRole('alert')).textContent).toBe('El folio no existe.')
  })
})
