// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MS_HASTA_COMPLETADO } from '../mocks/logica'
import { entrarComo, usarServidorMock } from '../pruebas/app'
import {
  abrirDetallesTecnicos, abrirDocumento, esperarExpediente, montarExpediente, rejilla, tarjeta, volverALaLista,
} from '../pruebas/expediente'

const mock = usarServidorMock()
const ORIGINALES = join(process.cwd(), 'public', 'mock-originales')
const API = 'http://localhost:8000/api/v1'
const token = () => JSON.parse(sessionStorage.getItem('gestor_documental.sesion')!).token as string

async function abrir(folio: string, ruta = `/folios/${folio}`) {
  montarExpediente(ruta)
  await esperarExpediente(folio)
  return userEvent.setup()
}
const peticiones = (texto: string) => mock.peticiones.filter((p) => p === texto).length
const fila = (campo: string) => within(screen.getByRole('region', { name: 'Datos leídos' })).getByRole('rowheader', { name: campo }).closest('tr')!
const tecnico = (campo: string) => screen.getByTestId(`tecnico-${campo}`)

describe('documento no reconocido (ADR-009, H4)', () => {
  const NO_RECONOCIDO = 'pasaporte_sano_escaneado.pdf'

  it('tarjeta y detalle "Tipo no reconocido", aviso en lugar de la tabla vacía; el revisor puede confirmar el tipo', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000003')
    const carta = tarjeta(NO_RECONOCIDO)
    expect(within(carta).getByRole('heading').textContent).toBe('Tipo no reconocido')
    expect(within(carta).getByTestId(/^semaforo-/).getAttribute('data-color')).toBe('amarillo')
    await abrirDocumento(u, NO_RECONOCIDO)
    expect(screen.getByTestId('tipo-documento').textContent).toBe('Tipo no reconocido')
    await abrirDetallesTecnicos(u)
    const clasificacion = screen.getByRole('region', { name: 'Clasificación' })
    expect(within(clasificacion).getByText('Detectado').nextElementSibling!.textContent).toBe('Tipo no reconocido')
    expect(within(clasificacion).getByText('Declarado').nextElementSibling!.textContent).toBe('—')
    expect(screen.getByText(/No se han extraído datos: el tipo del documento no está reconocido/)).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Datos leídos' })).toBeNull()
    expect(screen.queryByText('desconocido')).toBeNull()
    // Sin tipo reconocido el formulario de cambio de tipo sale ya abierto
    expect(screen.getByRole('button', { name: 'Confirmar clasificación' })).toBeTruthy()
  })

  it('el admin ve el aviso pero no puede confirmar la clasificación', async () => {
    await entrarComo('admin.demo')
    const u = await abrir('ONB-2026-000003')
    await abrirDocumento(u, NO_RECONOCIDO)
    expect(await screen.findByText(/No se han extraído datos/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Confirmar clasificación' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cambiar tipo' })).toBeNull()
  })
})

