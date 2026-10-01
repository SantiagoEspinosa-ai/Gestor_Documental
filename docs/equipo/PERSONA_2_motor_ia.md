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

## Cambios de contrato aceptados el 2026-09-30 (ADR-006)
- 1.5: `configuracion.servicio.listar()` devuelve las fichas validadas; se serializan con
  `model_dump()` para `GET /tipos-documentales` (forma en `endpoints.md`).
- 2.5: `procesar_documento(documento_id, tipo_confirmado=None)`. Regla de extraccion: ficha del tipo
  declarado; si no hay `tipo_declarado`, la del detectado; con `tipo_confirmado`, esa y sin
  clasificar. Si el detectado difiere del declarado -> `CLS-001` y decide el revisor.
- Alertas: el motor no rellena `Alerta.id` (lo asigna la plataforma). `VAL-001` y `VAL-002` van una
  por campo, con `campo` relleno. Codigos en `docs/contratos/codigos_alertas.md`.
- Reprocesar documentos en `error` queda fuera del MVP.
- Etapa 3: si se propone `sensible: true` en los YAML, se te avisa antes para aceptarlo en el cargador.

## Etapa 3 (dias 9-12)
- Base de conocimiento: `docs/conocimiento/*.md` -> chunks -> embeddings (Ollama `nomic-embed-text`)
  en pgvector; `rag.buscar(consulta, k)` -> fragmentos que el servicio inyecta en `contexto_rag`.
  Reparto de `modulos/rag` (ADR-006, "Coordinacion"): `conocimiento.py` tuyo, `memoria.py` y
  `embeddings.py` de PERSONA_3 (lo reutilizas), `servicio.py` y `README.md` comunes.
- Extra: `prompts/extraccion_v2.md` pidiendo `observaciones_visuales` (legibilidad, paginas
  recortadas, alteraciones) y convertirlas en alertas `VIS-xxx`.
- Probar el respaldo OpenRouter con los fixtures (modelos `:free` solo con datos ficticios).

## Como trabajar
- Trabaja SOLO en la rama `feat/motor-ia` (ver "Ramas y flujo de trabajo" en `CLAUDE.md`).
- Prompts solo en `prompts/`, versionados; el codigo nunca contiene prompts largos.
- Nunca claves en codigo ni en tests. Nunca datos reales: usa `fixtures/generados`.
- Commits `feat(motor_ia): ...`. Cada modulo con README de entrada/salida.

## Tareas heredadas de PERSONA_3 (traspaso del 2026-10-01; PROPUESTA hasta aprobar su PR)
PERSONA_3 pasa a otro proyecto. Heredas los fixtures y toda la carpeta `modulos/rag`: lo que el
apartado "Etapa 3" de arriba da a PERSONA_3 (`memoria.py` y `embeddings.py`) pasa a ser tuyo. Se hace
en `feat/motor-ia`. Ids, dependencias y recortes: `docs/equipo/PERSONA_3_estado.md`.

| Id | Tarea | Etapa |
|---|---|---|
| H9 | ADR para el valor reservado `desconocido` en `tipo_documental_detectado` (Contrato 1 y `endpoints.md`). EN CURSO: ADR-009 propuesto en `docs/adr-009-desconocido`; falta abrir el PR. Revisa PERSONA_1, que adapta la UI (H4) | 2 (dias 4-5) |
| H10 | Decidir con PERSONA_1 si `procesar_documento` sustituye a `motor_stub.py` antes de calcular la confianza (ADR-007). DECIDIDO en tu spec (`96f7425`): no lo sustituye hasta entonces; falta que PERSONA_1 lo confirme | 2 |
| H11 | Formato estable de `INDICE.md`. EN PARTE: `test_fixtures_ocr.py` ya filtra por casos y nivel (`7c84720`); falta documentar el formato en `fixtures/README.md` (o generar `INDICE.json` al lado) | 2 |
| H12 | Tiempo maximo esperado por documento y por pagina escaneada en tu spec. HECHO (seccion 13, llega con el PR #11) | 2 |
| H13 | Mantener `scripts/generar_fixtures.py` (su evaluador de reglas debe conocer los tipos nuevos, como `coherencia_curp_fecha` y `fechas_ordenadas`), `scripts/verificar_ocr_fixtures.py` (mismo preprocesado que `orquestador/ocr.py`) y `scripts/procesar_especimenes.py`; quitar del docstring del generador el pendiente de `ejemplos_referencia`; PR pequeno para fijar `pymupdf==1.28.2` y `pillow==12.3.0` | 2-3 |
| H14 | `rag/embeddings.py` (Ollama `nomic-embed-text`, compartido con `conocimiento.py`), `rag/memoria.py` (trocear e indexar `resumen.md`, tabla `memoria_folios` con su migracion), `buscar_antecedentes(referencia_persona, proceso)` con `permitir_antecedentes` y caducidad, `rag/servicio.py` y `rag/README.md` | 3 (dias 9-11) |
| H15 | `sensible: true` en los YAML y en el cargador, segun el ADR de la etapa 3 (H7, de PERSONA_1) | 3 |
| H18 | Repetir o recortar las 4 fotos de especimenes descartadas, solo si se rechaza R5 | 3, solo si se rechaza R5 |

Ficheros de partida: `fixtures/README.md`, `fixtures/especimenes/README.md`, los tres scripts de
fixtures, `backend/tests/test_generar_fixtures.py`, `test_especimenes.py`,
`test_verificar_ocr_fixtures.py`, `test_versiones_fixtures.py` y `sha256_fixtures_existentes.txt`,
ADR-006 ("Bloque 4" y "Coordinacion") y el anexo de `PERSONA_3_estado.md`.

Acuerdos que hay que respetar:
- Solo personas ficticias de `PERSONAS_FICTICIAS`, sin escudos, logotipos ni organismos reales. Los
  especimenes, sin metadatos y solo con el documento en el encuadre.
- `fixtures/generados/` e `INDICE.md` no se suben. Con el mismo `--hoy` los ficheros salen identicos
  byte a byte; cambiar el nivel `normal` rompe `DUP-001` frente a los mocks y obliga a regenerar
  `sha256_fixtures_existentes.txt`, `frontend/public/mock-originales` y los mocks (avisar a
  PERSONA_1).
- Un caso o un tipo nuevo en el generador cambia `INDICE.md`: avisar antes.
- `rag/servicio.py` es la unica API del modulo; el router de `/antecedentes` es de PERSONA_1. La
  migracion de `memoria_folios` se encadena en su historia de Alembic: avisa antes de crearla.
- La memoria nunca guarda la CURP en claro; la forma de `referencia_persona` la fija el ADR de la
  etapa 3.
