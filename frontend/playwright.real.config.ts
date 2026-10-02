// e2e REALES (H6): la UI contra la API real con el motor stub, sin mocks. npm run test:e2e:real
// No arranca servidores: exige el backend en :8000 y `npm run dev` en :5173 con VITE_USAR_MOCKS=false
// (lo comprueba e2e-real/comprobar-servidores.ts antes de empezar). Usuarios solo por variables de entorno.
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: 'e2e-real',
  testMatch: '**/*.e2e.ts', // nunca *.test.ts (Vitest) y nunca e2e/ (los de los mocks)
  globalSetup: './e2e-real/comprobar-servidores.ts',
  workers: 1, // un solo analisis a la vez en el backend (MAX_PROCESAMIENTOS_SIMULTANEOS=1)
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    // Sin traza: guardaria lo escrito en el formulario de login y el cuerpo de POST /auth/login (las
    // contrasenas). Captura solo si falla: el campo de contrasena sale con puntos (type=password)
    trace: 'off',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