describe('vista de expediente', () => {
  it('cabecera de un folio cerrado: referencia, fecha, proceso, estado y la decisión al final de la página', async () => {
    await entrarComo('revisor.demo')
    await abrir('ONB-2026-000004')
    const cabecera = screen.getByRole('heading', { level: 1 }).closest('header')!
    expect(within(cabecera).getByText(/Referencia CLI-000102/)).toBeTruthy()
    expect(within(cabecera).getByText('onboarding')).toBeTruthy()
    expect(cabecera.textContent).toContain('Aprobado') // estado_general
    expect(within(cabecera).getByRole('status').textContent).toContain('Folio cerrado: solo lectura.')
    const decision = within(screen.getByTestId('seccion-decision')).getByRole('status').textContent!
    expect(decision).toContain('Decisión: Aprobado')
    expect(decision).toContain('“Documentacion completa y coherente”')
    expect(decision).toContain('revisor.demo')
    expect(decision).toContain('Folio cerrado')
    // Cerrado: la pestana de carga se ve deshabilitada y dice por que
    const secciones = screen.getByRole('navigation', { name: 'Secciones del expediente' })
    expect(within(secciones).queryByRole('link', { name: /Cargar documentos/ })).toBeNull()
    const carga = within(secciones).getByText(/Cargar documentos/).closest('[aria-disabled]')!
    expect(carga.getAttribute('aria-disabled')).toBe('true')
    expect(carga.textContent).toContain('folio cerrado: no se pueden subir documentos')
  })

  it('folio abierto: la pestaña de carga es un enlace a /carga', async () => {
    await entrarComo('revisor.demo')
    await abrir('ONB-2026-000002')
    const secciones = screen.getByRole('navigation', { name: 'Secciones del expediente' })
    expect(within(secciones).getByRole('link', { name: 'Cargar documentos' }).getAttribute('href')).toBe('/folios/ONB-2026-000002/carga')
    expect(within(secciones).getByRole('link', { name: 'Documentos · 3' }).getAttribute('aria-current')).toBe('page')
  })

  it('detalle: original en iframe o img pedido cada vez, datos con corrección y sin valor como "No detectado"', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000002')
    // Credencial escaneada (PDF) con una corrección del propio revisor
    await abrirDocumento(u, 'credencial_elector_domicilio_distinto_escaneado.pdf')
    const iframe = await screen.findByTitle('Original: credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(iframe.getAttribute('src')).toMatch(/mock-originales\/credencial_elector_domicilio_distinto_escaneado\.pdf\?firma=\d+$/)
    expect(within(fila('Nombre completo')).getByText('Corregido por ti (antes: ANA EJEMPL0 PRUEBA)')).toBeTruthy()
    await abrirDetallesTecnicos(u)
    expect(screen.getByRole('meter', { name: 'Confianza verificada de la clasificación' })).toBeTruthy()

    // Foto (JPG) con el proveedor sin leer: fila en ámbar "No detectado", confianza 0 y VAL-004 informativa
    await volverALaLista(u)
    await abrirDocumento(u, 'comprobante_domicilio_domicilio_distinto_foto.jpg')
    expect(await screen.findByAltText('Original: comprobante_domicilio_domicilio_distinto_foto.jpg')).toBeTruthy()
    const proveedor = fila('Proveedor')
    expect(within(proveedor).getByText('No detectado · míralo en el original')).toBeTruthy()
    expect(proveedor.className).toContain('bg-semaforo-ambar-fondo')
    expect(within(proveedor).getByRole('button', { name: 'Escribir el valor de Proveedor' })).toBeTruthy()
    await abrirDetallesTecnicos(u)
    expect(within(tecnico('proveedor')).getByText('0 %')).toBeTruthy()
    const avisos = screen.getByRole('region', { name: 'Avisos de este documento' })
    expect(within(avisos).getByText('Informativa (1)')).toBeTruthy()
    expect(within(avisos).getByText('VAL-004')).toBeTruthy()

    // La URL caduca: al volver a abrir un documento se pide otra
    const antes = peticiones('GET /documentos/00000000-0000-4000-8000-000002000001/original')
    await volverALaLista(u)
    await abrirDocumento(u, 'credencial_elector_domicilio_distinto_escaneado.pdf')
    await screen.findByTitle('Original: credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(peticiones('GET /documentos/00000000-0000-4000-8000-000002000001/original')).toBe(antes + 1)

    // Comparaciones en la lista, con el valor de cada documento, y CMP-001 en las alertas del expediente
    await volverALaLista(u)
    const domicilio = screen.getByTestId('comparacion-domicilio')
    expect(within(domicilio).getByText('No coincide')).toBeTruthy()
    expect(within(domicilio).getByText(/Comprobante de domicilio \(comprobante_domicilio_domicilio_distinto_foto\.jpg\)/)).toBeTruthy()
    const expediente = screen.getByRole('region', { name: 'Alertas del expediente' })
    expect(within(expediente).getByText('Crítica (1)')).toBeTruthy()
    expect(within(expediente).getByText('CMP-001')).toBeTruthy()
  })

  it('confianza bajo el umbral de la ficha (detalles técnicos) y fecha con el tipo del campo', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, 'credencial_elector_vencido_foto.jpg')
    expect(within(fila('Fecha nacimiento')).getByText(/^\d{2}\/\d{2}\/\d{4}$/)).toBeTruthy()
    await abrirDetallesTecnicos(u)
    expect(within(tecnico('clave_elector')).getByText(/bajo el mínimo \(80 %\)/)).toBeTruthy()
    const avisos = screen.getByRole('region', { name: 'Avisos de este documento' })
    expect(within(avisos).getByText('Preventiva (1)')).toBeTruthy()
  })

  it('documento en error por fallo de S3 o del motor, sin SYS-00x: rojo "No se pudo leer", se explica sin código', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000003')
    const carta = tarjeta('comprobante_domicilio_sano_escaneado.pdf')
    expect(within(carta).getByTestId(/^semaforo-/).textContent).toBe('No se pudo leer')
    expect(within(carta).getByRole('link', { name: /Volver a subir/ }).getAttribute('href')).toBe('/folios/ONB-2026-000003/carga')
    await abrirDocumento(u, 'comprobante_domicilio_sano_escaneado.pdf')
    const error = screen.getByRole('alert')
    expect(error.textContent).toContain('El análisis de este documento falló.')
    expect(error.textContent).toContain('No se pudo procesar el archivo (fallo al leerlo o del motor de análisis)')
    expect(error.textContent).not.toContain('SYS-')
    // no cubre su tipo: la EXP-001 del comprobante sigue
    await volverALaLista(u)
    expect(within(screen.getByRole('region', { name: 'Alertas del expediente' })).getByText('EXP-001')).toBeTruthy()
  })

  it('documento en error: mensaje y SYS-001, sin opción de reprocesar', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000003')
    await abrirDocumento(u, 'pasaporte_sano_foto.jpg')
    const error = screen.getByRole('alert')
    expect(error.textContent).toContain('El análisis de este documento falló.')
    expect(error.textContent).toContain('SYS-001: Fallo del proveedor principal y sin respaldo')
    expect(error.textContent).toContain('queda fuera del MVP')
    expect(screen.queryByRole('button', { name: /reprocesar/i })).toBeNull()
  })

  it('el integrador ve el expediente ("Abrir") pero no el original (solo revisor y admin)', async () => {
    await entrarComo('integrador.demo')
    const u = await abrir('ONB-2026-000002')
    expect(within(rejilla()).queryByRole('link', { name: /^Abrir y revisar/ })).toBeNull()
    await abrirDocumento(u, 'credencial_elector_domicilio_distinto_escaneado.pdf')
    expect(await screen.findByText('Tu rol no puede ver el original del documento.')).toBeTruthy()
    expect(mock.peticiones.some((p) => p.endsWith('/original'))).toBe(false)
  })

  it('un ?doc= que no está en el folio lo dice', async () => {
    await entrarComo('revisor.demo')
    await abrir('ONB-2026-000002', '/folios/ONB-2026-000002?doc=no-existe')
    expect(screen.getByRole('alert').textContent).toBe('Ese documento no está en el folio.')
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

    montarExpediente(`/folios/${folio}`)
    expect((await screen.findByTestId(`semaforo-${id}`)).getAttribute('data-color')).toBe('en_proceso')
    await waitFor(() => expect(peticiones(`GET /folios/${folio}`)).toBeGreaterThan(2)) // sondea
    mock.t += MS_HASTA_COMPLETADO
    await waitFor(() => expect(screen.getByTestId(`semaforo-${id}`).getAttribute('data-color')).toBe('verde'))
    const tras = peticiones(`GET /folios/${folio}`)
    await new Promise((r) => setTimeout(r, 150)) // 5 intervalos de 30 ms
    expect(peticiones(`GET /folios/${folio}`)).toBe(tras) // ya no sondea
  })
})

