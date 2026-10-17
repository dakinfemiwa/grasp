"""scenario library references on instances; Edexcel spec refs on objectives

Every instance now records the scenario (id + version) it was generated with. Rows created
before the scenario library (all QUAD-RECT-AREA, abstract "A rectangle ... cm" wording) are
backfilled to SCN-RECT-ABSTRACT v1, whose wording and sampling reproduce them exactly.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    with op.batch_alter_table('learning_objectives') as batch:
        batch.add_column(sa.Column('spec_refs', JSON_TYPE, server_default='[]', nullable=False))
    with op.batch_alter_table('learning_objectives') as batch:
        batch.alter_column('spec_refs', server_default=None)

    op.add_column('question_instances', sa.Column('scenario_version', sa.Integer(), nullable=True))
    conn = op.get_bind()
    # scenario_id may already read SCN-RECT-ABSTRACT if this revision was applied and downgraded.
    conn.execute(sa.text(
        "UPDATE question_instances SET scenario_id = 'SCN-RECT-ABSTRACT', scenario_version = 1 "
        "WHERE scenario_version IS NULL AND template_id = 'QUAD-RECT-AREA' AND template_version = 1 "
        "AND (scenario_id IS NULL OR scenario_id = 'SCN-RECT-ABSTRACT')"
    ))
    orphans = conn.execute(sa.text(
        "SELECT count(*) FROM question_instances WHERE scenario_id IS NULL OR scenario_version IS NULL"
    )).scalar_one()
    if orphans:
        raise RuntimeError(f"{orphans} question_instances row(s) have no known scenario; assign one before migrating.")

    with op.batch_alter_table('question_instances') as batch:
        batch.alter_column('scenario_id', existing_type=sa.String(length=60), nullable=False)
        batch.alter_column('scenario_version', existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint('uq_question_instances_template_seed', type_='unique')
        batch.create_unique_constraint(
            'uq_question_instances_generation',
            ['template_id', 'template_version', 'scenario_id', 'scenario_version', 'seed'],
        )


def downgrade() -> None:
    conn = op.get_bind()
    clashes = conn.execute(sa.text(
        "SELECT count(*) FROM (SELECT 1 FROM question_instances "
        "GROUP BY template_id, template_version, seed HAVING count(*) > 1) AS d"
    )).scalar_one()
    if clashes:
        raise RuntimeError(
            f"Refusing to downgrade: {clashes} (template, version, seed) group(s) differ only by scenario."
        )
    with op.batch_alter_table('question_instances') as batch:
        batch.drop_constraint('uq_question_instances_generation', type_='unique')
        batch.create_unique_constraint(
            'uq_question_instances_template_seed', ['template_id', 'template_version', 'seed']
        )
        batch.alter_column('scenario_id', existing_type=sa.String(length=60), nullable=True)
        batch.drop_column('scenario_version')
    with op.batch_alter_table('learning_objectives') as batch:
        batch.drop_column('spec_refs')
