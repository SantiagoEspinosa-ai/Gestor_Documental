// Formato de los valores extraidos segun el tipo del campo de la ficha (texto, fecha, anio).

/** Un campo sin valor es null (nunca "" ni solo espacios): la UI lo muestra asi */
export const TEXTO_NO_DETECTADO = 'no detectado'

export function sinValor(valor: unknown): boolean {
  return valor === null || valor === undefined || (typeof valor === 'string' && !valor.trim())
}

/** Valor listo para mostrar: fechas ISO como DD/MM/AAAA; null como "no detectado" */
export function formatearValor(valor: unknown, tipo?: string | null): string {
  if (sinValor(valor)) return TEXTO_NO_DETECTADO
  if (tipo === 'fecha' && typeof valor === 'string') {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor)
    if (m) return `${m[3]}/${m[2]}/${m[1]}`
  }
  if (typeof valor === 'object') return JSON.stringify(valor)
  return String(valor)
}

/** Anio de 4 cifras (1000-9999): sin ceros a la izquierda, para que siga teniendo 4 cifras como entero */
export const PATRON_ANIO = /^[1-9]\d{3}$/

export const MOTIVO_OBLIGATORIO = 'Este campo es obligatorio: no se puede dejar vacío.'
export const MOTIVO_ANIO = 'El año debe tener 4 cifras (AAAA), por ejemplo 2029.'

export type CorreccionPreparada = { valida: true; valor: unknown } | { valida: false; motivo: string }

/**
 * Valor corregido para el PATCH de datos, segun la ficha (decidido con PERSONA_1 en el PR #10):
 * - vacio o solo espacios: null en un campo opcional (nunca ""); en uno obligatorio no se puede enviar;
 * - anio: entero de 4 cifras; otro formato no se puede enviar;
 * - el resto: el texto sin espacios a los lados.
 */
export function prepararCorreccion(texto: string, campo: { tipo?: string | null; obligatorio?: boolean } = {}): CorreccionPreparada {
  const limpio = texto.trim()
  if (!limpio) return campo.obligatorio ? { valida: false, motivo: MOTIVO_OBLIGATORIO } : { valida: true, valor: null }
  if (campo.tipo === 'anio') {
    return PATRON_ANIO.test(limpio) ? { valida: true, valor: Number(limpio) } : { valida: false, motivo: MOTIVO_ANIO }
  }
  return { valida: true, valor: limpio }
}

/** Nombre legible de un campo tecnico: fecha_nacimiento -> "Fecha nacimiento" */
export function nombreCampo(campo: string): string {
  const texto = campo.replaceAll('_', ' ')
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

/** Confianza 0..1 como porcentaje entero */
export function porcentaje(valor: number): string {
  return `${Math.round(valor * 100)} %`
}
