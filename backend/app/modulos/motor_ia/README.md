# motor_ia  (responsable: PERSONA_2)

Configuracion vigente (modelos, enrutador, reglas de vision y parseo, prompts):
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

## Servicio (`servicio.py`): lo unico que importan los demas modulos
- Entrada: `analizar(doc: DocumentoPreparado, *, folio, referencia: ReferenciaArchivoOriginal,
  tipo_confirmado=None, enrutador=None, ahora=None)`.
- Salida: `Analisis` con `resultado` (`ResultadoDocumento`, Contrato 1) y `llamadas` (`InfoLlamada`:
  modelo real, tiempos y tokens, para la auditoria).
- Clasifica (salvo con `tipo_confirmado`), extrae con la ficha `tipo_confirmado` > declarado > detectado
  (ADR-006, 2.5) y usa el respaldo si falla el principal. El sexo desde la MRZ lo completa el orquestador
  (`procesar_documento`); `analizar(..., mrz=)` solo usa la MRZ para la confianza. No importa `orquestador`.
  Alertas: `CLS-001`, `SYS-001`, `SYS-002`, `SYS-003`, `SYS-005` y `VAL-003`.
- Confianzas (ADR-007): las calcula el codigo en `confianza.py` (spec, seccion 14) y el servicio emite `CLS-002`;
  la del modelo va a `Analisis.confianzas_modelo` (auditoria). `VAL-00x`, reglas y recomendacion: `validacion`.
- Tests: `backend/tests/test_servicio_motor.py` (proveedores y enrutador falsos).
- `calentar.py`: `python -m app.modulos.motor_ia.calentar [--vision]` carga los modelos en Ollama antes de la demo
  (sin analizar nada); el primer documento deja de pagar ~21-28 s de carga. Spec, seccion 13.

Proveedores (cada uno en `proveedores/<nombre>.py`, implementan `ProveedorLLM`):
- `ollama.py` -> `OllamaProvider(base_url, modelo_texto, modelo_vision)`. Modelo de texto (sin imagenes)
  si hay texto suficiente; de vision si no o como reintento, con las paginas reducidas a 1000 px y por
  lotes de 4. `ultima_llamada` guarda el modelo real, los tiempos y los tokens; `modelo_para(doc)` da el
  modelo segun la modalidad. Errores: `ErrorProveedor` (usar el respaldo) y `ErrorRespuestaInvalida`
  (JSON invalido tras el reintento -> `SYS-002`).
- `base.py` -> parametros de llamada (constantes), parseo estricto, postprocesado (fechas, anio,
  evidencia, campos de la ficha), combinacion de lotes, `reducir_imagen`, `recortar_texto`.
- `openrouter.py` -> OpenRouter, solo como respaldo comercial (ADR-003). Pendiente.
Tests: `test_proveedores_base.py` y `test_proveedor_ollama.py` (Ollama simulado; respuestas reales en
`backend/tests/respuestas_modelo/`).

## CLI (`cli.py`, entregable de la etapa 1)
```
python -m app.modulos.motor_ia.cli fixtures/generados/pasaporte_sano_digital.pdf --tipo pasaporte
```
- Opciones: `--tipo` (declarado), `--tipo-confirmado`, `--folio` (por defecto `CLI-2026-000000`),
  `--salida <fichero.json>`.
- stdout: solo el `ResultadoDocumento` en JSON. stderr: resumen (modalidad, modelo, segundos y tokens de
  cada llamada, alertas), sin datos del documento.
- Salida: 0 completado; 1 `estado_analisis=error` (el JSON se imprime igual); 2 error de entrada o de
  configuracion (archivo, formato, tipo, `modelos.yaml`, fichas o prompts).
- Referencia del archivo: `local://<nombre>` (sin rutas personales) y SHA-256 real.
- Lee el `.env` de la raiz del repo (`python-dotenv`); el entorno real tiene prioridad. La ruta se busca
  desde la carpeta actual y, si no existe, desde la raiz del repo.
- En Windows sin Visual C++ Redistributable, ejecutarlo en el contenedor del backend (spec, seccion 12).
- Tests: `backend/tests/test_cli.py`.

