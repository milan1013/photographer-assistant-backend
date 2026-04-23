"""add print ordering tables: labs, lab_products, print_orders, order_items

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: str = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "labs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "lab_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lab_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="RSD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lab_products_lab_id", "lab_products", ["lab_id"])

    op.create_table(
        "print_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("gallery_id", sa.Uuid(), nullable=False),
        sa.Column("lab_id", sa.Uuid(), nullable=False),
        sa.Column("share_link_id", sa.Uuid(), nullable=True),
        sa.Column("ordered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("client_email", sa.String(255), nullable=True),
        sa.Column("client_phone", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="RSD"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["gallery_id"], ["galleries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["share_link_id"], ["share_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ordered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'completed', 'cancelled')", name="ck_order_status"),
    )
    op.create_index("ix_print_orders_gallery_id", "print_orders", ["gallery_id"])
    op.create_index("ix_print_orders_lab_id", "print_orders", ["lab_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=True),
        sa.Column("image_filename", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_id"], ["print_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["lab_products.id"], ondelete="SET NULL"),
        sa.CheckConstraint("quantity >= 1", name="ck_item_quantity"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_image_id", "order_items", ["image_id"])


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("print_orders")
    op.drop_table("lab_products")
    op.drop_table("labs")
