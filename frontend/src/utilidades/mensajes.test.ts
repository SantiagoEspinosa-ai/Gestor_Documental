import { describe, expect, it } from 'vitest'
import { ErrorApi } from '../api/cliente'
import { ESTADO_HTTP_CODIGO } from '../tipos/codigos'
import { MENSAJES_ERROR, mensajeDeError } from './mensajes'

describe('mensajes de error', () => {
  it('hay un mensaje para cada código oficial, pendiente de main y local', () => {
    for (const codigo of [...Object.keys(ESTADO_HTTP_CODIGO), 'SIN_CONEXION', 'RESPUESTA_NO_VALIDA']) {
      expect(MENSAJES_ERROR[codigo as keyof typeof MENSAJES_ERROR], codigo).toBeTruthy()
    }
  })

  it('usa el mensaje del código, con el detalle de la API solo en PETICION_INVALIDA', () => {
    expect(mensajeDeError(new ErrorApi(409, 'FOLIO_CERRADO', 'detalle interno'))).toBe('El folio ya está decidido: solo lectura.')
    expect(mensajeDeError(new ErrorApi(422, 'PETICION_INVALIDA', 'Falta `proceso`')))
      .toBe('Los datos enviados no son válidos. Falta `proceso`')
  })

  it('código desconocido: el mensaje de la API; otro error: genérico', () => {
    expect(mensajeDeError(new ErrorApi(418, 'CODIGO_NUEVO', 'Mensaje de la API'))).toBe('Mensaje de la API')
    expect(mensajeDeError(new Error('x'))).toBe('Ha ocurrido un error inesperado.')
  })
})
