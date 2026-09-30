"""Sesion de BD con SQLAlchemy 2.

El engine se crea en la primera peticion, no al importar: la app y los tests que no usan BD
arrancan sin PostgreSQL.
"""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


SesionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)


def get_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesion por peticion, cerrada siempre al terminar."""
    sesion = SesionLocal(bind=get_engine())
    try:
        yield sesion
    finally:
        sesion.close()
