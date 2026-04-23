"""add profile fields: phone, website, social, bio

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("website_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("instagram_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("facebook_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bio")
    op.drop_column("users", "facebook_url")
    op.drop_column("users", "instagram_url")
    op.drop_column("users", "website_url")
    op.drop_column("users", "phone")
