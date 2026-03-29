import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.gallery_view import GalleryView
from app.models.comment import Comment
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.gallery import GalleryCreate, GalleryUpdate, GalleryResponse, GalleryListResponse
from app.config import settings
from app.crud.galleries import (
    get_galleries_by_owner,
    get_gallery,
    get_gallery_count,
    create_gallery,
    update_gallery,
    delete_gallery,
    get_image_count,
)

router = APIRouter()


@router.get("", response_model=GalleryListResponse)
async def list_galleries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    galleries = await get_galleries_by_owner(db, current_user.id)
    return GalleryListResponse(galleries=galleries)


@router.post("", response_model=GalleryResponse, status_code=status.HTTP_201_CREATED)
async def create_gallery_route(
    body: GalleryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await get_gallery_count(db, current_user.id)
    if count >= settings.max_galleries_per_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.max_galleries_per_user} galleries allowed",
        )
    gallery = await create_gallery(db, current_user.id, body.name, body.description)
    return GalleryResponse(**gallery.__dict__, image_count=0)


@router.get("/{gallery_id}", response_model=GalleryResponse)
async def get_gallery_route(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    count = await get_image_count(db, gallery_id)
    return GalleryResponse(**gallery.__dict__, image_count=count)


@router.patch("/{gallery_id}", response_model=GalleryResponse)
async def update_gallery_route(
    gallery_id: uuid.UUID,
    body: GalleryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        gallery = await update_gallery(db, gallery, **update_data)
    count = await get_image_count(db, gallery_id)
    return GalleryResponse(**gallery.__dict__, image_count=count)


@router.delete("/{gallery_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gallery_route(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    await delete_gallery(db, gallery)


@router.get("/{gallery_id}/analytics")
async def gallery_analytics(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    # Total views
    total = await db.execute(
        select(func.count(GalleryView.id)).where(GalleryView.gallery_id == gallery_id)
    )
    total_views = total.scalar_one()

    # Unique IPs
    unique = await db.execute(
        select(func.count(func.distinct(GalleryView.ip_address))).where(GalleryView.gallery_id == gallery_id)
    )
    unique_visitors = unique.scalar_one()

    # Recent views (last 20)
    recent = await db.execute(
        select(GalleryView)
        .where(GalleryView.gallery_id == gallery_id)
        .order_by(GalleryView.viewed_at.desc())
        .limit(20)
    )
    views = [
        {
            "ip_address": v.ip_address,
            "user_agent": v.user_agent[:100] if v.user_agent else None,
            "viewed_at": v.viewed_at.isoformat(),
        }
        for v in recent.scalars().all()
    ]

    return {
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "recent_views": views,
    }


@router.get("/{gallery_id}/comments")
async def gallery_comments(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    result = await db.execute(
        select(Comment).where(Comment.gallery_id == gallery_id).order_by(Comment.created_at.desc())
    )
    comments = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "image_id": str(c.image_id),
            "author_name": c.author_name,
            "text": c.text,
            "created_at": c.created_at.isoformat(),
        }
        for c in comments
    ]
