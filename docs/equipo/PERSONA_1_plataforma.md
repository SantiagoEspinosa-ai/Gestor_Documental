# Prompt de arranque - PERSONA_1 (Plataforma: ingesta, folios, S3, auth, API, expediente, webhooks)

Copia todo este bloque como primer mensaje en Claude Code dentro del repo.

---

Eres mi asistente de desarrollo en este repositorio. Lee primero `CLAUDE.md`, `README.md`, `docs/arquitectura.md`,
`docs/adr/*.md`, `docs/contratos/endpoints.md`, `backend/app/schemas/resultado.py` y
`backend/app/modulos/motor_ia/interfaces.py`. Son contratos congelados: no los modifiques.

Soy PERSONA_1 y soy responsable de los modulos `ingesta`, `api`, `expediente` y `core` (auth, BD,
S3, auditoria, webhooks). Otras dos personas trabajan en paralelo en `orquestador`/`motor_ia`
(PERSONA_2) y en `frontend`/`rag`/fixtures (PERSONA_3). No toques sus modulos: donde necesite
algo de ellos, usa la interfaz de `interfaces.py` y crea un stub que devuelva datos ficticios.

## Objetivo de la etapa 1 (dias 2-5)
Que se pueda crear un folio, subir un archivo por API con JWT, y que quede en S3 y en BD en estado
`pendiente` con su hash, ID unico y deteccion de duplicados. Todo con tests.

## Tarea previa (etapa 0): bucket S3 real de Amazon
Se usa Amazon S3 real, sin MinIO ni emuladores. En la consola de AWS (a mano, no desde el codigo):
- Bucket `S3_BUCKET` en `AWS_REGION`, con "Bloquear todo el acceso publico" activado.
- Usuario IAM del proyecto con permisos minimos solo sobre ese bucket: `s3:PutObject`,
  `s3:GetObject`, `s3:ListBucket`. Sin `s3:DeleteObject` (el original nunca se borra).
- CORS del bucket: permitir `GET` desde `http://localhost:5173` para que el visor del frontend
  abra las URL prefirmadas.
- Las claves van solo en el `.env` de cada persona que las necesite (PERSONA_3 para los e2e);
  se entregan por canal seguro, nunca en el repo ni en chats con IA.

## Tareas, en este orden
1. `app/core/config.py`: settings con pydantic-settings leyendo `.env` (ver `.env.example`).
   Nunca valores por defecto con claves reales.
2. `app/core/db.py`: engine SQLAlchemy 2 + sesion; Alembic inicializado en `backend/alembic/`.
3. Modelos en `app/core/modelos.py`: usuarios(id, usuario, hash_contrasena, rol),
   procesos(nombre, prefijo_folio, webhook_url, permitir_antecedentes, caducidad_antecedentes_dias),
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
8. `app/core/almacenamiento.py`: cliente boto3 contra Amazon S3 real (sin endpoint personalizado);
   `subir(bytes, clave)`,
   `url_prefirmada(clave)`, `descargar(clave)`. Clave: `{proceso}/{anio}/{secuencia}/{uuid}.{ext}`.
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
    auth por rol, ingesta e2e con S3 simulado con `moto` (nunca contra el bucket real).
    Usa solo datos ficticios.
12. README de cada modulo tuyo con contrato de entrada/salida.

## Etapa 2 (dias 6-8), cuando PERSONA_2 entregue `procesar_documento`
- Conectar el pipeline real y guardar `resultados`.
- `modulos/validacion/comparaciones.py`: comparar campos entre documentos del mismo folio segun
  `comparaciones` de los YAML (normalizando mayusculas, acentos y espacios) -> `ComparacionCampo`
  y alertas `CMP-xxx`.
- Recomendacion global: bloqueante -> `rechazar` no automatico, sino `revision_manual` con alerta;
  sin alertas criticas/bloqueantes y confianzas sobre el minimo -> `aprobar`; resto -> `revision_manual`.
- Endpoints del revisor: PATCH datos (guarda en correcciones), confirmar clasificacion, resolver
  alerta, decision del folio (rechazar si hay bloqueante no resuelta). Todo a auditoria.

## Cambios de contrato aceptados el 2026-09-30 (ADR-004 y ADR-006)
Ya aplicados en `resultado.py`, `endpoints.md`, `codigos_error.md` y `codigos_alertas.md`. Si algo de
lo anterior de este prompt los contradice, prevalecen ellos.
- Etapa 1: `GET /folios` paginado (`PaginaFolios` de `ResumenFolio`); `GET /procesos` tambien para
  el revisor, sin `webhook_url` ni `modelos`; `GET /folios/{folio}` rellena `referencia_externa` y
  `fecha_solicitud` (= `folios.creado_en`); login con `expires_in` y `GET /auth/yo`.
- Etapa 1: manejador global de errores con `{codigo, mensaje}` para todo, incluidos los 404/405 de
  rutas y metodos y los 422 de validacion de FastAPI (catalogo en `codigos_error.md`); limite de
  subida de 20 MB (413).
- Etapa 1: `GET /tipos-documentales` con la ficha que serializa PERSONA_2 y forma de `GET /auditoria`
  con la lista cerrada de `accion` (`endpoints.md`).
- Etapa 2: `Alerta.id` asignado al guardar; rutas de resolver por `alerta_id`, de documento y de
  expediente; guardar `aplica`, `comentario_revisor`, `resuelta_por`, `resuelta_en`.
- Etapa 2: regla de bloqueo en `/decision` (bloqueante con `aplica` distinto de `false` -> 409
  `DECISION_BLOQUEADA`); guardar `comentario_decision`, `usuario_decision`, `fecha_decision` y cerrar
  el folio (409 `FOLIO_CERRADO` despues).
- Etapa 2: `CMP-001` solo en `alertas_expediente`; `EXP-001` bloqueante; `correcciones` en
  `ResultadoDocumento` (confianza 1.0 y evidencia `correccion_revisor` en el campo corregido).
- Etapa 2: confirmar clasificacion rellena `tipo_documental_confirmado`; si difiere del tipo usado
  para extraer, guarda el resultado actual como version previa en `resultados`, pone el documento en
  `pendiente` y relanza `procesar_documento(documento_id, tipo_confirmado=...)` de PERSONA_2.
- Etapa 3: `GET /folios/{folio}/resumen.md` devuelve 404 `RESUMEN_NO_DISPONIBLE` mientras no exista.
- Fuera del MVP: reprocesar documentos en `error`.

## Etapa 3 (dias 9-12)
- `modulos/expediente/resumen.py`: plantilla Jinja `expediente/plantillas/resumen.md.j2` con
  referencia de la persona, tipos presentados, datos validados, alertas, resultado, decisiones y
  fecha; regenerar en cada cambio, subir a S3 en `{clave_folio}/resumen.md`, exponer
  `GET /folios/{folio}/resumen.md`, avisar a `rag` para reindexar.
- Webhooks: `app/core/webhooks.py` con firma HMAC-SHA256, reintento x3, eventos del contrato.
- Enmascaramiento en logs (filtro de logging que oculta CURP, numeros de documento y domicilios).
- `GET /auditoria`.

## Como trabajar
- Trabaja SOLO en la rama `feat/plataforma` (ver "Ramas y flujo de trabajo" en `CLAUDE.md`).
- Antes de escribir codigo di en que modulo va. Commits `feat(ingesta): ...`.
- Reglas de validacion y parsers siempre con test.
- Si algo del contrato no encaja, propon un ADR en `docs/adr/` en vez de cambiarlo.
- Datos ficticios siempre; claves solo en `.env`.