describe('sondeo con limite en el expediente', () => {
  it('sin cambios durante el limite muestra "Sigue en proceso" y "Comprobar de nuevo" lo reanuda', async () => {
    await entrarComo('revisor.demo')
    montarExpediente('/folios/ONB-2026-000002', { inicialMs: 10, maximoMs: 20, limiteSinCambiosMs: 150 })
    const aviso = await screen.findByText(/Sigue en proceso/, {}, { timeout: 2000 })
    expect(aviso.closest('[role="status"]')).toBeTruthy()
    const antes = peticiones('GET /folios/ONB-2026-000002')
    await new Promise((r) => setTimeout(r, 100))
    expect(peticiones('GET /folios/ONB-2026-000002')).toBe(antes) // detenido: ya no consulta
    await userEvent.setup().click(screen.getByRole('button', { name: 'Comprobar de nuevo' }))
    await waitFor(() => expect(peticiones('GET /folios/ONB-2026-000002')).toBeGreaterThan(antes))
  })
})

describe('datos como los da el motor real (H3)', () => {
  it('una fecha que el OCR no pudo normalizar se pinta tal cual; evidencia con pagina y seccion', async () => {
    await entrarComo('revisor.demo')
    const u = await abrir('ONB-2026-000001')
    await abrirDocumento(u, 'pasaporte_vencido_escaneado.pdf')
    await screen.findByRole('region', { name: 'Datos leídos' })
    expect(fila('Fecha expedicion').textContent).toContain('30 SEP 2021')
    await abrirDetallesTecnicos(u)
    expect(tecnico('fecha_vencimiento').textContent).toContain('pagina_1:seccion_central')
    expect(screen.getByText(/prompt/).textContent).toMatch(/extraccion_pasaporte@v3/)
  })
})
