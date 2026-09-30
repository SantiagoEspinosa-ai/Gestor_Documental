// Preparacion comun de Vitest (node y jsdom).
import { Blob as BlobNode, File as FileNode } from 'node:buffer'
import { afterEach } from 'vitest'

// En jsdom, FormData/File/Blob son los de jsdom, pero fetch es el de Node: un FormData de jsdom se
// enviaria como "[object FormData]". Se usan los de Node para que msw reciba el multipart real.
const FormDataNode = (await new Response(new URLSearchParams('x=1')).formData()).constructor
Object.assign(globalThis, { FormData: FormDataNode, File: FileNode, Blob: BlobNode })

if (typeof window !== 'undefined') {
  const { cleanup } = await import('@testing-library/react')
  afterEach(() => {
    cleanup()
    sessionStorage.clear()
  })
}
