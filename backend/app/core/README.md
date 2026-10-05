# core

Responsable: PERSONA_1. Compartido por todos los modulos; `core` no importa ningun modulo (ADR-005).

## Ficheros
- `config.py`: `Settings` (pydantic-settings) y `get_settings()`. Lee el entorno y el `.env` de la raiz. `CORS_ORIGENES`: origenes separados por comas (por defecto `http://localhost:5173`); con `*` no arranca. `MOTOR_ANALISIS`: `real` (por defecto, el orquestador de PERSONA_2) o `stub` (pruebas sin Ollama); otro valor no arranca.
- `cors.py`: `CorsDesdeSettings`, el `CORSMiddleware` de Starlette con `CORS_ORIGENES`, los metodos del contrato (`GET`, `POST`, `PATCH` y `OPTIONS`), cabeceras `Authorization` y `Content-Type` y sin credenciales (el token va en la cabecera, no en cookies). Se construye con los Settings de la primera peticion.
- `db.py`: `Base` de SQLAlchemy 2, `get_engine()` perezoso y dependencia `get_sesion()` de FastAPI.
- `modelos.py`: tablas de la plataforma. Migraciones en `backend/alembic/` (`alembic upgrade head`).
- `procesos.py`: valida `config/procesos.yaml` (`leer_procesos(config_dir, tipos_existentes)`; los tipos los pasa `main.py` desde `configuracion.servicio`, porque core no importa modulos) y lo vuelca a la tabla `procesos` al arrancar (`sincronizar_procesos`, upsert sin borrar).
- `errores.py`: `ErrorApi(http, codigo, mensaje, headers)` y manejadores globales (`registrar_manejadores`): todo error sale como `{codigo, mensaje}` (ADR-006 1.4); 422 sin valores de campo, 500 sin detalles internos.
- `auditoria.py`: `registrar(sesion, accion, ...)` valida la accion contra `ACCIONES_AUDITORIA` y hace `add` sin commit; `listar(sesion, folio, pagina, tamano_pagina)` para `GET /auditoria`.
- `seguridad.py`: hash bcrypt, `crear_token` JWT y dependencias `usuario_actual` y `requiere_rol(*roles)`. Usuarios con `scripts/crear_usuario.py`.
- `webhooks.py` (etapa 3): webhooks de salida del Contrato 2. `POST` a la `webhook_url` del proceso con `X-Firma: sha256=<hex HMAC-SHA256(cuerpo, WEBHOOK_SECRET_HMAC)>` sobre los mismos bytes enviados y cuerpo `{evento, fecha, folio, identificador_unico_documento?, datos}` (`datos` = `ResultadoDocumento` en `documento.completado`/`documento.error`, `ResultadoExpediente` en `folio.estado_cambiado`, serializado como en la API; el identificador solo en `documento.*`). `httpx` con timeout de 5 s, sin seguir redirecciones (un 3xx es un fallo) y verificando el certificado. primer intento inmediato y, si falla, 3 reintentos con espera de 1, 5 y 25 s antes de cada uno (4 intentos como maximo); exito = 2xx; sin tabla, solo logs con evento, folio, intento, estado HTTP y el host (nunca el cuerpo, la firma, el secreto ni la URL completa). Fuera de `APP_ENV=dev`, solo `https`; con el secreto vacio, o con el de ejemplo fuera de dev, no se envia y se avisa. `enmascarar_para_webhook` es el unico punto donde se enmascarara (ADR-010 A5, cuando llegue H15). Como core no importa modulos, quien llama pasa el resultado ya construido: `ingesta/procesamiento.py` tras cada analisis (tambien los reprocesos) y `expediente.decidir_folio` tras decidir, siempre despues del commit y en un hilo aparte (`enviar_en_segundo_plano`); un fallo no cambia el documento ni el folio ni la respuesta. Sin `webhook_url` en el proceso no se envia nada.
- `almacenamiento.py`: puerto `Almacenamiento` y adaptador `AlmacenamientoS3` (boto3, S3 real, SSE-S3). `subir` es solo para originales y nunca sobrescribe (`IfNoneMatch="*"`); `subir_derivado` es para los derivados que se regeneran (`resumen.md`) y si sobrescribe, con el mismo SSE. `clave_original(...)`, `clave_derivado(proceso, anio, secuencia, nombre)` (junto a los originales del folio) y dependencia `get_almacenamiento()`. Tests solo con `moto`. El bucket real y el usuario IAM los crea PERSONA_1 a mano en la consola de AWS (tarea previa de `docs/equipo/PERSONA_1_plataforma.md`).

## Tablas
- `usuarios`: usuario unico, hash bcrypt y rol (admin, revisor, integrador).
- `procesos`: procesos de `config/procesos.yaml`: prefijo de folio, tipos requeridos/opcionales, antecedentes, webhook, perfil de modelos.
- `folios`: folio `{PREFIJO}-{AAAA}-{NNNNNN}`, unico por (proceso, anio, secuencia); estado, referencia externa (ADR-004) y decision humana (ADR-006 G).
- `secuencias_folio`: ultimo numero por (proceso, anio); se incrementa con un solo `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`.
- `documentos`: original subido: ruta S3, SHA-256, tipo declarado/confirmado y estado de analisis.
- `resultados`: `ResultadoDocumento` en JSON, una fila por version; la vigente es la de version mayor.
- `alertas`: alertas de documento o de expediente (`documento_id` NULL), con revision (`aplica`, comentario, autor, fecha). `version_resultado`: NULL = de plataforma (DUP, EXP, CMP); N = del motor en la version N del resultado (migracion 0003).
- `correcciones`: cambios del revisor sobre `datos_extraidos` (valor anterior y nuevo), con `version_resultado` = la version del Resultado sobre la que se hizo; solo se aplican a esa version (migracion 0004).
- `auditoria`: registro de acciones (`ACCIONES_AUDITORIA`), sin FK para no bloquear borrados.
