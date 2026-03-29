import uuid

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gallery import Gallery
from app.models.image import Image


async def get_galleries_by_owner(db: AsyncSession, owner_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(Gallery, func.count(Image.id).label("image_count"))
        .outerjoin(Image, Image.gallery_id == Gallery.id)
        .where(Gallery.owner_id == owner_id)
        .group_by(Gallery.id)
        .order_by(Gallery.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    galleries = []
    for gallery, image_count in rows:
        g = gallery.__dict__.copy()
        g["image_count"] = image_count
        galleries.append(g)
    return galleries


async def get_gallery(db: AsyncSession, gallery_id: uuid.UUID) -> Gallery | None:
    result = await db.execute(select(Gallery).where(Gallery.id == gallery_id))
    return result.scalar_one_or_none()


async def create_gallery(db: AsyncSession, owner_id: uuid.UUID, name: str, description: str | None = None) -> Gallery:
    gallery = Gallery(owner_id=owner_id, name=name, description=description)
    db.add(gallery)
    await db.commit()
    await db.refresh(gallery)
    return gallery


async def update_gallery(db: AsyncSession, gallery: Gallery, **kwargs) -> Gallery:
    for key, value in kwargs.items():
        if value is not None:
            setattr(gallery, key, value)
    await db.commit()
    await db.refresh(gallery)
    return gallery


async def delete_gallery(db: AsyncSession, gallery: Gallery) -> None:
    await db.delete(gallery)
    await db.commit()


async def get_image_count(db: AsyncSession, gallery_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count(Image.id)).where(Image.gallery_id == gallery_id))
    return result.scalar_one()


async def get_gallery_count(db: AsyncSession, owner_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count(Gallery.id)).where(Gallery.owner_id == owner_id))
    return result.scalar_one()
