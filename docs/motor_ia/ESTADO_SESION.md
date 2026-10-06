# Estado de la sesion de PERSONA_2 (2026-10-06)

Punto de partida para la proxima sesion. El detalle de cada decision esta en
[SPEC_CONFIGURACION.md](SPEC_CONFIGURACION.md) y el historial en [EXPLICACION_MOTOR.md](EXPLICACION_MOTOR.md).

## Fusionado en `main`

| PR | Rama | Contenido |
|---|---|---|
| #32 | `feat/plataforma` (PERSONA_1) | Enmascaramiento de los campos sensibles (ADR-010) |
| #35 | `chore/fijar-pymupdf-pillow` | H13: `pymupdf==1.28.2` y `pillow==12.3.0` en `backend/requirements.txt` |
| #36 | `feat/motor-ia` | Checklist del e2e del hito y su resultado, especimen dificil del comprobante (vision, 27/27 en total), este documento |
| #37 | `feat/rag-memoria` | H14, lado de PERSONA_2: `rag.servicio.indexar_resumen` y `fragmento_resumen`, modelo `MemoriaFolio`, sin embeddings (spec, seccion 16) |
| #39 | `feat/plataforma-memoria` (PERSONA_1) | H14, lado de PERSONA_1: migracion `0005`, `avisar_reindexar` -> `indexar_resumen` y `scripts/reindexar_resumenes.py`. **H14 completo** |
| #41 | `feat/plataforma-antecedentes` (PERSONA_1) | H16: antecedentes (ADR-010 C1-C4) con `fragmento_resumen` |
| #38 | `feat/plataforma-mostrar` (PERSONA_1) | H17: boton "Mostrar" en los campos sensibles para revisor y admin |
| #40 | `chore/ci-ubuntu-24` (PERSONA_1) | CI fijado a `ubuntu-24.04` |
| #43 | `fix/filtro-logs-acceso` (PERSONA_1) | `core/logs.py` conserva los `args`: vuelven las lineas de acceso de uvicorn |
| #42 | `chore/compose-demo` (PERSONA_1) | `docker-compose.demo.yml`: arranque de demo con el backend sin `--reload` |

## Ramas de PERSONA_2

| Rama | Ultimo commit | Push | Contenido pendiente de llegar a `main` |
|---|---|---|---|
| `feat/motor-ia` | este commit | si | Merges de `origin/main` (#37-#41 en `6325c9d`; #42 y #43), este documento, la spec al dia (H14 hecho), el docstring de `indexar_resumen` (commit sobre la sesion recibida) y el arranque de demo en `CHECKLIST_E2E_HITO.md`. Sin PR todavia |

`feat/rag-memoria` ya esta en `main` (#37).

## Pendiente, en orden

1. **Siguiente paso: e2e por la web con la mascara, "Mostrar" y antecedentes**, con PERSONA_1 (los documentos se
   suben juntos). Seguir `CHECKLIST_E2E_HITO.md` y comprobar ademas:
   - CURP, numero de pasaporte y clave de elector enmascarados (`****` + 4 ultimos) en la UI y en la API;
   - "Mostrar" (H17) para revisor y admin, y que deja `dato_revelado` en la auditoria (sin el valor);
   - `resumen.md` del folio enmascarado (datos y comparaciones);
   - antecedentes (H16): con dos folios del mismo proceso y la misma `referencia_externa`, cerrar el primero y ver
     su fragmento en el segundo, sin valores de los datos; sin referencia o sin permiso, `permitido: false`.
   Plataforma preparada el 2026-10-06 (sin el `docker-compose.override.yml` local; en `.env` del equipo,
   `OLLAMA_BASE_URL` a `host.docker.internal` y `MOTOR_ANALISIS=real`; `revisor_hito` y su contrasena temporal
   borrados). **Despues se paro la plataforma** (Docker Desktop se cerro; ya esta arrancado, con `db` y `backend`
   parados). Antes del e2e: `git pull` en `main`, arranque de demo
   `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build` (#42; aplica la migracion `0005` y
   levanta tambien el frontend en `:5173`), ejecutar una vez `scripts/reindexar_resumenes.py` para los folios
   existentes y crear el usuario revisor con `scripts/crear_usuario.py`. Antes de subir: calentar el modelo y, si hace falta, vaciar la cache de la VM de
   Docker. Recomendado `OLLAMA_MAX_LOADED_MODELS=1` en el equipo (variable de usuario) y reiniciar Ollama.
2. **Limpiar despues del e2e por la web**: el usuario revisor creado para la prueba (BD local), si no se queda
   para la demo.

## No tocar sin aviso

- La plataforma del checkout principal (`db`, `backend` y el frontend con `npm run dev`) y los folios del e2e del
  hito: `ONB-2026-000001` (sano), `ONB-2026-000002` (vencido) y `ONB-2026-000003` (domicilio distinto). Se
  ensenan a PERSONA_1.
- Los ficheros de `ONB-2026-000003` de la prueba local de H10 en el bucket S3 de desarrollo: los gestiona
  PERSONA_1.

## Reglas de trabajo

- **Bateria completa antes de cada push**, en cualquier rama: contenedor del backend con `scripts/`, `fixtures/`,
  `frontend/` y `docs/` montados (spec, seccion 8), y vitest y `tsc` si se toca el frontend. Encadenar tests,
  commit y push para que un fallo pare el push.
- **Nunca `--force`**: push normal.
- **No tocar ficheros de PERSONA_1 sin su permiso y sin avisar**. Los compartidos (`validacion/servicio.py`,
  `config/tipos/*.yaml`, `requirements.txt`, contratos, mocks) van en PR pequenos y con aviso; en
  `validacion/servicio.py`, solo el bloque de PERSONA_2 al final, tras `git fetch` y merge de `origin/main`.
- **Nunca mostrar claves ni secretos** (`.env`, contrasenas temporales): comprobar solo si estan vacios, son de
  ejemplo o tienen caracteres raros, sin ensenar el valor. Solo datos ficticios.
- **Spec y `EXPLICACION_MOTOR.md` en el mismo commit**: cada decision de configuracion va a la spec con su entrada
  en el registro, y cada cambio de regla, de modelo o resultado de prueba anade una entrada al "Historial de
  mejoras" (problema -> cambio -> mejora medida).
- **Flujo**: plan antes de codigo y esperar el OK; comprobar la rama antes de escribir y de cada commit; commit y
  push solo cuando se piden; avisar antes de lanzar modelos si la RAM no alcanza (vigilante de 1 GB, un modelo
  cada vez).
- **Contratos congelados** (`resultado.py`, `endpoints.md`, `interfaces.py`): solo cambian con ADR o en el PR de
  contratos acordado.
