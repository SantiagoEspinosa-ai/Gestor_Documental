"""Sesion de BD con SQLAlchemy 2.

El engine se crea en la primera peticion, no al importar: la app y los tests que no usan BD
arrancan sin PostgreSQL.
"""
import sqlite3
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _claves_foraneas_en_sqlite(conexion_dbapi, _registro) -> None:
    """SQLite no comprueba las FK por defecto; asi los tests fallan igual que PostgreSQL."""
    if isinstance(conexion_dbapi, sqlite3.Connection):
        cursor = conexion_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
