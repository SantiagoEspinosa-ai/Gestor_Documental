// Pantalla de procesos (H8): como se muestra el webhook de un proceso

/** Nunca la URL completa (puede llevar una ruta o un token): solo el host */
export function describirWebhook(url: string | null | undefined): string {
  if (!url) return 'Sin webhook'
  try {
    return `Configurado (${new URL(url).host})`
  } catch {
    return 'Configurado'
  }
}