## Enrutador (`enrutador.py`)
- `crear_enrutador(directorio=None, entorno=None, tipos_documentales=None) -> EnrutadorYaml`
  (implementa `Enrutador`, Contrato 3). Lee y valida `CONFIG_DIR/modelos.yaml` de forma estricta
  (claves desconocidas, proveedores y tipos documentales inexistentes, variables de cada tipo) y crea
  los proveedores con las variables de entorno que indica el YAML. Sin nombres de modelos ni claves en
  el codigo; los errores nombran la variable, nunca su valor.
- `obtener(tarea, tipo)`: `por_tipo` si existe; si no, `principal`. `respaldo(tarea, tipo)`: el
  `respaldo`, o `None` si es el mismo que el principal o no esta disponible (aviso en el log).
- **Regla de modelo** (decidida sin ADR): el enrutador devuelve el proveedor y el proveedor elige su
  modelo: el de texto, sin imagenes, si todas las paginas tienen al menos 30 caracteres de texto (capa del
  PDF u OCR), y el de vision si alguna no llega (`OllamaProvider.modelo_para`, `usa_texto`). Con **OCR
  pobre** el **servicio** pasa a vision (riesgo 2 del plan; detalle en la seccion 3 de la spec): si la
  clasificacion con texto da `desconocido`, reclasifica con vision (`clasificar_con_vision`), decide
  `CLS-001` con esa clasificacion y extrae con vision; si la extraccion con texto deja vacia la mitad o mas
  de los obligatorios o algun campo con formato invalido, reintenta con `extraer_con_vision`, salvo si salta
  `CLS-001` con un tipo concreto. Todas las llamadas quedan en `Analisis.llamadas` con `entrada` y `motivo`.
  `Enrutador.obtener` no cambia, asi que el Contrato 3 tampoco.
- **Barrera de privacidad** (ADR-003): un proveedor con `privado: false` solo se usa con
  `PERMITIR_PROVEEDORES_NO_PRIVADOS=true` (desarrollo con fixtures ficticios). Si es un principal y la
  barrera esta cerrada, error al arrancar; si es un respaldo, `None`.
- Principal no disponible (falta una variable, valor de ejemplo `TU_CLAVE_AQUI`/`TU_MODELO_AQUI` o tipo
  sin implementar): `ErrorEnrutador` al arrancar. Respaldo no disponible: `None` y aviso.
- `Tarea.validacion` se acepta en el YAML, pero no se usa. Los perfiles de `procesos.yaml`
  (`modelos: default`) no se implementan: siempre se usa `modelos.yaml` tal cual.
- Tests: `backend/tests/test_enrutador.py` (entorno inyectado, sin red ni claves).

## Prompts (`prompts.py`)
- `renderizar(id, version=None, *, tipo_documental=None, **variables) -> (texto, version_prompt)`.
  Lee `PROMPTS_DIR/<id>_<version>.md` (por defecto `prompts/` de la raiz del repo), separa el
  frontmatter (`id`, `version`, `salida`) y renderiza con Jinja (`StrictUndefined`: si falta una
  variable, `ErrorPrompt`). Sin `version`, usa `VERSIONES_VIGENTES`.
- `version_prompt` (va en `FechaYModelo.version_prompt`): `extraccion_pasaporte@v3`, o `clasificacion@v2`.
- `formatear_contenido`, `formatear_tipos`, `formatear_esquema`, `formatear_campos` y `formatear_contexto_rag`
  dan el formato comun de las variables. `formatear_campos` (la usa `extraccion_v3`) lista los campos sin
  "obligatorio"/"opcional": con "opcional" el modelo de vision dejaba campos legibles vacios. El texto del
  documento se inserta como valor, nunca como plantilla.
- Tests: `backend/tests/test_prompts.py`.

Reglas: el modelo devuelve JSON estricto y se valida con Pydantic. Si no es valido, un reintento con
`prompts/correccion_json_v1.md` en el mismo modelo; si vuelve a fallar, `ErrorRespuestaInvalida`.
Si el proveedor falla, el servicio decide si usa el de respaldo (tarea 9).
