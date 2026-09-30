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

/** Nombre legible de un campo tecnico: fecha_nacimiento -> "Fecha nacimiento" */
export function nombreCampo(campo: string): string {
  const texto = campo.replaceAll('_', ' ')
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

/** Confianza 0..1 como porcentaje entero */
export function porcentaje(valor: number): string {
  return `${Math.round(valor * 100)} %`
}
