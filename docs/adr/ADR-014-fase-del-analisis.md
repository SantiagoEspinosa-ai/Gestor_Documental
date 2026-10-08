# ADR-014: Fase del analisis de un documento

Fecha: 2026-10-08. Estado: ACEPTADO (2026-10-08, PERSONA_1 y PERSONA_2, PR de feat/fase-analisis).
Propone: PERSONA_2; PERSONA_1 dio permiso para tocar sus ficheros en el PR.
Afecta al Contrato 1 (`backend/app/schemas/resultado.py`: enum `FaseAnalisis` y campo opcional
`fase_analisis` en `ResultadoDocumento`) y a `docs/contratos/endpoints.md` ("Reglas", webhook y estados).
Sin migracion ni cambios en la BD.

## Contexto
En los ensayos de la demo, un documento puede estar varios minutos en `procesando` (cola de un analisis cada
vez, cambio de modelo, vision en CPU) y la web solo dice "se esta analizando". El revisor no sabe si espera
turno, si se lee el texto o si el modelo de vision esta leyendo una foto dificil.

## Decision
1. `ResultadoDocumento.fase_analisis: FaseAnalisis | None = None`, con `en_cola`, `preparando`, `ocr`,
   `clasificando`, `vision` y `extrayendo`. Solo tiene valor con `estado_analisis` `pendiente` o
   `procesando`; en `completado` y `error` siempre es `null`.
2. El motor avisa de la fase con un callback opcional, `al_avanzar`, en `orquestador.procesar_documento` y en
   `motor_ia.analizar`: `preparando` al empezar, `ocr` antes del OCR o de leer la capa de texto, `clasificando`
   antes de clasificar, `vision` al usar el modelo de vision (directa sin texto suficiente, reclasificacion,
   extraccion por OCR pobre y reintento) y `extrayendo` antes de extraer con texto. El aviso nunca lanza: si
   el callback falla se ignora (log de depuracion sin datos del documento) y el resultado no cambia.
3. La plataforma guarda la fase **solo en memoria**, en un registro de `ingesta/procesamiento.py` con
   `threading.Lock`: `en_cola` justo antes del semaforo, despues lo que avise el motor, y se borra siempre
   al terminar (completado, error o excepcion). Vale para un proceso uvicorn, como el semaforo
   `MAX_PROCESAMIENTOS_SIMULTANEOS`; con varios workers haria falta otro mecanismo.
4. `construir_resultado` (`GET /documentos/{id}` y el expediente) la rellena desde el registro. Un
   documento `pendiente` o `procesando` sin entrada (p. ej. tras reiniciar la API) da `null`.
5. **No** va en la auditoria ni en la BD. En los webhooks sale siempre `null`: solo se envian en
   `completado` o `error`.
6. La web muestra la frase de la fase y el tiempo que lleva en ella, contado en el cliente.

## Consecuencias
- Campo opcional y `null` por defecto: los clientes que no lo conocen no cambian.
- Se pierde al reiniciar la API: un analisis reanudado vuelve a avisar sus fases desde `en_cola`.
- El sondeo de la web no cuenta un cambio de fase como cambio (su firma es identificador y estado); si se
  quiere que lo cuente, es otro cambio, fuera de este ADR.
