# Prompt de arranque - PERSONA_2 (Motor IA: orquestador, OCR, enrutador, proveedores, prompts)

Copia todo este bloque como primer mensaje en Claude Code dentro del repo.

---

Eres mi asistente de desarrollo en este repositorio. Lee primero `CLAUDE.md`, `README.md`, `docs/arquitectura.md`,
`docs/adr/*.md`, `backend/app/schemas/resultado.py`, `backend/app/modulos/motor_ia/interfaces.py`,
`config/modelos.yaml`, `config/tipos/*.yaml` y `prompts/*.md`. Los contratos estan congelados.

Soy PERSONA_2 y soy responsable de `orquestador`, `motor_ia` y `configuracion`. PERSONA_1 hace la
plataforma (BD, S3, API) y PERSONA_3 el frontend, fixtures y RAG. No toques sus modulos. Mi trabajo
debe poder ejecutarse desde un script CLI con un archivo local, sin BD ni S3, para no depender de nadie.

## Objetivo de la etapa 1 (dias 2-5)
`python -m app.modulos.motor_ia.cli fixtures/generados/pasaporte_sano_digital.pdf --tipo pasaporte`
imprime un `ResultadoDocumento` valido (Contrato 1) con clasificacion, datos extraidos, confianza y
evidencia por campo, usando Ollama.

## Tarea previa (etapa 1, dia 2): cuenta gratuita de OpenRouter
- Crear cuenta en openrouter.ai sin cargar saldo ni tarjeta (ADR-003: solo modelos `:free`).
- Crear la API key y ponerla solo en tu `.env` (`PROVEEDOR_COMERCIAL_API_KEY`). Compartirla por canal
  seguro con PERSONA_1 y PERSONA_3 cuando la necesiten en la integracion; nunca en el repo ni en chats.
- Elegir un modelo gratuito con entrada de imagen (filtrar en openrouter.ai/models por precio 0) y
  ponerlo en `PROVEEDOR_COMERCIAL_MODELO`. Si la cuenta exige activar "modelos gratuitos" en la
  configuracion de privacidad, activarlo: por eso solo se le envian fixtures ficticios.

## Tareas, en este orden
1. `modulos/configuracion/cargador.py`: modelos Pydantic `TipoDocumental`, `Campo`, `Regla`; carga y
   valida todos los YAML de `config/tipos` al arrancar; `obtener(nombre)`, `listar()`. Test que falla
   si un YAML esta mal formado.
2. `modulos/orquestador/modalidad.py`: `detectar(bytes, nombre) -> Modalidad`. PDF con texto
   extraible (PyMuPDF, umbral de caracteres por pagina) -> `pdf_digital`; PDF sin texto ->
   `pdf_escaneado`; jpg/png -> `imagen`. Tests con los tres casos.
3. `modulos/orquestador/ocr.py`: `OCRProvider` (Protocol) + `TesseractOCR` (pytesseract, `spa+eng`),
   con preprocesado minimo (escala de grises, autocontraste, deskew simple si es facil).
4. `modulos/orquestador/preparador.py`: `preparar(bytes, nombre, tipo_declarado) -> DocumentoPreparado`.
   pdf_digital: texto por pagina + render PNG a 150 dpi; pdf_escaneado: render a 200 dpi + OCR;
   imagen: OCR + la propia imagen. Conserva orden y numero de pagina. Multipagina intacto.
5. `modulos/motor_ia/prompts.py`: carga `prompts/<id>_<version>.md`, separa el frontmatter,
   renderiza con Jinja; devuelve `(texto, version_prompt)`.
6. `modulos/motor_ia/proveedores/ollama.py`: `OllamaProvider(ProveedorLLM)` con httpx contra
   `/api/chat`, imagenes en base64 para el modelo de vision, `format: json`. Parseo estricto del JSON
   a `ResultadoClasificacion` / `ResultadoExtraccion` con Pydantic; si el JSON es invalido, un reintento
   con instruccion de correccion.
7. `modulos/motor_ia/proveedores/base.py`: utilidades comunes (limpiar fences ```json, truncar
   texto largo por paginas, timeout, registro del modelo usado).
   `proveedores/openrouter.py`: `OpenRouterProvider(ProveedorLLM)` con httpx contra
   `{PROVEEDOR_COMERCIAL_BASE_URL}/chat/completions` (API compatible con OpenAI), imagenes en
   base64, `response_format` JSON, mismo parseo estricto que Ollama. Modelo `:free` y clave desde
   las variables de entorno del YAML (ADR-003). Es solo respaldo: si responde 429 (limite gratuito
   agotado) se registra y se sigue con el resultado de Ollama o `SYS-001`.
8. `modulos/motor_ia/enrutador.py`: implementa `Enrutador` leyendo `config/modelos.yaml`
   (principal, respaldo, por_tipo). Sin claves en codigo: lee los nombres de variables de entorno
   indicados en el YAML.
9. `modulos/motor_ia/servicio.py`: `analizar(doc: DocumentoPreparado, ficha: TipoDocumental)
   -> ResultadoDocumento parcial`: clasifica (tipos posibles = todos los YAML), compara con el
   declarado (si difiere -> alerta `CLS-001`, severidad `critica`), extrae con el esquema de campos de
   la ficha, rellena `fecha_y_modelo_utilizado` y `estado_analisis=completado`. Si el proveedor
   principal falla, usa el de respaldo; si no hay, `estado_analisis=error` con alerta `SYS-001`.
10. `modulos/motor_ia/cli.py` para ejecutar todo desde terminal con un archivo local.
11. `modulos/validacion/reglas.py` (esta parte la haces tu en etapa 2 con apoyo de PERSONA_1):
    motor de reglas deterministas segun `tipo` de regla en los YAML: `patron`,
    `fecha_posterior_a_hoy`, `fecha_posterior_a_hoy_mas_dias`, `fecha_no_anterior_a_hoy_menos_dias`,
    `anio_mayor_o_igual_actual`, `obligatorio`, `confianza_minima`. Cada regla -> cumplida o alerta
    con la severidad de la ficha. Tests unitarios para cada tipo de regla.
12. Tests: detector de modalidad, parseo de respuestas del modelo (con respuestas guardadas en
    `tests/respuestas_modelo/*.json`, nunca llamando al modelo real en tests), enrutador.

## Etapa 2 (dias 6-8)
- Exponer `procesar_documento(documento_id)` que PERSONA_1 conectara: descarga original (via su
  `almacenamiento`), prepara, analiza, valida reglas, devuelve `ResultadoDocumento` completo con
  `recomendacion` a nivel documento.
- Reintentos y manejo de errores del proveedor; registro de tiempos y tokens en auditoria.
- Ajustar prompts con los fixtures de PERSONA_3 hasta que los 4 casos salgan bien.

## Etapa 3 (dias 9-12)
- Base de conocimiento: `docs/conocimiento/*.md` -> chunks -> embeddings (Ollama `nomic-embed-text`)
  en pgvector; `rag.buscar(consulta, k)` -> fragmentos que el servicio inyecta en `contexto_rag`.
- Extra: `prompts/extraccion_v2.md` pidiendo `observaciones_visuales` (legibilidad, paginas
  recortadas, alteraciones) y convertirlas en alertas `VIS-xxx`.
- Probar el respaldo OpenRouter con los fixtures (modelos `:free` solo con datos ficticios).

## Como trabajar
- Prompts solo en `prompts/`, versionados; el codigo nunca contiene prompts largos.
- Nunca claves en codigo ni en tests. Nunca datos reales: usa `fixtures/generados`.
- Commits `feat(motor_ia): ...`. Cada modulo con README de entrada/salida.
