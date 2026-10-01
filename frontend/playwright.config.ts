// e2e con Playwright sobre los mocks de msw (VITE_USAR_MOCKS=true): npm run test:e2e
// Solo Chromium. El estado de los mocks vive en la memoria de la pagina: cada test empieza con los datos
// iniciales y navega dentro de la app (sin recargar) para no perderlo.
import { defineConfig, devices } from '@playwright/test'

// Puerto propio para no chocar con un `npm run dev` abierto (5173)
const PUERTO = 5174

export default defineConfig({
  testDir: 'e2e',
  testMatch: '**/*.e2e.ts', // nunca *.test.ts: esos son de Vitest (npm test)
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PUERTO}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${PUERTO}`,
    url: `http://localhost:${PUERTO}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // Las variables del proceso mandan sobre frontend/.env: siempre con mocks
    env: { VITE_USAR_MOCKS: 'true', VITE_API_URL: 'http://localhost:8000' },
  },
})
