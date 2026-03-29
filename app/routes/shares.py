import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.share_link import ShareLinkCreate, ShareLinkUpdate, ShareLinkResponse
from app.crud.galleries import get_gallery
from app.crud.share_links import (
    get_share_links_by_gallery,
    get_share_link,
    create_share_link,
    update_share_link,
    delete_share_link,
)

router = APIRouter()


@router.get("/galleries/{gallery_id}/shares", response_model=list[ShareLinkResponse])
async def list_shares(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    return await get_share_links_by_gallery(db, gallery_id)


@router.post("/galleries/{gallery_id}/shares", response_model=ShareLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    gallery_id: uuid.UUID,
    body: ShareLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.permission not in ("view", "edit"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission must be 'view' or 'edit'")
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    return await create_share_link(db, gallery_id, body.permission, body.label, body.expires_at)


@router.patch("/shares/{share_id}", response_model=ShareLinkResponse)
async def update_share(
    share_id: uuid.UUID,
    body: ShareLinkUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await get_share_link(db, share_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    gallery = await get_gallery(db, link.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        link = await update_share_link(db, link, **update_data)
    return link


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await get_share_link(db, share_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    gallery = await get_gallery(db, link.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    await delete_share_link(db, link)
