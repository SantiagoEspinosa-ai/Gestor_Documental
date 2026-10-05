# Estado de la sesion de PERSONA_2 (2026-10-05)

Punto de partida para la proxima sesion. El detalle de cada decision esta en
[SPEC_CONFIGURACION.md](SPEC_CONFIGURACION.md) y el historial en [EXPLICACION_MOTOR.md](EXPLICACION_MOTOR.md).

## Ramas de PERSONA_2

Todas al dia con `origin/main` (`1eff60d`), con push hecho y la bateria completa en verde (903 tests, 2 saltados
y 1 xfail; H14, 914).

| Rama | Ultimo commit | Push | Contenido pendiente de llegar a `main` |
|---|---|---|---|
| `feat/motor-ia` | este commit | si | Checklist del e2e del hito y su resultado, especimen dificil del comprobante (vision, 27/27 en total), este documento. Solo `docs/motor_ia/` |
| `chore/fijar-pymupdf-pillow` | `8080f6f` | si | H13: `pymupdf==1.28.2` y `pillow==12.3.0` en `backend/requirements.txt` (compartido) |
| `feat/rag-memoria` | `c170791` | si | H14: `rag.servicio.indexar_resumen` y `fragmento_resumen`, modelo `MemoriaFolio` en `rag/modelos.py`, sin embeddings (spec, seccion 16). Sin PR todavia |

## PR abiertos y que esperan

| PR | Rama | Espera |
|---|---|---|
| H13 | `chore/fijar-pymupdf-pillow` | Revision de PERSONA_1. Tras fusionar: `docker compose build backend` |
| Documentacion del motor | `feat/motor-ia` | Revision de PERSONA_1. Si se fusiona algo antes en `main`, volver a hacer merge y pasar la bateria |

## Pendiente, en orden

1. **Repetir el e2e del hito por la web cuando se fusione el #32** (enmascaramiento de PERSONA_1). Seguir
   `CHECKLIST_E2E_HITO.md` y comprobar ademas:
   - CURP, numero de pasaporte y clave de elector enmascarados (`****` + 4 ultimos) en la UI y en la API;
   - "mostrar" para revisor y admin, y que deja `dato_revelado` en la auditoria (sin el valor);
   - `resumen.md` del folio enmascarado (datos y comparaciones).
   Antes: calentar el modelo y, si hace falta, vaciar la cache de la VM de Docker. Recomendado definir
   `OLLAMA_MAX_LOADED_MODELS=1` en el equipo (variable de usuario) y reiniciar Ollama.
2. **H14 espera a PERSONA_1**: la migracion de `memoria_folios` (y `import app.modulos.rag.modelos` en
   `alembic/env.py`) y que `expediente.servicio.avisar_reindexar` pase el texto del resumen y llame a
   `rag.servicio.indexar_resumen(folio, resumen_md)`. Despues: PR de `feat/rag-memoria`.
3. **Limpiar despues del e2e por la web** (no antes: se usan para la demo):
   - el usuario de prueba `revisor_hito` (BD local de la plataforma);
   - su contrasena temporal (fichero en el scratchpad de la sesion, nunca en el repo);
   - el `docker-compose.override.yml` local (sin commit) del checkout principal.

## No tocar sin aviso

- La plataforma levantada desde `main` en el checkout principal (`db` y `backend`, con el override local) y los
  folios del e2e del hito: `ONB-2026-000001` (sano), `ONB-2026-000002` (vencido) y `ONB-2026-000003` (domicilio
  distinto). Se ensenan a PERSONA_1.
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
