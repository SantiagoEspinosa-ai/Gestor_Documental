import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import { ProveedorSesion } from './componentes/ProveedorSesion'
import './index.css'
import { entorno } from './utilidades/entorno'

async function arrancar() {
  // Mocks de msw solo con VITE_USAR_MOCKS=true; en otro caso ni se descargan
  if (entorno.usarMocks) await (await import('./mocks/navegador')).iniciarMocks()
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <BrowserRouter>
        <ProveedorSesion>
          <App />
        </ProveedorSesion>
      </BrowserRouter>
    </StrictMode>,
  )
}

void arrancar()
