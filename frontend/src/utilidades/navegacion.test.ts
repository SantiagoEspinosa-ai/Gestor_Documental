import { describe, expect, it } from 'vitest'
import { RUTA_POR_DEFECTO, rutaCompleta, rutaInternaSegura } from './navegacion'

describe('vuelta tras el login', () => {
  it('rutaCompleta junta pathname, search y hash', () => {
    expect(rutaCompleta({ pathname: '/auditoria', search: '?folio=ONB-2026-000004&tamano_pagina=20', hash: '#tabla' }))
      .toBe('/auditoria?folio=ONB-2026-000004&tamano_pagina=20#tabla')
    expect(rutaCompleta({ pathname: '/folios', search: '', hash: '' })).toBe('/folios')
  })

  it.each([
    '/folios',
    '/folios/ONB-2026-000001',
    '/folios/ONB-2026-000001/carga',
    '/auditoria?folio=ONB-2026-000004&tamano_pagina=20#tabla',
    '/auditoria?siguiente=https://otro.example', // una URL dentro de la query no cambia el destino
    '/folios/ONB-2026-000001#documento-2',
  ])('acepta la ruta interna %s tal cual', (ruta) => {
    expect(rutaInternaSegura(ruta)).toBe(ruta)
  })

  it.each([
    ['URL absoluta', 'https://otro.example/folios'],
    ['protocolo relativo', '//otro.example/folios'],
    ['tres barras', '///otro.example'],
    ['barra invertida', '/\\otro.example'],
    ['barra invertida dentro', '/folios\\..\\..'],
    ['tabulador que el navegador quita', '/\t/otro.example'],
    ['salto de linea', '/\n/otro.example'],
    ['javascript:', 'javascript:alert(1)'],
    ['ruta relativa', 'folios'],
    ['vacia', ''],
    ['el propio login', '/login'],
    ['el login con parametros', '/login?x=1'],
    ['no es texto', 42],
    ['null', null],
    ['undefined', undefined],
  ])('rechaza %s', (_motivo, valor) => {
    expect(rutaInternaSegura(valor)).toBe(RUTA_POR_DEFECTO)
  })

  it('admite otra ruta por defecto', () => {
    expect(rutaInternaSegura('//otro.example', '/auditoria')).toBe('/auditoria')
  })
})
