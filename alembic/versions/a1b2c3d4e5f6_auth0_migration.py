"""Auth0 migration: add auth0_sub, remove password_hash, email_verified, refresh_tokens

Revision ID: a1b2c3d4e5f6
Revises: e532e6704930
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str = "96f39ea3255c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auth0_sub column
    op.add_column("users", sa.Column("auth0_sub", sa.String(255), nullable=True))
    op.create_index("ix_users_auth0_sub", "users", ["auth0_sub"], unique=True)

    # Drop password_hash and email_verified columns
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email_verified")

    # Drop refresh_tokens table
    op.drop_table("refresh_tokens")


def downgrade() -> None:
    # Recreate refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Add back columns
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default="false"))
    op.add_column("users", sa.Column("password_hash", sa.String(255), server_default=""))

    # Remove auth0_sub
    op.drop_index("ix_users_auth0_sub", "users")
    op.drop_column("users", "auth0_sub")
