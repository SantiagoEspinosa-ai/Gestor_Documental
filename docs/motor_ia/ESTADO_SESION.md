# Estado de la sesion de PERSONA_2 (2026-10-06)

Punto de partida para la proxima sesion. El detalle de cada decision esta en
[SPEC_CONFIGURACION.md](SPEC_CONFIGURACION.md) y el historial en [EXPLICACION_MOTOR.md](EXPLICACION_MOTOR.md).

## Fusionado en `main`

| PR | Rama | Contenido |
|---|---|---|
| #35 | `chore/fijar-pymupdf-pillow` | H13: `pymupdf==1.28.2` y `pillow==12.3.0` en `backend/requirements.txt` |
| #36 | `feat/motor-ia` | Checklist del e2e del hito y su resultado, especimen dificil del comprobante (vision, 27/27 en total), este documento |
| #32 | `feat/plataforma` (PERSONA_1) | Enmascaramiento de los campos sensibles (ADR-010) |

## Ramas de PERSONA_2

| Rama | Ultimo commit | Push | Contenido pendiente de llegar a `main` |
|---|---|---|---|
| `feat/motor-ia` | este commit | si | Solo este documento y su entrada en la spec |
| `feat/rag-memoria` | `959922b` | si | H14: `rag.servicio.indexar_resumen` y `fragmento_resumen`, modelo `MemoriaFolio` en `rag/modelos.py`, sin embeddings (spec, seccion 16). Merges de `origin/main` con #32, #34 y #35 (`3c9aea3`) y con #33 y #36 (`959922b`); bateria 958 pasan, 2 saltados y 1 xfail |

## PR abiertos y que esperan

| PR | Rama | Espera |
|---|---|---|
| #37 (H14) | `feat/rag-memoria` | Aprobacion de PERSONA_1. Nadie lo llama todavia: fusionarlo no cambia la plataforma. Si se fusiona algo antes en `main`, volver a hacer merge y pasar la bateria |

## Pendiente, en orden

1. **Siguiente paso: e2e por la web con la mascara**, con PERSONA_1 (los documentos se suben juntos). Seguir
   `CHECKLIST_E2E_HITO.md` y comprobar ademas:
   - CURP, numero de pasaporte y clave de elector enmascarados (`****` + 4 ultimos) en la UI y en la API;
   - "mostrar" para revisor y admin, y que deja `dato_revelado` en la auditoria (sin el valor);
   - `resumen.md` del folio enmascarado (datos y comparaciones).
   Plataforma preparada el 2026-10-06: `main` actualizado, imagen del backend reconstruida (H13), sin el
   `docker-compose.override.yml` local (en `.env` del equipo: `OLLAMA_BASE_URL` a `host.docker.internal` y
   `MOTOR_ANALISIS=real`), frontend con `VITE_USAR_MOCKS=false`, y `revisor_hito` y su contrasena temporal
   borrados. El usuario revisor nuevo se crea con `scripts/crear_usuario.py`. Antes de subir: calentar el modelo
   y, si hace falta, vaciar la cache de la VM de Docker. Recomendado `OLLAMA_MAX_LOADED_MODELS=1` en el equipo
   (variable de usuario) y reiniciar Ollama.
2. **H14 tras aprobar el #37, lo hace PERSONA_1**: migracion `0005` de `memoria_folios`, `import
   app.modulos.rag.modelos` en `alembic/env.py`, que `expediente.servicio.avisar_reindexar` pase el texto del
   resumen y llame a `rag.servicio.indexar_resumen(folio, resumen_md)`, y un script para reindexar los folios
   cerrados.
3. **Limpiar despues del e2e por la web**: el usuario revisor creado para la prueba (BD local), si no se queda
   para la demo.

## No tocar sin aviso

- La plataforma levantada desde `main` en el checkout principal (`db`, `backend` y el frontend con `npm run dev`)
  y los folios del e2e del hito: `ONB-2026-000001` (sano), `ONB-2026-000002` (vencido) y `ONB-2026-000003`
  (domicilio distinto). Se ensenan a PERSONA_1.
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
