import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.print_order import PrintOrder, OrderItem
from app.models.gallery import Gallery


async def create_order(
    db: AsyncSession,
    gallery_id: uuid.UUID,
    lab_id: uuid.UUID,
    total_price: Decimal,
    currency: str,
    items_data: list[dict],
    share_link_id: uuid.UUID | None = None,
    ordered_by_user_id: uuid.UUID | None = None,
    client_name: str | None = None,
    client_email: str | None = None,
    client_phone: str | None = None,
    note: str | None = None,
) -> PrintOrder:
    order = PrintOrder(
        gallery_id=gallery_id,
        lab_id=lab_id,
        share_link_id=share_link_id,
        ordered_by_user_id=ordered_by_user_id,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        total_price=total_price,
        currency=currency,
        note=note,
    )
    db.add(order)
    await db.flush()

    for item in items_data:
        db.add(OrderItem(order_id=order.id, **item))

    await db.commit()
    await db.refresh(order)
    # Reload with relationships
    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.id == order.id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
    )
    return result.scalar_one()


async def get_orders_by_gallery(db: AsyncSession, gallery_id: uuid.UUID) -> list[PrintOrder]:
    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.gallery_id == gallery_id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
        .order_by(PrintOrder.created_at.desc())
    )
    return list(result.scalars().all())


async def get_orders_by_owner(db: AsyncSession, owner_id: uuid.UUID) -> list[PrintOrder]:
    result = await db.execute(
        select(PrintOrder)
        .join(Gallery, PrintOrder.gallery_id == Gallery.id)
        .where(Gallery.owner_id == owner_id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
        .order_by(PrintOrder.created_at.desc())
    )
    return list(result.scalars().all())


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> PrintOrder | None:
    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.id == order_id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
    )
    return result.scalar_one_or_none()


async def update_order_status(db: AsyncSession, order: PrintOrder, new_status: str) -> PrintOrder:
    order.status = new_status
    await db.commit()
    await db.refresh(order)
    return order
