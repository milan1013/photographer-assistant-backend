import uuid

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image import Image


async def get_images_by_gallery(
    db: AsyncSession,
    gallery_id: uuid.UUID,
    sort_by: str = "sort_order",
    sort_dir: str = "asc",
) -> list[Image]:
    column_map = {
        "sort_order": Image.sort_order,
        "filename": Image.filename,
        "num_copies": Image.num_copies,
        "created_at": Image.created_at,
    }
    col = column_map.get(sort_by, Image.sort_order)
    order = col.desc() if sort_dir == "desc" else col.asc()

    stmt = select(Image).where(Image.gallery_id == gallery_id).order_by(order, Image.filename.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_image(db: AsyncSession, image_id: uuid.UUID) -> Image | None:
    result = await db.execute(select(Image).where(Image.id == image_id))
    return result.scalar_one_or_none()


async def create_image(db: AsyncSession, **kwargs) -> Image:
    image = Image(**kwargs)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


async def update_image_copies(db: AsyncSession, image: Image, num_copies: int) -> Image:
    image.num_copies = num_copies
    await db.commit()
    await db.refresh(image)
    return image


async def batch_update_copies(db: AsyncSession, image_ids: list[uuid.UUID], gallery_id: uuid.UUID, num_copies: int) -> int:
    stmt = (
        update(Image)
        .where(Image.id.in_(image_ids), Image.gallery_id == gallery_id)
        .values(num_copies=num_copies)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def delete_image(db: AsyncSession, image: Image) -> None:
    await db.delete(image)
    await db.commit()


async def get_existing_filenames(db: AsyncSession, gallery_id: uuid.UUID, filenames: list[str]) -> set[str]:
    result = await db.execute(
        select(Image.filename).where(Image.gallery_id == gallery_id, Image.filename.in_(filenames))
    )
    return set(result.scalars().all())


async def get_next_sort_order(db: AsyncSession, gallery_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Image.sort_order), -1)).where(Image.gallery_id == gallery_id)
    )
    return result.scalar_one() + 1
