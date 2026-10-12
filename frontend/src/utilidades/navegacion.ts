// Vuelta tras el login: la ruta completa que se pidio (pathname, search y hash), solo si es interna.
import type { Location } from 'react-router'

export const RUTA_POR_DEFECTO = '/folios'
const ORIGEN_FICTICIO = 'http://app.invalid'

/** Barra invertida o caracter de control (U+0000-U+001F y U+007F) */
const esPeligroso = (caracter: string) => {
  const codigo = caracter.charCodeAt(0)
  return caracter === '\\' || codigo < 0x20 || codigo === 0x7f
}

/** Ruta completa de una ubicacion del router: /auditoria?folio=X#arriba */
export function rutaCompleta(ubicacion: Pick<Location, 'pathname' | 'search' | 'hash'>): string {
  return `${ubicacion.pathname}${ubicacion.search}${ubicacion.hash}`
}

/**
 * Devuelve `valor` si es una ruta interna de la app; si no, la ruta por defecto. Evita redirecciones
 * a otros sitios: solo una "/" inicial (nunca "//" ni una URL absoluta), sin barras invertidas ni
 * caracteres de control (los navegadores convierten "/\x" o "/\t/x" en "//x") y que al resolverla se
 * quede en el mismo origen. Tampoco /login, para no volver al propio formulario.
 */
export function rutaInternaSegura(valor: unknown, porDefecto: string = RUTA_POR_DEFECTO): string {
  if (typeof valor !== 'string' || !valor.startsWith('/') || valor.startsWith('//')) return porDefecto
  if ([...valor].some(esPeligroso)) return porDefecto
  let url: URL
  try {
    url = new URL(valor, ORIGEN_FICTICIO)
  } catch {
    return porDefecto
  }
  if (url.origin !== ORIGEN_FICTICIO || url.pathname === '/login') return porDefecto
  return valor
}

// ------------------------------------------------------------------ pestanas del expediente

export type Pestana = 'documentos' | 'carga' | 'resumen'

/** Enlaces de cada pestana: se pueden compartir y el boton atras funciona */
export function rutaPestana(folio: string, pestana: Pestana, documento?: string): string {
  const base = `/folios/${encodeURIComponent(folio)}`
  if (pestana === 'carga') return `${base}/carga`
  if (pestana === 'resumen') return `${base}?pestana=resumen`
  return documento ? `${base}?doc=${encodeURIComponent(documento)}` : base
}
