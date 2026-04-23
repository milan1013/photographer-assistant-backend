import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Numeric, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PrintOrder(Base):
    __tablename__ = "print_orders"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'confirmed', 'completed', 'cancelled')", name="ck_order_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    gallery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("galleries.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("labs.id", ondelete="RESTRICT"), nullable=False, index=True)
    share_link_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("share_links.id", ondelete="SET NULL"), nullable=True)
    ordered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RSD")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    gallery = relationship("Gallery")
    lab = relationship("Lab", back_populates="orders")
    share_link = relationship("ShareLink")
    ordered_by_user = relationship("User")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_item_quantity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("print_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True)
    image_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lab_products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order = relationship("PrintOrder", back_populates="items")
    image = relationship("Image")
    product = relationship("LabProduct")
