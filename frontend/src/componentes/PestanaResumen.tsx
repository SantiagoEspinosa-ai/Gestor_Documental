import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router'
import type { ResultadoExpediente, Rol, TipoDocumental } from '../tipos/contrato'
import { cuentaEnElFolio } from '../utilidades/expediente'
import { rutaPestana } from '../utilidades/navegacion'
import { semaforoDocumento, tareasDelRevisor } from '../utilidades/semaforo'
import { Antecedentes } from './Antecedentes'
import { TextoRecomendacion } from './Insignias'
import { ResumenExpediente } from './ResumenExpediente'
import { SoloRol } from './SoloRol'

const ROLES_ANTECEDENTES: readonly Rol[] = ['revisor', 'admin'] // GET /folios/{folio}/antecedentes

/** Pestana Resumen: tres cifras, "Lo que tienes que hacer", el resumen en Markdown y los antecedentes */
export function PestanaResumen({ expediente, fichas }: { expediente: ResultadoExpediente; fichas: readonly TipoDocumental[] }) {
  const documentos = expediente.documentos.filter(cuentaEnElFolio)
  const colores = documentos.map((d) => semaforoDocumento(d, fichas).color)
  const cuenta = (c: string) => colores.filter((x) => x === c).length
  const coinciden = expediente.comparaciones.filter((c) => c.coincide).length
  const tareas = tareasDelRevisor(expediente, fichas)
  const cifra = 'rounded-lg border border-q-slate-100 bg-white p-4'
  return (
    <div className="space-y-4">
      <section aria-label="Cifras del expediente" className="grid gap-3 sm:grid-cols-3">
        <div className={cifra}>
          <h2 className="text-xs font-medium uppercase text-slate-600">Documentos</h2>
          <p className="mt-1 text-2xl font-semibold text-q-slate">{documentos.length}</p>
          <p className="text-sm text-slate-700" data-testid="cifra-colores">
            {cuenta('verde')} en verde · {cuenta('amarillo')} en amarillo · {cuenta('rojo')} en rojo
            {cuenta('en_proceso') > 0 && <> · {cuenta('en_proceso')} analizándose</>}
          </p>
        </div>
        <div className={cifra}>
          <h2 className="text-xs font-medium uppercase text-slate-600">Comparaciones</h2>
          <p className="mt-1 text-2xl font-semibold text-q-slate">{coinciden} de {expediente.comparaciones.length}</p>
          <p className="text-sm text-slate-700">coinciden</p>
        </div>
        <div className={cifra}>
          <h2 className="text-xs font-medium uppercase text-slate-600">Recomendación de la IA</h2>
          <p className="mt-1 text-xl font-semibold"><TextoRecomendacion valor={expediente.recomendacion_global} /></p>
          <p className="text-xs text-slate-600">La IA recomienda; la decisión final es del revisor.</p>
        </div>
      </section>

      <section aria-labelledby="titulo-tareas" className="rounded-lg border border-q-slate-100 bg-white p-4">
        <h2 id="titulo-tareas" className="font-semibold">Lo que tienes que hacer</h2>
        {tareas.length === 0 ? (
          <p className="mt-1 flex items-center gap-2 text-sm text-semaforo-verde">
            <CheckCircle2 className="size-4" aria-hidden /> No queda nada pendiente.
          </p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {tareas.map((t) => (
              <li key={t.clave} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 px-3 py-1.5">
                <span>{t.texto}</span>
                <Link to={t.documento ? rutaPestana(expediente.folio, 'documentos', t.documento) : `${rutaPestana(expediente.folio, 'documentos')}#alertas-expediente`}
                  className="inline-flex items-center gap-1 text-q-slate underline hover:text-q-orange-700">
                  {t.documento ? 'Ir al documento' : 'Ir a los avisos del expediente'} <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {expediente.ruta_resumen_md
        ? <ResumenExpediente key={expediente.folio} folio={expediente.folio} fijo />
        : <p className="rounded-lg border border-q-slate-100 bg-white p-4 text-sm text-slate-600">Todavía no hay resumen en texto de este folio.</p>}
      {/* H16: antecedentes del folio, solo revisor y admin (ADR-010 C5) */}
      <SoloRol roles={ROLES_ANTECEDENTES}><Antecedentes key={expediente.folio} folio={expediente.folio} /></SoloRol>
    </div>
  )
}
