import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Request
from app.database import get_db
from app.dependencies import get_active_share_link
import bleach
from pydantic import BaseModel
from sqlalchemy import select

from app.models.gallery_view import GalleryView
from app.models.comment import Comment
from app.models.user import User
from app.models.share_link import ShareLink
from app.schemas.share_link import SharedGalleryResponse
from app.schemas.image import ImageResponse, ImageListResponse, ImageUpdateCopies, BatchUpdateCopies
from app.crud.galleries import get_gallery, get_image_count
from app.crud.images import get_images_by_gallery, get_image, update_image_copies, batch_update_copies
from app.storage import get_storage, StorageBackend
from app.image_processing import apply_watermark

router = APIRouter()

_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


@router.get("/{token}/gallery", response_model=SharedGalleryResponse)
async def shared_gallery_info(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    gallery = await get_gallery(db, link.gallery_id)
    if not gallery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    count = await get_image_count(db, gallery.id)

    # Track view
    view = GalleryView(
        gallery_id=gallery.id,
        share_link_id=link.id,
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:500],
    )
    db.add(view)
    await db.commit()

    # Load owner branding
    owner_result = await db.execute(select(User).where(User.id == gallery.owner_id))
    owner = owner_result.scalar_one_or_none()

    return SharedGalleryResponse(
        gallery_name=gallery.name,
        gallery_description=gallery.description,
        permission=link.permission,
        image_count=count,
        branding_name=owner.branding_name if owner else None,
        branding_logo_url=owner.branding_logo_url if owner else None,
    )


@router.get("/{token}/images", response_model=ImageListResponse)
async def shared_gallery_images(
    token: str,
    sort_by: str = "sort_order",
    sort_dir: str = "asc",
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    images = await get_images_by_gallery(db, link.gallery_id, sort_by, sort_dir)
    return ImageListResponse(images=images, total=len(images))


@router.get("/{token}/images/{image_id}/file")
async def shared_image_file(
    token: str,
    image_id: uuid.UUID,
    size: str = "medium",
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if size == "thumbnail":
        key = image.thumbnail_key
        media_type = "image/webp"
    elif size == "medium" and image.medium_key:
        key = image.medium_key
        media_type = image.mime_type or "image/jpeg"
    else:
        key = image.storage_key
        media_type = image.mime_type or "image/jpeg"

    data = await _get_storage().get(key)

    # Apply watermark for view-only links
    if link.permission == "view":
        fmt = "WEBP" if media_type == "image/webp" else "JPEG"
        data = apply_watermark(data, "PREVIEW", fmt)

    return Response(content=data, media_type=media_type)


@router.get("/{token}/images/{image_id}/thumbnail")
async def shared_thumbnail(
    token: str,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    data = await _get_storage().get(image.thumbnail_key)

    # Apply watermark for view-only links
    if link.permission == "view":
        data = apply_watermark(data, "PREVIEW", "WEBP")

    return Response(content=data, media_type="image/webp")


@router.patch("/{token}/images/batch", response_model=dict)
async def shared_batch_update_copies(
    token: str,
    body: BatchUpdateCopies,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    if link.permission != "edit":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="View-only access")
    if body.num_copies < 0 or body.num_copies > 999:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="num_copies must be 0-999")
    count = await batch_update_copies(db, body.image_ids, link.gallery_id, body.num_copies)
    return {"updated": count}


@router.patch("/{token}/images/{image_id}", response_model=ImageResponse)
async def shared_update_copies(
    token: str,
    image_id: uuid.UUID,
    body: ImageUpdateCopies,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    if link.permission != "edit":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="View-only access")
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    if body.num_copies < 0 or body.num_copies > 999:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="num_copies must be 0-999")
    return await update_image_copies(db, image, body.num_copies)


# --- Comments ---

class CommentCreate(BaseModel):
    author_name: str
    text: str

class CommentResponse(BaseModel):
    id: uuid.UUID
    image_id: uuid.UUID
    author_name: str
    text: str
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/{token}/images/{image_id}/comments")
async def get_comments(
    token: str,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    result = await db.execute(
        select(Comment).where(Comment.image_id == image_id).order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [
        {"id": str(c.id), "image_id": str(c.image_id), "author_name": c.author_name, "text": c.text, "created_at": c.created_at.isoformat()}
        for c in comments
    ]


@router.post("/{token}/images/{image_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    token: str,
    image_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    clean_name = bleach.clean(body.author_name, tags=[], strip=True).strip()
    clean_text = bleach.clean(body.text, tags=[], strip=True).strip()

    if not clean_name or not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and comment required")

    comment = Comment(
        image_id=image_id,
        gallery_id=link.gallery_id,
        author_name=clean_name[:100],
        text=clean_text[:1000],
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return {"id": str(comment.id), "image_id": str(comment.image_id), "author_name": comment.author_name, "text": comment.text, "created_at": comment.created_at.isoformat()}
