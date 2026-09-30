# core

Responsable: PERSONA_1. Compartido por todos los modulos; `core` no importa ningun modulo (ADR-005).

## Ficheros
- `config.py`: `Settings` (pydantic-settings) y `get_settings()`. Lee el entorno y el `.env` de la raiz.
- `db.py`: `Base` de SQLAlchemy 2, `get_engine()` perezoso y dependencia `get_sesion()` de FastAPI.
- `modelos.py`: tablas de la plataforma. Migraciones en `backend/alembic/` (`alembic upgrade head`).
- `procesos.py`: valida `config/procesos.yaml` (`leer_procesos`) y lo vuelca a la tabla `procesos` al arrancar (`sincronizar_procesos`, upsert sin borrar).
- `errores.py`: `ErrorApi(http, codigo, mensaje)` y su manejador, que responde `{codigo, mensaje}` (ADR-006 1.4).
- `seguridad.py`: hash bcrypt, `crear_token` JWT y dependencias `usuario_actual` y `requiere_rol(*roles)`. Usuarios con `scripts/crear_usuario.py`.

## Tablas
- `usuarios`: usuario unico, hash bcrypt y rol (admin, revisor, integrador).
- `procesos`: procesos de `config/procesos.yaml`: prefijo de folio, tipos requeridos/opcionales, antecedentes, webhook, perfil de modelos.
- `folios`: folio `{PREFIJO}-{AAAA}-{NNNNNN}`, unico por (proceso, anio, secuencia); estado, referencia externa (ADR-004) y decision humana (ADR-006 G).
- `documentos`: original subido: ruta S3, SHA-256, tipo declarado/confirmado y estado de analisis.
- `resultados`: `ResultadoDocumento` en JSON, una fila por version; la vigente es la de version mayor.
- `alertas`: alertas de documento o de expediente (`documento_id` NULL), con revision (`aplica`, comentario, autor, fecha).
- `correcciones`: cambios del revisor sobre `datos_extraidos` (valor anterior y nuevo).
- `auditoria`: registro de acciones (`ACCIONES_AUDITORIA`), sin FK para no bloquear borrados.
