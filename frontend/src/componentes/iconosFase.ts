// Icono de cada fase del analisis (ADR-014), comun al flujo, a la barra y a la insignia del semaforo
import { Clock, Eye, FileCog, FileSearch, ListChecks, ScanText } from 'lucide-react'
import type { FaseAnalisis } from '../tipos/contrato'

export const ICONO_FASE: Record<FaseAnalisis, typeof Clock> = {
  en_cola: Clock, preparando: FileCog, ocr: ScanText, clasificando: FileSearch, vision: Eye, extrayendo: ListChecks,
}
