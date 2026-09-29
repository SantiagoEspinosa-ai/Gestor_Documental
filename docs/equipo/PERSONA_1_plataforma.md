# Prompt de arranque - PERSONA_1 (Plataforma: ingesta, folios, S3, auth, API, expediente, webhooks)

Copia todo este bloque como primer mensaje en Claude Code dentro del repo.

---

Eres mi asistente de desarrollo en este repositorio. Lee primero `CLAUDE.md`, `README.md`,
`docs/adr/*.md`, `docs/contratos/endpoints.md`, `backend/app/schemas/resultado.py` y
`backend/app/modulos/motor_ia/interfaces.py`. Son contratos congelados: no los modifiques.

Soy PERSONA_1 y soy responsable de los modulos `ingesta`, `api`, `expediente` y `core` (auth, BD,
S3, auditoria, webhooks). Otras dos personas trabajan en paralelo en `orquestador`/`motor_ia`
(PERSONA_2) y en `frontend`/`rag`/fixtures (PERSONA_3). No toques sus modulos: donde necesite
algo de ellos, usa la interfaz de `interfaces.py` y crea un stub que devuelva datos ficticios.

## Objetivo de la etapa 1 (dias 2-5)
Que se pueda crear un folio, subir un archivo por API con JWT, y que quede en S3 y en BD en estado
`pendiente` con su hash, ID unico y deteccion de duplicados. Todo con tests.

## Tareas, en este orden
1. `app/core/config.py`: settings con pydantic-settings leyendo `.env` (ver `.env.example`).
   Nunca valores por defecto con claves reales.
2. `app/core/db.py`: engine SQLAlchemy 2 + sesion; Alembic inicializado en `backend/alembic/`.
3. Modelos en `app/core/modelos.py`: usuarios(id, usuario, hash_contrasena, rol),
   procesos(nombre, prefijo_folio, webhook_url, permitir_antecedentes, caducidad_antecedentes_dias,
   conservacion_originales_dias),
   folios(folio PK, proceso, anio, secuencia, estado_general, referencia_externa, creado_en),
   documentos(id UUID, folio FK, nombre_archivo, ruta_s3, hash_sha256, tipo_declarado,
   estado_analisis, creado_en), resultados(documento_id FK, json JSONB = ResultadoDocumento,
   version, creado_en), alertas(id, documento_id, codigo, severidad, mensaje, confianza,
   resuelta_por_revisor, aplica, comentario), correcciones(id, documento_id, campo, valor_anterior,
   valor_nuevo, usuario, creado_en), auditoria(id, usuario, accion, folio, documento_id, detalle JSONB,
   modelo, version_prompt, creado_en). Indice unico (proceso, anio, secuencia). Indice en hash_sha256.
4. Cargar `config/procesos.yaml` a la tabla procesos al arrancar (upsert).
5. `app/core/seguridad.py`: hash bcrypt, JWT (python-jose), dependencia `usuario_actual` y
   `requiere_rol(*roles)`. Script `scripts/crear_usuario.py` para crear admin/revisor/integrador
   de desarrollo (contrasenas ficticias, nunca en el repo).
6. Router `api/auth.py`: `POST /api/v1/auth/login`.
7. Router `api/folios.py`: `POST /folios` genera `{PREFIJO}-{AAAA}-{NNNNNN}` con secuencia por
   (proceso, anio) de forma atomica (SELECT ... FOR UPDATE o secuencia PostgreSQL por proceso).
   `GET /folios/{folio}` devuelve `ResultadoExpediente` (por ahora sin comparaciones).
