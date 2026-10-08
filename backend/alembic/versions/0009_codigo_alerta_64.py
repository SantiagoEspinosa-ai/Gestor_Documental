"""alertas.codigo de 30 a 64 caracteres: los codigos REG-{id_regla} pueden superar 30 (p. ej.
REG-nacimiento_antes_de_expedicion tiene 34) y el documento acababa en error al guardar sus alertas.

El downgrade vuelve a 30 y falla, sin tocar nada, si hay codigos mas largos (se perderian al truncar).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LONGITUD_ANTERIOR = 30
LONGITUD_NUEVA = 64


def upgrade() -> None:
    """Amplia alertas.codigo a 64 caracteres."""
    # batch: SQLite no soporta ALTER COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('alertas') as batch:
        batch.alter_column('codigo', existing_type=sa.String(length=LONGITUD_ANTERIOR),
                           type_=sa.String(length=LONGITUD_NUEVA), existing_nullable=False)


def downgrade() -> None:
    """Vuelve alertas.codigo a 30 caracteres; falla si algun codigo no cabe."""
    largos = op.get_bind().scalar(sa.text(
        f"SELECT COUNT(*) FROM alertas WHERE LENGTH(codigo) > {LONGITUD_ANTERIOR}"))
    if largos:
        raise RuntimeError(f"No se puede bajar la 0009: {largos} alertas tienen un codigo de mas de "
                           f"{LONGITUD_ANTERIOR} caracteres")
    with op.batch_alter_table('alertas') as batch:
        batch.alter_column('codigo', existing_type=sa.String(length=LONGITUD_NUEVA),
                           type_=sa.String(length=LONGITUD_ANTERIOR), existing_nullable=False)
