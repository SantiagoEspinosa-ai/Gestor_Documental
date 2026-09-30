/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Mismo puerto que el servicio frontend de docker-compose.yml
  server: { port: 5173, strictPort: true },
  // Tests de los mocks en Node (msw/node); los de componentes llegaran con la tarea 6
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
