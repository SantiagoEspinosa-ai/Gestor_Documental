# motor_ia  (responsable: PERSONA_2)

Entrada: `DocumentoPreparado` (del orquestador) + ficha del tipo documental (de configuracion).
Salida: `ResultadoClasificacion`, `ResultadoExtraccion` -> ensamblados en `ResultadoDocumento` (Contrato 1).

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py`  -> Ollama local; dos instancias en `modelos.yaml` (`ollama_vision`, `ollama_texto`)
- `comercial.py` -> [A ACORDAR ADR-003]

Prompts: se cargan desde `PROMPTS_DIR/<id>_<version>.md` (p. ej. `extraccion_v1.md`); la version del
prompt va en `FechaYModelo.version_prompt`.
Reglas: el modelo devuelve JSON estricto; se valida con Pydantic; si falla, reintento con el proveedor de respaldo.