8. `app/core/almacenamiento.py`: cliente boto3 con `S3_ENDPOINT_URL` opcional (en local, el servicio
   `minio` de docker-compose); `subir(bytes, clave)`, `url_prefirmada(clave)`, `descargar(clave)`.
   Cifrado en reposo con `ServerSideEncryption=S3_CIFRADO` en cada `put_object` (diapositiva 12).
   Crear el bucket al arrancar si no existe y activar el versionado (diapositiva 10).
   Claves (diapositiva 10: los derivados se guardan aparte y nunca sustituyen al original):
   - original:  `{proceso}/{anio}/{secuencia}/originales/{uuid}.{ext}`
   - derivados: `{proceso}/{anio}/{secuencia}/derivados/{uuid}/pagina_{n}.png`, `texto.txt`, `resultado.json`
   - resumen:   `{proceso}/{anio}/{secuencia}/resumen.md`
   El original nunca se modifica ni se sobrescribe.
9. `modulos/ingesta/servicio.py`: `ingestar(folio, archivo, tipo_declarado, usuario)`: valida
   extension contra `formatos_permitidos` del tipo (lee YAML de `config/tipos`), calcula SHA-256,
   detecta duplicado en el mismo folio (misma hash -> alerta `DUP-001` severidad `critica`, no
   bloquea la subida), sube a S3, inserta documento en `pendiente`, registra auditoria y lanza
   `BackgroundTask(procesar_documento, id)`. `procesar_documento` por ahora es un stub que cambia
   estado a `procesando` y luego `completado` con un `ResultadoDocumento` ficticio valido; PERSONA_2
   lo sustituira por el real en la etapa 2.
10. Router `api/documentos.py`: `POST /folios/{folio}/documentos` (202), `GET /documentos/{id}`,
    `GET /documentos/{id}/original`.
11. Tests con pytest: generacion de folios (secuencia y concurrencia basica), hash y duplicados,
    auth por rol, ingesta e2e con S3 mockeado (moto o stub). Usa solo datos ficticios.
12. README de cada modulo tuyo con contrato de entrada/salida.

## Etapa 2 (dias 6-8), cuando PERSONA_2 entregue `procesar_documento`
- Conectar el pipeline real y guardar `resultados`.
- `modulos/validacion/comparaciones.py`: comparar campos entre documentos del mismo folio segun
  `comparaciones` de los YAML (normalizando mayusculas, acentos y espacios) -> `ComparacionCampo`
  y alertas `CMP-001`.
- Completitud del expediente: si falta algun tipo de `tipos_requeridos` del proceso, alerta
  `EXP-001` (bloqueante) en `alertas_expediente`. Codigos: `docs/contratos/codigos_alertas.md`.
- Guardar los derivados que devuelva el motor (texto, paginas PNG, `resultado.json`) en las claves
  `derivados/` del punto 8.
- Recomendacion global: bloqueante -> `rechazar` no automatico, sino `revision_manual` con alerta;
  sin alertas criticas/bloqueantes y confianzas sobre el minimo -> `aprobar`; resto -> `revision_manual`.
- Endpoints del revisor: PATCH datos (guarda en correcciones), confirmar clasificacion, resolver
  alerta, decision del folio (rechazar si hay bloqueante no resuelta). Todo a auditoria.

## Etapa 3 (dias 9-12)
- `modulos/expediente/resumen.py`: plantilla Jinja `expediente/plantillas/resumen.md.j2` con
  referencia de la persona, tipos presentados, datos validados, alertas, resultado, decisiones y
  fecha (si se acepta ADR-004, `referencia_externa` y `fecha_solicitud`); regenerar en cada
  cambio, subir a S3 en `{proceso}/{anio}/{secuencia}/resumen.md`, exponer
  `GET /folios/{folio}/resumen.md`, avisar a `rag` para reindexar.
- Webhooks: `app/core/webhooks.py` con firma HMAC-SHA256, reintento x3, eventos del contrato.
- Enmascaramiento en logs (filtro de logging que oculta CURP, numeros de documento y domicilios).
- `GET /auditoria`.

## Como trabajar
- Antes de escribir codigo di en que modulo va. Commits `feat(ingesta): ...`.
- Reglas de validacion y parsers siempre con test.
- Si algo del contrato no encaja, propon un ADR en `docs/adr/` en vez de cambiarlo.
- Datos ficticios siempre; claves solo en `.env`.
