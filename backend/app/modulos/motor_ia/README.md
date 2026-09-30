# motor_ia  (responsable: PERSONA_2)

Configuracion vigente (modelos, enrutador, reglas de vision y parseo, prompts):
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

Entrada: `DocumentoPreparado` (del orquestador) + ficha del tipo documental (de configuracion).
Salida: `ResultadoClasificacion`, `ResultadoExtraccion` -> ensamblados en `ResultadoDocumento` (Contrato 1).

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py`  -> Ollama local (vision + texto)
- `openrouter.py` -> OpenRouter, solo como respaldo comercial (ADR-003)

## Prompts (`prompts.py`)
- `renderizar(id, version=None, *, tipo_documental=None, **variables) -> (texto, version_prompt)`.
  Lee `PROMPTS_DIR/<id>_<version>.md` (por defecto `prompts/` de la raiz del repo), separa el
  frontmatter (`id`, `version`, `salida`) y renderiza con Jinja (`StrictUndefined`: si falta una
  variable, `ErrorPrompt`). Sin `version`, usa `VERSIONES_VIGENTES`.
- `version_prompt` (va en `FechaYModelo.version_prompt`): `extraccion_pasaporte@v2`, o `clasificacion@v2`.
- `formatear_contenido`, `formatear_tipos`, `formatear_esquema` y `formatear_contexto_rag` dan el formato
  comun de las variables. El texto del documento se inserta como valor, nunca como plantilla.
- Tests: `backend/tests/test_prompts.py`.

Reglas: el modelo devuelve JSON estricto; se valida con Pydantic; si falla, reintento con el proveedor de respaldo.
