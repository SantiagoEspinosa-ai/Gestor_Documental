// Utilidades para los tests de la pagina del expediente: montarla en una ruta, esperar a que cargue y
// moverse entre la lista de documentos y el detalle de uno (?doc=).
import { screen, within } from '@testing-library/react'
import type userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { PaginaExpediente } from '../paginas/PaginaExpediente'
import type { TiemposSondeo } from '../utilidades/sondeo'
import { montar } from './app'

type Usuario = ReturnType<typeof userEvent.setup>

const escapar = (texto: string) => texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** `ruta`: /folios/<folio> con ?pestana= o ?doc= si hace falta */
export function montarExpediente(ruta: string, tiempos: Partial<TiemposSondeo> = { inicialMs: 30, maximoMs: 30 }) {
  return montar(ruta, (
    <Routes><Route path="/folios/:folio" element={<PaginaExpediente tiemposSondeo={tiempos} />} /></Routes>
  ))
}

/** Espera a que el expediente haya cargado (cabecera y pestanas) */
export async function esperarExpediente(folio: string): Promise<void> {
  await screen.findByRole('navigation', { name: 'Secciones del expediente' })
  screen.getByRole('heading', { level: 1, name: `Expediente ${folio}` })
}

/** Rejilla de documentos de la pestana Documentos */
export const rejilla = () => screen.getByRole('region', { name: 'Documentos del folio' })

/** Tarjeta de un documento por su nombre de fichero */
export function tarjeta(nombre: string): HTMLElement {
  const enlace = within(rejilla()).getByRole('link', { name: new RegExp(`^Abrir( y revisar)? ${escapar(nombre)}$`) })
  return enlace.closest('article')!
}

/** "Abrir y revisar" (o "Abrir") de un documento desde la lista */
export async function abrirDocumento(u: Usuario, nombre: string): Promise<void> {
  await u.click(within(tarjeta(nombre)).getByRole('link', { name: new RegExp(`^Abrir( y revisar)? `) }))
  await screen.findByRole('link', { name: /Todos los documentos/ })
}

/** "← Todos los documentos" */
export async function volverALaLista(u: Usuario): Promise<void> {
  await u.click(screen.getByRole('link', { name: /Todos los documentos/ }))
  await screen.findByRole('region', { name: 'Documentos del folio' })
}

/** Abre "Detalles tecnicos" del documento */
export async function abrirDetallesTecnicos(u: Usuario): Promise<HTMLElement> {
  const detalles = screen.getByTestId('detalles-tecnicos')
  if (!(detalles as HTMLDetailsElement).open) await u.click(within(detalles).getByText('Detalles técnicos'))
  return detalles
}
