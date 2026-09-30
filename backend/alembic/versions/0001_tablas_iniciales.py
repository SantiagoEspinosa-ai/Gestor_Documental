"""Tablas iniciales de la plataforma (app.core.modelos).

Revision ID: 0001
Revises: 
Create Date: 2026-09-30 16:37:06.210576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea las 8 tablas."""
    op.create_table('auditoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario', sa.String(length=100), nullable=True),
    sa.Column('accion', sa.String(length=50), nullable=False),
    sa.Column('folio', sa.String(length=30), nullable=True),
    sa.Column('documento_id', sa.Uuid(), nullable=True),
    sa.Column('detalle', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('modelo', sa.String(length=100), nullable=True),
    sa.Column('version_prompt', sa.String(length=100), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auditoria_folio'), 'auditoria', ['folio'], unique=False)
    op.create_table('procesos',
    sa.Column('nombre', sa.String(length=50), nullable=False),
    sa.Column('prefijo_folio', sa.String(length=10), nullable=False),
    sa.Column('tipos_requeridos', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('tipos_opcionales', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('permitir_antecedentes', sa.Boolean(), nullable=False),
    sa.Column('caducidad_antecedentes_dias', sa.Integer(), nullable=False),
    sa.Column('webhook_url', sa.String(length=500), nullable=True),
    sa.Column('modelos', sa.String(length=50), server_default='default', nullable=False),
    sa.PrimaryKeyConstraint('nombre'),
    sa.UniqueConstraint('prefijo_folio')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario', sa.String(length=100), nullable=False),
    sa.Column('hash_contrasena', sa.String(length=255), nullable=False),
    sa.Column('rol', sa.String(length=20), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("rol IN ('admin', 'revisor', 'integrador')", name='ck_usuarios_rol'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario')
    )
    op.create_table('folios',
    sa.Column('folio', sa.String(length=30), nullable=False),
    sa.Column('proceso', sa.String(length=50), nullable=False),
    sa.Column('anio', sa.Integer(), nullable=False),
    sa.Column('secuencia', sa.Integer(), nullable=False),
    sa.Column('estado_general', sa.String(length=20), server_default='en_revision', nullable=False),
    sa.Column('referencia_externa', sa.String(length=100), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('decision', sa.String(length=10), nullable=True),
    sa.Column('decision_comentario', sa.Text(), nullable=True),
    sa.Column('decision_usuario', sa.String(length=100), nullable=True),
    sa.Column('decision_fecha', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("decision IS NULL OR decision IN ('aprobar', 'rechazar')", name='ck_folios_decision'),
    sa.CheckConstraint("estado_general IN ('en_revision', 'aprobado', 'rechazado')", name='ck_folios_estado_general'),
    sa.ForeignKeyConstraint(['proceso'], ['procesos.nombre'], ),
    sa.PrimaryKeyConstraint('folio'),
    sa.UniqueConstraint('proceso', 'anio', 'secuencia', name='uq_folios_proceso_anio_secuencia')
    )
    op.create_table('documentos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('folio', sa.String(length=30), nullable=False),
    sa.Column('nombre_archivo', sa.String(length=255), nullable=False),
    sa.Column('ruta_s3', sa.String(length=500), nullable=False),
    sa.Column('hash_sha256', sa.String(length=64), nullable=False),
    sa.Column('tipo_declarado', sa.String(length=50), nullable=True),
    sa.Column('tipo_documental_confirmado', sa.String(length=50), nullable=True),
    sa.Column('estado_analisis', sa.String(length=20), server_default='pendiente', nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("estado_analisis IN ('pendiente', 'procesando', 'completado', 'error')", name='ck_documentos_estado_analisis'),
    sa.ForeignKeyConstraint(['folio'], ['folios.folio'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documentos_folio_hash', 'documentos', ['folio', 'hash_sha256'], unique=False)
    op.create_index(op.f('ix_documentos_hash_sha256'), 'documentos', ['hash_sha256'], unique=False)
    op.create_table('alertas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('folio', sa.String(length=30), nullable=False),
    sa.Column('documento_id', sa.Uuid(), nullable=True),
    sa.Column('codigo', sa.String(length=30), nullable=False),
    sa.Column('severidad', sa.String(length=20), nullable=False),
    sa.Column('mensaje', sa.Text(), nullable=False),
    sa.Column('confianza', sa.Float(), nullable=False),
    sa.Column('campo', sa.String(length=100), nullable=True),
    sa.Column('resuelta_por_revisor', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('aplica', sa.Boolean(), nullable=True),
    sa.Column('comentario', sa.Text(), nullable=True),
    sa.Column('resuelta_por', sa.String(length=100), nullable=True),
    sa.Column('resuelta_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("severidad IN ('informativa', 'preventiva', 'critica', 'bloqueante')", name='ck_alertas_severidad'),
    sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ),
    sa.ForeignKeyConstraint(['folio'], ['folios.folio'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alertas_documento_id'), 'alertas', ['documento_id'], unique=False)
    op.create_index(op.f('ix_alertas_folio'), 'alertas', ['folio'], unique=False)
    op.create_table('correcciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('documento_id', sa.Uuid(), nullable=False),
    sa.Column('campo', sa.String(length=100), nullable=False),
    sa.Column('valor_anterior', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('valor_nuevo', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('usuario', sa.String(length=100), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resultados',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('documento_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('documento_id', 'version', name='uq_resultados_documento_version')
    )


def downgrade() -> None:
    """Borra las tablas en orden inverso a las FK."""
    op.drop_table('resultados')
    op.drop_table('correcciones')
    op.drop_index(op.f('ix_alertas_folio'), table_name='alertas')
    op.drop_index(op.f('ix_alertas_documento_id'), table_name='alertas')
    op.drop_table('alertas')
    op.drop_index(op.f('ix_documentos_hash_sha256'), table_name='documentos')
    op.drop_index('ix_documentos_folio_hash', table_name='documentos')
    op.drop_table('documentos')
    op.drop_table('folios')
    op.drop_table('usuarios')
    op.drop_table('procesos')
    op.drop_index(op.f('ix_auditoria_folio'), table_name='auditoria')
    op.drop_table('auditoria')
