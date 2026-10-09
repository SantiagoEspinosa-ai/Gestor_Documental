// Icono y clases de cada color del semaforo (tokens --color-semaforo-* de index.css)
import { AlertTriangle, Archive, CheckCircle2, LoaderCircle, XCircle } from 'lucide-react'
import type { ColorSemaforo } from '../utilidades/semaforo'

export const ESTILO_SEMAFORO: Record<ColorSemaforo, { icono: typeof CheckCircle2; caja: string; texto: string }> = {
  verde: { icono: CheckCircle2, caja: 'border-semaforo-verde-borde bg-semaforo-verde-fondo', texto: 'text-semaforo-verde' },
  amarillo: { icono: AlertTriangle, caja: 'border-semaforo-ambar-borde bg-semaforo-ambar-fondo', texto: 'text-semaforo-ambar' },
  rojo: { icono: XCircle, caja: 'border-semaforo-rojo-borde bg-semaforo-rojo-fondo', texto: 'text-semaforo-rojo' },
  en_proceso: { icono: LoaderCircle, caja: 'border-semaforo-gris-borde bg-semaforo-gris-fondo', texto: 'text-semaforo-gris' },
  retirado: { icono: Archive, caja: 'border-semaforo-gris-borde bg-semaforo-gris-fondo', texto: 'text-semaforo-gris' },
}
