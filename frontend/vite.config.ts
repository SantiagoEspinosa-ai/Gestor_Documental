/// <reference types="vitest/config" />
import { rmSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/** Ficheros de public/ que solo sirven a los mocks (msw) y nunca van en un build */
const SOLO_MOCKS_EN_PUBLIC = ['mockServiceWorker.js', 'mock-originales']

function sinMocksEnBuild(): Plugin {
  let salida = 'dist'
  return {
    name: 'sin-mocks-en-build',
    apply: 'build',
    configResolved(config) {
      salida = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      for (const nombre of SOLO_MOCKS_EN_PUBLIC) rmSync(resolve(salida, nombre), { recursive: true, force: true })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), sinMocksEnBuild()],
  // Mismo puerto que el servicio frontend de docker-compose.yml
  server: { port: 5173, strictPort: true },
  // Tests de los mocks en Node (msw/node)
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
