// Falla si el build de produccion (dist/) contiene algo de los mocks de msw.
// Se ejecuta al final de `npm run build`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const dist = fileURLToPath(new URL('../dist/', import.meta.url))
// Rastros inconfundibles de src/mocks y de public/mockServiceWorker.js
const PROHIBIDOS = ['mockServiceWorker', 'setupWorker', '[mocks]', 'demo-revisor', 'demo-admin', 'demo-integrador',
  'ONB-2026-000001', 'mock-originales']

if (!existsSync(dist)) {
  console.error('No existe dist/: ejecuta antes `vite build`')
  process.exit(1)
}

const ficheros = []
const recorrer = (dir) => readdirSync(dir).forEach((n) => {
  const ruta = join(dir, n)
  if (statSync(ruta).isDirectory()) recorrer(ruta)
  else ficheros.push(ruta)
})
recorrer(dist)

const problemas = []
for (const ruta of ficheros) {
  const nombre = relative(dist, ruta).replaceAll('\\', '/')
  if (/mock/i.test(nombre)) problemas.push(`fichero de mocks: ${nombre}`)
  const contenido = readFileSync(ruta, 'latin1')
  for (const p of PROHIBIDOS) if (contenido.includes(p)) problemas.push(`${nombre} contiene "${p}"`)
}

if (problemas.length) {
  console.error(`El build incluye mocks:\n  - ${problemas.join('\n  - ')}`)
  process.exit(1)
}
console.log(`Build sin mocks: ${ficheros.length} ficheros revisados en dist/`)
