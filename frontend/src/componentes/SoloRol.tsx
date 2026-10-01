import type { ReactNode } from 'react'
import type { Rol } from '../tipos/contrato'
import { useRol } from './contextoSesion'

interface Props {
  /** Roles que pueden ver el contenido (los del contrato para esa accion) */
  roles: readonly Rol[]
  children: ReactNode
  /** Lo que se muestra a los demas roles; por defecto, nada */
  alternativa?: ReactNode
}

/** Muestra su contenido solo a los roles indicados. Es solo interfaz: la API vuelve a comprobarlo. */
export function SoloRol({ roles, children, alternativa = null }: Props) {
  const rol = useRol()
  return <>{rol && roles.includes(rol) ? children : alternativa}</>
}
