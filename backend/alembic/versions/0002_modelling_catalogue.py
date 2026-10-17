"""modelling catalogue: reshape learning_objectives, add objective_prerequisites, retire SUVAT

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def retire_suvat() -> None:
    """Remove the SUVAT dev seed. Refuses to run if any student attempts exist."""
    conn = op.get_bind()
    attempts = conn.execute(sa.text("SELECT count(*) FROM attempts")).scalar_one()
    if attempts:
        raise RuntimeError(
            f"Refusing to retire SUVAT content: {attempts} attempt row(s) exist. "
            "Export or remove student data deliberately before running this migration."
        )
    conn.execute(sa.text("DELETE FROM questions"))
    # student_progress rows cascade with their objective.
    conn.execute(sa.text("DELETE FROM learning_objectives WHERE code LIKE 'suvat.%'"))


def upgrade() -> None:
    retire_suvat()

    op.drop_index(op.f('ix_learning_objectives_topic'), table_name='learning_objectives')
    with op.batch_alter_table('learning_objectives') as batch:
        batch.alter_column('topic', new_column_name='domain_area', existing_type=sa.String(length=100), existing_nullable=False)
        batch.alter_column('name', new_column_name='title', existing_type=sa.String(length=200), existing_nullable=False)
        # Server defaults only backfill any pre-existing rows; the seeder always sets these.
        batch.add_column(sa.Column('success_criteria', JSON_TYPE, server_default='[]', nullable=False))
        batch.add_column(sa.Column('domains', JSON_TYPE, server_default='[]', nullable=False))
        batch.add_column(sa.Column('evidence_types', JSON_TYPE, server_default='[]', nullable=False))
        batch.add_column(sa.Column('catalogue_version', sa.Integer(), server_default='1', nullable=False))
    with op.batch_alter_table('learning_objectives') as batch:
        for column in ('success_criteria', 'domains', 'evidence_types', 'catalogue_version'):
            batch.alter_column(column, server_default=None)

    op.create_table('objective_prerequisites',
    sa.Column('objective_id', sa.Integer(), nullable=False),
    sa.Column('prerequisite_id', sa.Integer(), nullable=False),
    sa.CheckConstraint('objective_id <> prerequisite_id', name=op.f('ck_objective_prerequisites_not_self')),
    sa.ForeignKeyConstraint(['objective_id'], ['learning_objectives.id'], name=op.f('fk_objective_prerequisites_objective_id_learning_objectives'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['prerequisite_id'], ['learning_objectives.id'], name=op.f('fk_objective_prerequisites_prerequisite_id_learning_objectives'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('objective_id', 'prerequisite_id', name=op.f('pk_objective_prerequisites'))
    )


def downgrade() -> None:
    # Restores the 0001 column shape only; retired SUVAT seed rows are not restored.
    op.drop_table('objective_prerequisites')
    with op.batch_alter_table('learning_objectives') as batch:
        batch.drop_column('catalogue_version')
        batch.drop_column('evidence_types')
        batch.drop_column('domains')
        batch.drop_column('success_criteria')
        batch.alter_column('title', new_column_name='name', existing_type=sa.String(length=200), existing_nullable=False)
        batch.alter_column('domain_area', new_column_name='topic', existing_type=sa.String(length=100), existing_nullable=False)
    op.create_index(op.f('ix_learning_objectives_topic'), 'learning_objectives', ['topic'], unique=False)
