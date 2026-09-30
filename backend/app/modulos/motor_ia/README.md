# motor_ia  (responsable: PERSONA_2)

Configuracion vigente (modelos, enrutador, reglas de vision y parseo, prompts):
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

Entrada: `DocumentoPreparado` (del orquestador) + ficha del tipo documental (de configuracion).
Salida: `ResultadoClasificacion`, `ResultadoExtraccion` -> ensamblados en `ResultadoDocumento` (Contrato 1).

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py` -> `OllamaProvider(base_url, modelo_texto, modelo_vision)`. Modelo de texto si
  `pdf_digital` (sin imagenes); de vision en el resto, con las paginas reducidas a 1000 px y por lotes
  de 4. `ultima_llamada` guarda el modelo real, los tiempos y los tokens; `modelo_para(doc)` da el
  modelo segun la modalidad. Errores: `ErrorProveedor` (usar el respaldo) y `ErrorRespuestaInvalida`
  (JSON invalido tras el reintento -> `SYS-002`).
- `base.py` -> parametros de llamada (constantes), parseo estricto, postprocesado (fechas, anio,
  evidencia, campos de la ficha), combinacion de lotes, `reducir_imagen`, `recortar_texto`.
- `openrouter.py` -> OpenRouter, solo como respaldo comercial (ADR-003). Pendiente.
Tests: `test_proveedores_base.py` y `test_proveedor_ollama.py` (Ollama simulado; respuestas reales en
`backend/tests/respuestas_modelo/`).

## Prompts (`prompts.py`)
- `renderizar(id, version=None, *, tipo_documental=None, **variables) -> (texto, version_prompt)`.
  Lee `PROMPTS_DIR/<id>_<version>.md` (por defecto `prompts/` de la raiz del repo), separa el
  frontmatter (`id`, `version`, `salida`) y renderiza con Jinja (`StrictUndefined`: si falta una
  variable, `ErrorPrompt`). Sin `version`, usa `VERSIONES_VIGENTES`.
- `version_prompt` (va en `FechaYModelo.version_prompt`): `extraccion_pasaporte@v2`, o `clasificacion@v2`.
- `formatear_contenido`, `formatear_tipos`, `formatear_esquema` y `formatear_contexto_rag` dan el formato
  comun de las variables. El texto del documento se inserta como valor, nunca como plantilla.
- Tests: `backend/tests/test_prompts.py`.

Reglas: el modelo devuelve JSON estricto y se valida con Pydantic. Si no es valido, un reintento con
`prompts/correccion_json_v1.md` en el mismo modelo; si vuelve a fallar, `ErrorRespuestaInvalida`.
Si el proveedor falla, el servicio decide si usa el de respaldo (tarea 9).
