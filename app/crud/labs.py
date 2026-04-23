import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lab import Lab, LabProduct


async def get_active_labs(db: AsyncSession) -> list[Lab]:
    result = await db.execute(
        select(Lab)
        .where(Lab.is_active == True)
        .options(selectinload(Lab.products.and_(LabProduct.is_active == True)))
        .order_by(Lab.name)
    )
    return list(result.scalars().all())


async def get_all_labs(db: AsyncSession) -> list[Lab]:
    """Admin: returns all labs including inactive, with all products."""
    result = await db.execute(
        select(Lab)
        .options(selectinload(Lab.products))
        .order_by(Lab.name)
    )
    return list(result.scalars().all())


async def get_lab(db: AsyncSession, lab_id: uuid.UUID) -> Lab | None:
    result = await db.execute(
        select(Lab)
        .where(Lab.id == lab_id)
        .options(selectinload(Lab.products))
    )
    return result.scalar_one_or_none()


async def create_lab(db: AsyncSession, **kwargs) -> Lab:
    lab = Lab(**kwargs)
    db.add(lab)
    await db.commit()
    # Reload with products relationship eagerly loaded
    result = await db.execute(
        select(Lab).where(Lab.id == lab.id).options(selectinload(Lab.products))
    )
    return result.scalar_one()


async def update_lab(db: AsyncSession, lab: Lab, **kwargs) -> Lab:
    for key, value in kwargs.items():
        if value is not None:
            setattr(lab, key, value)
    await db.commit()
    result = await db.execute(
        select(Lab).where(Lab.id == lab.id).options(selectinload(Lab.products))
    )
    return result.scalar_one()


async def delete_lab(db: AsyncSession, lab: Lab) -> None:
    await db.delete(lab)
    await db.commit()


async def create_lab_product(db: AsyncSession, lab_id: uuid.UUID, **kwargs) -> LabProduct:
    product = LabProduct(lab_id=lab_id, **kwargs)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def update_lab_product(db: AsyncSession, product: LabProduct, **kwargs) -> LabProduct:
    for key, value in kwargs.items():
        if value is not None:
            setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product


async def delete_lab_product(db: AsyncSession, product: LabProduct) -> None:
    await db.delete(product)
    await db.commit()


async def get_lab_product(db: AsyncSession, product_id: uuid.UUID) -> LabProduct | None:
    result = await db.execute(select(LabProduct).where(LabProduct.id == product_id))
    return result.scalar_one_or_none()
