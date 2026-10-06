# Checklist del e2e del hito (subir 3 documentos por la web con el motor real)

Para PERSONA_1 y PERSONA_2, juntos. Datos ficticios: fixtures sanos de `fixtures/generados/`
(`--hoy 2026-09-30`). Referencia: prueba local de H10 del 2026-10-05 (spec, registro de cambios).

## 1. Antes de empezar (10 min)

| Paso | Comando o accion | Esperado |
|---|---|---|
| Rama | `main` con H10 y D3 fusionados (`feat/plataforma-motor`) | `ingesta/procesamiento.py` importa `orquestador.servicio.procesar_documento` |
| `.env` | Claves de S3 sin `< >` ni comillas; `OLLAMA_BASE_URL=http://host.docker.internal:11434` (backend en Docker); `MOTOR_ANALISIS=real`; `MAX_PROCESAMIENTOS_SIMULTANEOS=1`; `PERMITIR_PROVEEDORES_NO_PRIVADOS=false` | La API arranca |
| Ollama | Arrancado con `OLLAMA_MAX_LOADED_MODELS=1`; `ollama list` muestra `gemma4:e2b` y `qwen2.5vl:3b` | Un solo modelo en memoria cada vez |
| Fixtures | `python scripts/generar_fixtures.py --hoy 2026-09-30` si no estan en `fixtures/generados/` | 42 ficheros + `INDICE.md` |
| Plataforma | **Demo** (#42): `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build`. Backend sin `--reload`; levanta `db`, `backend` y `frontend` (`:5173`), que usa la API real si `frontend/.env` no tiene `VITE_USAR_MOCKS=true`. Alternativa de desarrollo: `docker compose up -d --build db backend` y `npm run dev` en `frontend/` (`VITE_USAR_MOCKS=false`) | `GET /api/v1/procesos` sin token da 401; la web carga en `:5173` |
| RAM | Comprobar memoria libre | Al menos 4,5 GB libres antes de calentar. Si no: `docker run --rm --privileged alpine sh -c "sync; echo 3 > /proc/sys/vm/drop_caches"` (vacia la cache de la VM de Docker; no toca datos) |
| Calentar | `docker compose exec backend python -m app.modulos.motor_ia.calentar` | `gemma4:e2b: cargado en ~30 s`. Justo antes de subir: el modelo se descarga tras 10 min sin uso |

## 2. La prueba

1. Entrar en la web como revisor.
2. Crear un folio `onboarding` con una `referencia_externa` nueva (p. ej. `E2E-HITO-<hora>`).
3. Subir, en este orden y declarando el tipo:
   - `pasaporte_sano_digital.pdf` (pasaporte);
   - `credencial_elector_sano_foto.jpg` (credencial de elector);
   - `comprobante_domicilio_sano_escaneado.pdf` (comprobante de domicilio).
4. Esperar sin recargar: la UI sondea sola.

## 3. Resultado esperado

| Que mirar | Esperado (prueba local de H10) |
|---|---|
| Estado de cada documento | `completado` los tres |
| Tiempos (modelo calentado, en serie) | ~70 s el primero, ~140 s el segundo, ~190 s el tercero; **unos 3-4 min** en total |
| Tipo detectado | El declarado, con confianza 1,0 |
| Datos | Pasaporte 7/7, credencial 6/6, comprobante 4/4, con confianza 1,0 ("verificada") |
| Alertas | Ninguna en los documentos ni en el expediente |
| Comparaciones | `nombre_completo`, `fecha_nacimiento` y `domicilio` coinciden |
| Recomendacion | `aprobar` en cada documento y `aprobar` global |
| Auditoria | Un `documento_procesado` por documento, con `modelo` `gemma4:e2b` y `version_prompt` `extraccion_<tipo>@v3` |

Opcional, si sobra tiempo: folio `vencido` (`REG-vigencia_documento` bloqueante en el pasaporte, recomendacion
`revision_manual`, aprobar bloqueado) y folio `domicilio_distinto` (`CMP-001` en el expediente). Valores esperados en
`fixtures/generados/INDICE.md`.

## 4. Si algo falla

| Sintoma | Primero mirar | Causa habitual |
|---|---|---|
| La subida da 500 | `docker compose logs backend` | Credenciales o region de S3 mal escritas en `.env` (`InvalidRegionError`, `< >`) |
| Documento en `error` con `SYS-001` | ¿Responde Ollama? `curl http://localhost:11434/api/ps` desde el equipo | `OLLAMA_BASE_URL` apunta a `localhost` dentro del contenedor, u Ollama parado |
| `SYS-002` | Log del backend: "respuesta invalida tras el reintento" | Respuesta rara del modelo; repetir el documento |
| El primero tarda ~30 s mas | `curl http://localhost:11434/api/ps`: `context_length` debe ser 16384 | No se calento, o paso mas de 10 min desde el calentamiento |
| Mucho mas lento (>4 min por documento) o el equipo se queda sin memoria | `api/ps`: ¿dos modelos cargados? | Ollama sin `OLLAMA_MAX_LOADED_MODELS=1`, o el documento fue por vision (foto mala) |
| `VAL-002` o `CLS-002` en un documento sano | El documento usado y su OCR | Se subio otro fichero (p. ej. un nivel dificil): la confianza es baja cuando el texto no deja verificar el dato (ADR-007) |
| `REG-antiguedad_maxima` en el comprobante | Fecha de emision | Se uso un especimen impreso a partir del 2026-12-15, o fixtures generados con otro `--hoy` |
| La UI se queda en "procesando" | El estado en `GET /documentos/{id}` | Los documentos van de uno en uno: el tercero espera a los dos primeros |

Datos para el informe del hito: tiempos de cada documento (columna "Terminado a los"), RAM libre minima, capturas
de la UI sin datos personales reales (solo ficticios).

## 5. Resultado del e2e del hito (2026-10-05)

Sobre `main` (`1eff60d`: H10 y D3 de PERSONA_1), `docker compose` con `MOTOR_ANALISIS=real`,
`MAX_PROCESAMIENTOS_SIMULTANEOS=1`, Ollama del equipo y S3 real; modelo calentado con `calentar` (contexto 16384).
Documentos subidos por la API, datos ficticios.

| Folio | Documentos | Resultado | Tiempo total |
|---|---|---|---|
| `ONB-2026-000001` (sano) | pasaporte digital, credencial foto, comprobante escaneado | Los 3 `completado`, tipo y 17/17 campos con confianza 1,0, sin alertas, comparaciones coinciden; `aprobar` en cada documento y **global `aprobar`** | **210 s** (75, 74 y 61 s) |
| `ONB-2026-000002` (vencido) | los 3 del caso vencido | Pasaporte con `REG-vigencia_documento` (bloqueante) y `REG-vigencia_proxima`; global `revision_manual` | 197 s |
| `ONB-2026-000003` (domicilio distinto) | los 3 del caso domicilio_distinto | `CMP-001` critica en `domicilio`; global `revision_manual` | 196 s |

- El primer documento **no recargo el modelo**: su clasificacion tardo 13,3 s, como las demas (14,2 y 11,8 s).
- D3: al corregir `fecha_vencimiento` del pasaporte a una fecha pasada se recalcularon las reglas
  (`REG-vigencia_documento` y `REG-vigencia_proxima`) y la recomendacion paso a `revision_manual` (documento y
  global); al restaurarla, volvio a `aprobar`.
- RAM libre minima: 3,4-3,8 GB (6,3 GB antes de calentar, tras vaciar la cache de la VM de Docker).
