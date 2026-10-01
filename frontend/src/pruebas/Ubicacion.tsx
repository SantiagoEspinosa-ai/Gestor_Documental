// Solo para los tests de pantallas (fichero aparte: solo exporta un componente)
import { useLocation } from 'react-router'

/** Muestra la ruta completa actual del router (data-testid="ubicacion"), para comprobar redirecciones */
export function Ubicacion() {
  const { pathname, search, hash } = useLocation()
  return <output data-testid="ubicacion">{`${pathname}${search}${hash}`}</output>
}
