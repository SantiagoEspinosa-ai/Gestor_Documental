// @vitest-environment jsdom
// Zoom del original (imagenes) y "Abrir en pestana nueva" (PDF), contra los mocks. Ninguna accion de zoom
// vuelve a pedir el original: cada GET /documentos/{id}/original deja `original_visto` (ADR-010 A4b).
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { entrarComo, montar, usarServidorMock } from '../pruebas/app'
import { VisorOriginal } from './VisorOriginal'

const mock = usarServidorMock()
const FOTO = { id: '00000000-0000-4000-8000-000002000002', nombre: 'comprobante_domicilio_domicilio_distinto_foto.jpg' }
const PDF = { id: '00000000-0000-4000-8000-000002000001', nombre: 'credencial_elector_domicilio_distinto_escaneado.pdf' }
const pedidas = (id: string) => mock.peticiones.filter((p) => p === `GET /documentos/${id}/original`).length

async function abrir(doc: { id: string; nombre: string }) {
  await entrarComo('revisor.demo')
  montar('/', <VisorOriginal documentoId={doc.id} nombreArchivo={doc.nombre} />)
  if (doc.nombre.endsWith('.pdf')) await screen.findByTitle(`Original: ${doc.nombre}`)
  else await screen.findByAltText(`Original: ${doc.nombre}`)
  return userEvent.setup()
}
const zoom = () => screen.getByTestId('zoom').textContent
const boton = (nombre: string) => screen.getByRole('button', { name: nombre }) as HTMLButtonElement
const transformacion = () => (screen.getByAltText(`Original: ${FOTO.nombre}`) as HTMLImageElement).style.transform

describe('zoom en una imagen', () => {
  it('acercar y alejar de 25 en 25, con limites de 50 % y 400 %', async () => {
    const u = await abrir(FOTO)
    expect(zoom()).toBe('100 %')
    await u.click(boton('Acercar'))
    expect(zoom()).toBe('125 %')
    expect(transformacion()).toContain('scale(1.25)')
    for (let i = 0; i < 20; i++) if (!boton('Acercar').disabled) await u.click(boton('Acercar'))
    expect(zoom()).toBe('400 %')
    expect(boton('Acercar').disabled).toBe(true)
    for (let i = 0; i < 20; i++) if (!boton('Alejar').disabled) await u.click(boton('Alejar'))
    expect(zoom()).toBe('50 %')
    expect(boton('Alejar').disabled).toBe(true)
  })

  it('"Ajustar" vuelve al 100 % y al centro', async () => {
    const u = await abrir(FOTO)
    await u.click(boton('Acercar'))
    await u.click(boton('Acercar'))
    screen.getByTestId('marco-zoom').focus()
    await u.keyboard('{ArrowLeft}{ArrowUp}') // con zoom, las flechas la mueven
    expect(transformacion()).toBe('translate(40px, 40px) scale(1.5)')
    await u.click(boton('Ajustar'))
    expect(zoom()).toBe('100 %')
    expect(transformacion()).toBe('translate(0px, 0px) scale(1)')
    expect(boton('Ajustar').disabled).toBe(true)
  })

  it('Ctrl + rueda hace zoom; la rueda sola no', async () => {
    await abrir(FOTO)
    const marco = screen.getByTestId('marco-zoom')
    fireEvent.wheel(marco, { deltaY: -100 })
    expect(zoom()).toBe('100 %')
    fireEvent.wheel(marco, { deltaY: -100, ctrlKey: true })
    expect(zoom()).toBe('125 %')
    fireEvent.wheel(marco, { deltaY: 100, ctrlKey: true })
    fireEvent.wheel(marco, { deltaY: 100, ctrlKey: true })
    expect(zoom()).toBe('75 %')
  })

  it('sin zoom la imagen no se mueve', async () => {
    const u = await abrir(FOTO)
    screen.getByTestId('marco-zoom').focus()
    await u.keyboard('{ArrowLeft}')
    expect(transformacion()).toBe('translate(0px, 0px) scale(1)')
  })

  it('"Pantalla completa" abre un dialogo con la misma imagen; Esc lo cierra y el foco vuelve', async () => {
    const u = await abrir(FOTO)
    await u.click(boton('Pantalla completa'))
    const dialogo = screen.getByRole('dialog', { name: `Pantalla completa: ${FOTO.nombre}` })
    expect(dialogo.getAttribute('aria-modal')).toBe('true')
    const imagen = within(dialogo).getByAltText(`Original: ${FOTO.nombre}`) as HTMLImageElement
    expect(imagen.src).toBe((screen.getAllByAltText(`Original: ${FOTO.nombre}`)[0] as HTMLImageElement).src)
    expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: /Cerrar/ }))
    await u.click(within(dialogo).getByRole('button', { name: 'Acercar' })) // con su propio zoom
    expect(within(dialogo).getByTestId('zoom').textContent).toBe('125 %')
    await u.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(boton('Pantalla completa'))
  })

  it('el zoom, el arrastre y la pantalla completa no vuelven a pedir el original; "Volver a cargar" si', async () => {
    const u = await abrir(FOTO)
    expect(pedidas(FOTO.id)).toBe(1)
    await u.click(boton('Acercar'))
    await u.click(boton('Alejar'))
    fireEvent.wheel(screen.getByTestId('marco-zoom'), { deltaY: -100, ctrlKey: true })
    screen.getByTestId('marco-zoom').focus()
    await u.keyboard('{ArrowRight}')
    await u.click(boton('Ajustar'))
    await u.click(boton('Pantalla completa'))
    await u.keyboard('{Escape}')
    expect(pedidas(FOTO.id)).toBe(1)
    await u.click(boton('Volver a cargar'))
    await screen.findByAltText(`Original: ${FOTO.nombre}`)
    expect(pedidas(FOTO.id)).toBe(2)
  })
})

describe('PDF', () => {
  it('se queda con el visor del navegador y "Abrir en pestaña nueva" usa la misma URL, sin pedirla otra vez', async () => {
    await abrir(PDF)
    const iframe = screen.getByTitle(`Original: ${PDF.nombre}`)
    const enlace = screen.getByRole('link', { name: 'Abrir en pestaña nueva' })
    expect(enlace.getAttribute('href')).toBe(iframe.getAttribute('src'))
    expect(enlace.getAttribute('target')).toBe('_blank')
    expect(enlace.getAttribute('rel')).toBe('noopener noreferrer')
    expect(screen.queryByRole('toolbar', { name: 'Zoom de la imagen' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Pantalla completa' })).toBeNull()
    expect(pedidas(PDF.id)).toBe(1)
  })
})
