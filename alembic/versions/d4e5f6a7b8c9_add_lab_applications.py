"""add lab_applications table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: str = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lab_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lab_name", sa.String(255), nullable=False),
        sa.Column("lab_email", sa.String(255), nullable=False),
        sa.Column("lab_address", sa.String(500), nullable=True),
        sa.Column("lab_phone", sa.String(50), nullable=True),
        sa.Column("lab_website", sa.String(500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_lab_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_lab_id"], ["labs.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_lab_application_status"),
    )
    op.create_index("ix_lab_applications_lab_email", "lab_applications", ["lab_email"])
    op.create_index("ix_lab_applications_status", "lab_applications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lab_applications_status", "lab_applications")
    op.drop_index("ix_lab_applications_lab_email", "lab_applications")
    op.drop_table("lab_applications")
