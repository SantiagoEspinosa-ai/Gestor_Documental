# Guion de la demo (H19) — Gestor Documental Inteligente

Demo: 2026-10-12. Duración objetivo: **15 minutos** de demo más preguntas.
Conduce PERSONA_1 (pantallas y plataforma); PERSONA_2 explica el motor y vigila Ollama.
**Solo datos ficticios**: fixtures de `fixtures/generados/` (`--hoy 2026-09-30`), nunca documentos reales.

Hilo conductor (diapositivas): **recibir → procesar → validar → consolidar → exponer** (+ antecedentes).
Idea que repetir: *la IA recomienda; la decisión final es siempre humana*.

---

## 0. Preparación (T-60 min, sin público)

| Paso | Cómo | Comprobación |
|---|---|---|
| Código | `main` con #32 (enmascaramiento), H17 ("Mostrar") y, si llega, H16 (antecedentes) | CI de `main` en verde |
| Arranque desde cero | `docker compose up -d --build` (db, backend, frontend) | `GET /api/v1/procesos` sin token → 401; la web carga |
| Variables | `.env`: `MOTOR_ANALISIS=real`, `MAX_PROCESAMIENTOS_SIMULTANEOS=1`, `PERMITIR_PROVEEDORES_NO_PRIVADOS=false`, `OLLAMA_BASE_URL` correcto | La API arranca sin errores |
| Ollama | `OLLAMA_MAX_LOADED_MODELS=1`; `ollama list` con `gemma4:e2b` y `qwen2.5vl:3b` | Un modelo cargado cada vez |
| RAM | ≥ 4,5 GB libres antes de calentar (si no, vaciar la caché de la VM de Docker: checklist de PERSONA_2) | Monitor de recursos |
| Usuarios de demo | `scripts/crear_usuario.py`: `demo.revisor`, `demo.admin`, `demo.integrador`, con contraseñas de demo que no estén en el repo ni en las diapositivas | Login de los tres |
| Folios precargados | Subir por adelantado (y dejar procesar) los 3 casos de `INDICE.md`: **sano**, **vencido**, **domicilio_distinto**, cada uno con su `referencia_externa` (p. ej. `DEMO-SANO`, `DEMO-VENCIDO`, `DEMO-DOMICILIO`) | Los 9 documentos `completado` con el resultado esperado |
| Memoria | `python scripts/reindexar_resumenes.py` (si H14 está en `main`) | Sin fallos |
| Calentar | `python -m app.modulos.motor_ia.calentar` **5 min antes** de empezar (el modelo se descarga tras 10 min sin uso) | `api/ps` con `context_length` 16384 |
| Plan B | Capturas de cada paso guardadas y la demo ensayada una vez de punta a punta | Ver sección 3 |

---

## 1. Guion (15 min)

| Min | Paso | Qué se hace | Qué se dice (idea, no literal) |
|---|---|---|---|
| 0-1 | **Problema** | Diapositiva de contexto | Expedientes con varios documentos; revisar a mano es lento y propenso a errores |
| 1-3 | **Arquitectura** | C4 N1 y N2 (`docs/arquitectura_solucion.md`) | Monolito modular; IA local (Ollama), nada sale del equipo; S3 cifrado; la IA recomienda y el humano decide |
| 3-5 | **Recibir** (en vivo) | Revisor: *Nuevo folio* `onboarding` con referencia `DEMO-VIVO`; aparece **EXP-001** por cada requerido que falta. Subir los 3 documentos sanos declarando el tipo | Validación de formato y firma del fichero, SHA-256, original cifrado en S3; el análisis va en segundo plano, de uno en uno |
| — | (mientras procesa, ~3,5 min) | Volver a subir uno de los documentos → **DUP-001** | Duplicados detectados por hash |
| 5-8 | **Procesar y validar** | Abrir el folio precargado **DEMO-SANO**: datos con **confianza verificada**, evidencia por página, reglas cumplidas, recomendación *aprobar* | La confianza la calcula el código comprobando el dato en el texto (ADR-007), no la "seguridad" del modelo |
| — | **Privacidad** | CURP y número de documento como `****1234`; pulsar **Mostrar** → se ve 60 s y se oculta solo | Enmascarado por defecto en API, webhooks y resumen; cada "mostrar" queda auditado |
| 8-11 | **Casos con alertas** | **DEMO-VENCIDO**: REG-vigencia **bloqueante**, *Aprobar* deshabilitado y el motivo. **Corregir** la fecha de vencimiento → las reglas se recalculan al momento (D3). **DEMO-DOMICILIO**: **CMP-001**, los documentos no coinciden | Reglas deterministas en YAML, comparación entre documentos; el revisor corrige y el sistema se recalcula |
| 11-13 | **Consolidar y decidir** | Volver a **DEMO-VIVO** (ya completado): EXP-001 han desaparecido, recomendación global; **Aprobar** con comentario → folio cerrado en solo lectura. **Ver resumen** | El `resumen.md` identifica por referencia, nunca por nombre, y va enmascarado |
| 13-14 | **Exponer** | Admin: **Auditoría** filtrada por `DEMO-VIVO` (subidas, análisis, `dato_revelado`, decisión). Mencionar API REST (`/docs`) y webhooks firmados HMAC con `X-Entrega-Id` | Todo queda trazado; el integrador consume por API y webhook |
| 14-15 | **Antecedentes** *(solo si H16 está en `main`)* | Nuevo folio con referencia `DEMO-SANO` → pestaña Antecedentes muestra el folio anterior | Memoria de folios por referencia, con el resumen enmascarado |
| 15 | **Cierre** | Diapositiva: calidad (CI, ~940 tests backend, ~216 frontend, e2e reales) y "Limitaciones y evolución" | Lo que haríamos después del MVP: worker con cola, proxy con TLS, outbox |

---

## 2. Reparto durante la demo

- **PERSONA_1**: conduce la web (revisor y admin) y explica plataforma, privacidad y auditoría.
- **PERSONA_2**: explica el motor (texto o visión, confianza calculada, reglas) y vigila Ollama y la RAM en una segunda pantalla.

---

## 3. Si algo falla (plan B)

| Síntoma | Qué hacer en el momento |
|---|---|
| El análisis en vivo tarda más de lo previsto | Seguir con los folios precargados y volver a DEMO-VIVO al final |
| Documento en `error` con SYS-001 (Ollama) | PERSONA_2 comprueba Ollama; mientras, enseñar el caso: *el error se ve y se audita, no se pierde* |
| El primer documento tarda ~30 s de más | No se calentó o pasaron 10 min: seguir hablando; calentar de nuevo antes del siguiente |
| La web o la API no responden | Capturas del plan B, en el orden del guion |
| Falta RAM | Cerrar aplicaciones; si no basta, enseñar los folios precargados sin análisis en vivo |

**Nunca** cambiar a `MOTOR_ANALISIS=stub` en la demo: el stub no extrae datos ni emite alertas.

---

## 4. Ensayo (antes del día 12)

1. Ensayo completo cronometrado, con los dos, en la máquina de la demo.
2. Anotar el tiempo real de cada documento y ajustar el minuto 3-5 si hace falta.
3. Preparar las capturas del plan B durante el ensayo.
4. Después del ensayo: borrar `DEMO-VIVO` no es posible (folio cerrado); usar otra referencia el día de la demo.
