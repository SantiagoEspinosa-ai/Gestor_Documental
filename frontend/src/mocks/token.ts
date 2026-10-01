// Token FICTICIO de los mocks: como un JWT, lleva dentro el usuario y la caducidad y se valida sin
// memoria del servidor, asi que la sesion sobrevive a una recarga de la pagina (msw arranca de cero).
// Formato: mock.<carga en base64url>.<firma>. La "firma" es un hash FNV-1a con una constante publica:
// solo detecta un token retocado a mano; no es seguridad (todo esto vive en el navegador).
import { USUARIOS_DEMO, type UsuarioDemo } from './usuarios'

const PREFIJO = 'mock'
const SAL_DE_PRUEBA = 'firma-ficticia-de-los-mocks' // no es un secreto: los mocks no protegen nada

interface Carga {
  /** usuario */
  u: string
  /** caducidad, ms desde 1970 */
  exp: number
  /** emitido en, ms: distingue dos logins del mismo usuario */
  iat: number
}

export type ResultadoToken =
  | { valido: true; usuario: UsuarioDemo; expiraEn: number }
  | { valido: false; motivo: 'no_valido' | 'caducado' }

function fnv1a(texto: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

const aBase64Url = (texto: string) => btoa(texto).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
const deBase64Url = (texto: string) => atob(texto.replaceAll('-', '+').replaceAll('_', '/'))

export function emitirToken(usuario: string, expiraEn: number, emitidoEn: number): string {
  const carga = aBase64Url(JSON.stringify({ u: usuario, exp: expiraEn, iat: emitidoEn } satisfies Carga))
  return `${PREFIJO}.${carga}.${fnv1a(`${SAL_DE_PRUEBA}.${carga}`)}`
}

/** Comprueba formato, firma, usuario y caducidad (con el reloj de los mocks) */
export function validarToken(token: string, ahora: number): ResultadoToken {
  const partes = token.split('.')
  if (partes.length !== 3 || partes[0] !== PREFIJO || fnv1a(`${SAL_DE_PRUEBA}.${partes[1]}`) !== partes[2]) {
    return { valido: false, motivo: 'no_valido' }
  }
  let carga: Partial<Carga>
  try {
    carga = JSON.parse(deBase64Url(partes[1])) as Partial<Carga>
  } catch {
    return { valido: false, motivo: 'no_valido' }
  }
  const usuario = USUARIOS_DEMO.find((u) => u.usuario === carga.u)
  if (!usuario || typeof carga.exp !== 'number') return { valido: false, motivo: 'no_valido' }
  if (carga.exp <= ahora) return { valido: false, motivo: 'caducado' }
  return { valido: true, usuario, expiraEn: carga.exp }
}
