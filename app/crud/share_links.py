import secrets
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.share_link import ShareLink


async def get_share_links_by_gallery(db: AsyncSession, gallery_id: uuid.UUID) -> list[ShareLink]:
    result = await db.execute(
        select(ShareLink).where(ShareLink.gallery_id == gallery_id).order_by(ShareLink.created_at.desc())
    )
    return list(result.scalars().all())


async def get_share_link(db: AsyncSession, share_id: uuid.UUID) -> ShareLink | None:
    result = await db.execute(select(ShareLink).where(ShareLink.id == share_id))
    return result.scalar_one_or_none()


async def create_share_link(
    db: AsyncSession,
    gallery_id: uuid.UUID,
    permission: str,
    label: str | None = None,
    expires_at: datetime | None = None,
) -> ShareLink:
    token = secrets.token_urlsafe(48)
    link = ShareLink(
        gallery_id=gallery_id,
        token=token,
        permission=permission,
        label=label,
        expires_at=expires_at,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def update_share_link(db: AsyncSession, link: ShareLink, **kwargs) -> ShareLink:
    for key, value in kwargs.items():
        if value is not None:
            setattr(link, key, value)
    await db.commit()
    await db.refresh(link)
    return link


async def delete_share_link(db: AsyncSession, link: ShareLink) -> None:
    await db.delete(link)
    await db.commit()
