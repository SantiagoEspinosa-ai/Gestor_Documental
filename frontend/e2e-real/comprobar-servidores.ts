// Antes de los e2e reales: el backend y Vite tienen que estar ya arrancados (este proyecto no los arranca)
const API = 'http://localhost:8000/api/v1/procesos'
const WEB = 'http://localhost:5173/'

async function estado(url: string): Promise<number | null> {
  try {
    return (await fetch(url)).status
  } catch {
    return null
  }
}

export default async function comprobarServidores() {
  const api = await estado(API)
  if (api !== 401) {
    throw new Error(api === null
      ? `El backend no responde en ${API}. Arrancalo antes (uvicorn app.main:app --port 8000, desde backend/).`
      : `GET ${API} sin token deberia dar 401 y ha dado ${api}: ¿es el backend del Gestor Documental?`)
  }
  if ((await estado(WEB)) !== 200) {
    throw new Error(`Vite no responde en ${WEB}. Arranca \`npm run dev\` con VITE_USAR_MOCKS=false y VITE_API_URL=http://localhost:8000.`)
  }
}
