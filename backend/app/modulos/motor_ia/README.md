# motor_ia  (responsable: PERSONA_2)

Entrada: `DocumentoPreparado` (del orquestador) + ficha del tipo documental (de configuracion).
Salida: `ResultadoClasificacion`, `ResultadoExtraccion` -> ensamblados en `ResultadoDocumento` (Contrato 1).

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py`  -> Ollama local (vision + texto)
- `openrouter.py` -> OpenRouter, solo como respaldo comercial (ADR-003)

Prompts: se cargan desde `/prompts/<tarea>_<tipo>.md`; la version del prompt va en `FechaYModelo.version_prompt`.
Reglas: el modelo devuelve JSON estricto; se valida con Pydantic; si falla, reintento con el proveedor de respaldo.
