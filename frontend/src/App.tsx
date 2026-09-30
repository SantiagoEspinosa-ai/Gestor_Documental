import { Navigate, Route, Routes } from 'react-router'
import { Estructura } from './componentes/Estructura'
import { RutaProtegida } from './componentes/RutaProtegida'
import { PaginaExpediente } from './paginas/PaginaExpediente'
import { PaginaFolios } from './paginas/PaginaFolios'
import { PaginaLogin } from './paginas/PaginaLogin'
import { PaginaNoEncontrada } from './paginas/PaginaNoEncontrada'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<PaginaLogin />} />
      <Route element={<RutaProtegida />}>
        <Route element={<Estructura />}>
          <Route index element={<Navigate to="/folios" replace />} />
          <Route path="/folios" element={<PaginaFolios />} />
          <Route path="/folios/:folio" element={<PaginaExpediente />} />
        </Route>
      </Route>
      <Route path="*" element={<PaginaNoEncontrada />} />
    </Routes>
  )
}
