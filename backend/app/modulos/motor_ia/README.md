# motor_ia  (responsable: PERSONA_2)

Configuracion vigente (modelos, enrutador, reglas de vision y parseo, prompts):
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

Entrada: `DocumentoPreparado` (del orquestador) + ficha del tipo documental (de configuracion).
Salida: `ResultadoClasificacion`, `ResultadoExtraccion` -> ensamblados en `ResultadoDocumento` (Contrato 1).

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py`  -> Ollama local (vision + texto)
- `openrouter.py` -> OpenRouter, solo como respaldo comercial (ADR-003)

Prompts: se cargan desde `PROMPTS_DIR/<id>_<version>.md` (p. ej. `extraccion_v1.md`); la version del prompt va en `FechaYModelo.version_prompt`.
Reglas: el modelo devuelve JSON estricto; se valida con Pydantic; si falla, reintento con el proveedor de respaldo.
