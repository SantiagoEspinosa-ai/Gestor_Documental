import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import { ProveedorSesion } from './componentes/ProveedorSesion'
import './index.css'

async function arrancar() {
  // Mocks de msw solo en desarrollo y con VITE_USAR_MOCKS=true. La condicion va escrita con
  // import.meta.env para que en `npm run build` sea `false` y el bundler elimine el import
  // (scripts/comprobar-build-sin-mocks.mjs lo verifica en cada build).
  if (import.meta.env.DEV && import.meta.env.VITE_USAR_MOCKS === 'true') {
    await (await import('./mocks/navegador')).iniciarMocks()
  }
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
