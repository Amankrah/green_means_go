"""add assessment_revisions table + version/current_revision_id for immutable history

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-20

Schema-only. Existing assessments keep working: reads synthesize a 'current' revision
for rows that predate this table, and the next write starts a real revision chain.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assessments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("current_revision_id", sa.String(length=36), nullable=True)
        )

    op.create_table(
        "assessment_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("lcia_method", sa.String(length=128), nullable=True),
        sa.Column("single_score", sa.Float(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("assessment_revisions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_assessment_revisions_assessment_id"),
            ["assessment_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("assessment_revisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_assessment_revisions_assessment_id"))
    op.drop_table("assessment_revisions")
    with op.batch_alter_table("assessments", schema=None) as batch_op:
        batch_op.drop_column("current_revision_id")
        batch_op.drop_column("version")
