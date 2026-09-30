from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
import app.core.modelos  # noqa: F401  registra las tablas en Base.metadata
from app.core.db import Base

config = context.config

if config.config_file_name is not None:
    # Sin desactivar los loggers de la app ya creados (p. ej. al migrar desde los tests)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# La URL sale siempre de los settings (.env), nunca de alembic.ini
config.set_main_option("sqlalchemy.url", get_settings().database_url.get_secret_value())

# Tablas de app.core.modelos
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectar a la BD (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones conectando a la BD."""
    conectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectable.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
