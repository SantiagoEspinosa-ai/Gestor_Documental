// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { MS_HASTA_COMPLETADO } from '../mocks/logica'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { PaginaExpediente } from './PaginaExpediente'

const mock = usarServidorMock()
const ORIGINALES = join(process.cwd(), 'public', 'mock-originales')
const API = 'http://localhost:8000/api/v1'
const token = () => JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!).token as string

function montarExpediente(folio: string) {
  return montar(`/folios/${folio}`, (
    <Routes><Route path="/folios/:folio" element={<PaginaExpediente tiemposSondeo={{ inicialMs: 30, maximoMs: 30 }} />} /></Routes>
  ))
}
const documento = (nombre: string) => screen.getByRole('button', { name: new RegExp(nombre.replaceAll('.', '\\.')) })
const peticiones = (texto: string) => mock.peticiones.filter((p) => p === texto).length
const fila = (campo: string) => screen.getByRole('rowheader', { name: campo }).closest('tr')!

describe('documento no reconocido (ADR-009, H4)', () => {
  const NO_RECONOCIDO = 'pasaporte_sano_escaneado.pdf'

  it('clasificación "Tipo no reconocido" y aviso en lugar de la tabla vacía; el revisor puede confirmar el tipo', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000003')
    await screen.findByRole('heading', { name: /Expediente ONB-2026-000003/ })
    const boton = documento(NO_RECONOCIDO)
    expect(boton.textContent).toContain('Tipo no reconocido') // lista de documentos
    await userEvent.setup().click(boton)
    const clasificacion = await screen.findByRole('region', { name: 'Clasificación' })
    const detectado = within(clasificacion).getByText('Detectado').nextElementSibling!
    expect(detectado.textContent).toBe('Tipo no reconocido')
    expect(within(clasificacion).getByText('Declarado').nextElementSibling!.textContent).toBe('—')
    expect(screen.getByText(/No se han extraído datos: el tipo del documento no está reconocido/)).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Datos extraídos' })).toBeNull()
    expect(screen.queryByText('desconocido')).toBeNull()
    expect(screen.getByRole('button', { name: 'Confirmar clasificación' })).toBeTruthy()
  })

  it('el admin ve el aviso pero no puede confirmar la clasificación', async () => {
    await entrarComo('admin.demo')
    montarExpediente('ONB-2026-000003')
    await screen.findByRole('heading', { name: /Expediente ONB-2026-000003/ })
    await userEvent.setup().click(documento(NO_RECONOCIDO))
    expect(await screen.findByText(/No se han extraído datos/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Confirmar clasificación' })).toBeNull()
  })
})

describe('vista de expediente', () => {
  it('cabecera de un folio cerrado: referencia, fecha, proceso, estado, recomendacion y la decision', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000004')
    await screen.findByRole('heading', { name: /Expediente ONB-2026-000004/ })
    const cabecera = screen.getByRole('heading', { name: /Expediente/ }).closest('header')!
    expect(within(cabecera).getByText('CLI-000104')).toBeTruthy()
    expect(within(cabecera).getByText('onboarding')).toBeTruthy()
    expect(within(cabecera).getByText('Aprobado')).toBeTruthy() // estado_general
    const decision = within(cabecera).getByRole('status').textContent!
    expect(decision).toContain('Decisión: Aprobado')
    expect(decision).toContain('“Documentacion completa y coherente”')
    expect(decision).toContain('revisor.demo')
    expect(decision).toContain('Folio cerrado')
    expect(within(cabecera).getByRole('link', { name: /Carga de documentos/ }).getAttribute('href')).toBe('/folios/ONB-2026-000004/carga')
  })

  it('documento seleccionado: original en iframe o img pedido cada vez, datos con correccion y null como "no detectado"', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000002')
    const u = userEvent.setup()
    // El primero se selecciona solo: credencial escaneada (PDF) con una correccion
    const iframe = await screen.findByTitle('Original: credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(iframe.getAttribute('src')).toMatch(/mock-originales\/credencial_elector_domicilio_distinto_escaneado\.pdf\?firma=\d+$/)
    expect(within(fila('Nombre completo')).getByText('Corregido por revisor (antes: ANA EJEMPL0 PRUEBA)')).toBeTruthy()
    expect(screen.getByRole('meter', { name: 'Confianza verificada de la clasificación' })).toBeTruthy()

    // Foto (JPG) con el proveedor sin leer: null -> "no detectado", confianza 0 y VAL-004 informativa
    await u.click(documento('comprobante_domicilio_domicilio_distinto_foto.jpg'))
    expect(await screen.findByAltText('Original: comprobante_domicilio_domicilio_distinto_foto.jpg')).toBeTruthy()
    const proveedor = fila('Proveedor')
    expect(within(proveedor).getByText('no detectado')).toBeTruthy()
    expect(within(proveedor).getByText('0 %')).toBeTruthy()
    const alertasDoc = screen.getByRole('region', { name: 'Alertas del documento seleccionado' })
    expect(within(alertasDoc).getByText('Informativa (1)')).toBeTruthy()
    expect(within(alertasDoc).getByText('VAL-004')).toBeTruthy()

    // La URL caduca: al volver a abrir un documento se pide otra
    const antes = peticiones('GET /documentos/00000000-0000-4000-8000-000002000001/original')
    await u.click(documento('credencial_elector_domicilio_distinto_escaneado.pdf'))
    await screen.findByTitle('Original: credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(peticiones('GET /documentos/00000000-0000-4000-8000-000002000001/original')).toBe(antes + 1)

    // Comparaciones con el valor de cada documento y CMP-001 en las alertas del expediente
    const comparaciones = screen.getByRole('region', { name: 'Comparaciones entre documentos' })
    expect(within(comparaciones).getByText(/Domicilio: no coincide/)).toBeTruthy()
    expect(within(comparaciones).getByText(/Comprobante de domicilio \(comprobante_domicilio_domicilio_distinto_foto\.jpg\)/)).toBeTruthy()
    const expediente = screen.getByRole('region', { name: 'Alertas del expediente' })
    expect(within(expediente).getByText('Crítica (1)')).toBeTruthy()
    expect(within(expediente).getByText('CMP-001')).toBeTruthy()
  })

  it('confianza bajo el umbral de la ficha y fecha con el tipo del campo', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000001')
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: /credencial_elector_vencido_foto\.jpg/ }))
    expect(within(fila('Clave elector')).getByText(/bajo el mínimo \(80 %\)/)).toBeTruthy()
    expect(within(fila('Fecha nacimiento')).getByText(/^\d{2}\/\d{2}\/\d{4}$/)).toBeTruthy()
    const alertas = screen.getByRole('region', { name: 'Alertas del documento seleccionado' })
    expect(within(alertas).getByText('Preventiva (1)')).toBeTruthy()
  })

  it('documento en error por fallo de S3 o del motor, sin SYS-00x: se explica sin codigo', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000003')
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: /comprobante_domicilio_sano_escaneado\.pdf/ }))
    const error = screen.getByRole('alert')
    expect(error.textContent).toContain('El análisis de este documento falló.')
    expect(error.textContent).toContain('No se pudo procesar el archivo (fallo al leerlo o del motor de análisis)')
    expect(error.textContent).not.toContain('SYS-')
    // no cubre su tipo: la EXP-001 del comprobante sigue
    expect(within(screen.getByRole('region', { name: 'Alertas del expediente' })).getByText('EXP-001')).toBeTruthy()
  })

  it('documento en error: mensaje y SYS-001, sin opcion de reprocesar', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('ONB-2026-000003')
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: /pasaporte_sano_foto\.jpg/ }))
    const error = screen.getByRole('alert')
    expect(error.textContent).toContain('El análisis de este documento falló.')
    expect(error.textContent).toContain('SYS-001: Fallo del proveedor principal y sin respaldo')
    expect(error.textContent).toContain('queda fuera del MVP')
    expect(screen.queryByRole('button', { name: /reprocesar/i })).toBeNull()
  })

  it('el integrador ve el expediente pero no el original (solo revisor y admin)', async () => {
    await entrarComo('integrador.demo')
    montarExpediente('ONB-2026-000002')
    expect(await screen.findByText('Tu rol no puede ver el original del documento.')).toBeTruthy()
    expect(mock.peticiones.some((p) => p.endsWith('/original'))).toBe(false)
  })

  it('polling del expediente cada 3 s mientras haya documentos en curso, y se para al terminar', async () => {
    await entrarComo('revisor.demo')
    const cabeceras = { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` }
    const { folio } = await (await fetch(`${API}/folios`, { method: 'POST', headers: cabeceras, body: JSON.stringify({ proceso: 'onboarding' }) })).json()
    const formulario = new FormData()
    const nombre = 'credencial_elector_sano_digital.pdf'
    formulario.append('archivo', new File([readFileSync(join(ORIGINALES, nombre))], nombre))
    const { identificador_unico_documento: id } = await (await fetch(`${API}/folios/${folio}/documentos`,
      { method: 'POST', headers: { Authorization: `Bearer ${token()}` }, body: formulario })).json()

    montarExpediente(folio)
    expect((await screen.findByTestId(`estado-${id}`)).textContent).toBe('Pendiente')
    await waitFor(() => expect(peticiones(`GET /folios/${folio}`)).toBeGreaterThan(2)) // sondea
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`estado-${id}`).textContent).toBe('Completado'))
    const tras = peticiones(`GET /folios/${folio}`)
    await new Promise((r) => setTimeout(r, 150)) // 5 intervalos de 30 ms
    expect(peticiones(`GET /folios/${folio}`)).toBe(tras) // ya no sondea
  })
})

describe('sondeo con limite en el expediente', () => {
  it('sin cambios durante el limite muestra "Sigue en proceso" y "Comprobar de nuevo" lo reanuda', async () => {
    await entrarComo('revisor.demo')
    montar('/folios/ONB-2026-000002', (
      <Routes><Route path="/folios/:folio" element={
        <PaginaExpediente tiemposSondeo={{ inicialMs: 10, maximoMs: 20, limiteSinCambiosMs: 150 }} />} /></Routes>
    ))
    const aviso = await screen.findByText(/Sigue en proceso/, {}, { timeout: 2000 })
    expect(aviso.closest('[role="status"]')).toBeTruthy()
    const antes = peticiones('GET /folios/ONB-2026-000002')
    await new Promise((r) => setTimeout(r, 100))
    expect(peticiones('GET /folios/ONB-2026-000002')).toBe(antes) // detenido: ya no consulta
    await userEvent.setup().click(screen.getByRole('button', { name: 'Comprobar de nuevo' }))
    await waitFor(() => expect(peticiones('GET /folios/ONB-2026-000002')).toBeGreaterThan(antes))
  })
})
