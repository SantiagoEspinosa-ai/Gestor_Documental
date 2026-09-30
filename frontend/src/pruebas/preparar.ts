// Preparacion comun de Vitest (node y jsdom).
import { afterEach } from 'vitest'

if (typeof window !== 'undefined') {
  // Subidas multipart en jsdom: Vitest convierte el FormData de jsdom para el fetch de Node, pero con
  // jsdom 30 cada fichero llega como un Blob vacio y sin nombre. Con el FormData y el File de Node
  // (y el Blob de jsdom intacto) Vitest no convierte los ficheros y llegan a msw con bytes y nombre.
  const { File: FileNode } = await import('node:buffer')
  const FormDataNode = (await new Response(new URLSearchParams('x=1')).formData()).constructor
  Object.assign(globalThis, { FormData: FormDataNode, File: FileNode })

  const { cleanup } = await import('@testing-library/react')
  afterEach(() => {
    cleanup()
    sessionStorage.clear()
  })
}
