import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UpdateProfileRequest, UserResponse

logger = logging.getLogger("fotomil")
router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import bleach

    for field, max_len in [
        ("branding_name", 255), ("phone", 50), ("bio", 500),
        ("website_url", 500), ("instagram_url", 500), ("facebook_url", 500),
    ]:
        val = getattr(body, field)
        if val is None:
            continue  # field not sent in request
        cleaned = bleach.clean(val, tags=[], strip=True).strip()[:max_len]
        setattr(current_user, field, cleaned or None)

    if body.branding_logo_url is not None:
        current_user.branding_logo_url = body.branding_logo_url.strip()[:500] or None
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/profile/logo", response_model=UserResponse)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.storage import get_storage
    from app.image_processing import generate_thumbnail

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        raise HTTPException(status_code=400, detail="Logo must be JPG, PNG, or WebP")

    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 2MB")

    thumb = generate_thumbnail(data, max_size=128)
    logo_key = f"logos/{current_user.id}.webp"

    storage = get_storage()
    await storage.save(logo_key, thumb)

    current_user.branding_logo_url = f"/api/auth/logo/{current_user.id}"
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/logo/{user_id}")
async def serve_logo(user_id: str):
    from app.storage import get_storage
    storage = get_storage()
    try:
        data = await storage.get(f"logos/{user_id}.webp")
        return Response(content=data, media_type="image/webp")
    except Exception:
        raise HTTPException(status_code=404, detail="Logo not found")


@router.post("/profile/change-password")
async def change_password(current_user: User = Depends(get_current_user)):
    from app.auth0_mgmt import send_password_reset_email

    if not current_user.auth0_sub.startswith("auth0|"):
        raise HTTPException(
            status_code=400,
            detail="Password is managed by your social login provider.",
        )

    ok = await send_password_reset_email(current_user.email)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to send reset email")
    return {"status": "ok"}


@router.get("/profile/identities")
async def get_identities(current_user: User = Depends(get_current_user)):
    from app.auth0_mgmt import get_user_identities

    identities = await get_user_identities(current_user.auth0_sub)
    return identities


@router.delete("/profile/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.storage import get_storage
    from app.auth0_mgmt import delete_auth0_user
    from app.models.gallery import Gallery
    from app.models.image import Image
    from sqlalchemy import select

    storage = get_storage()

    # Delete all user's stored files
    galleries = (await db.execute(
        select(Gallery).where(Gallery.owner_id == current_user.id)
    )).scalars().all()

    for gallery in galleries:
        images = (await db.execute(
            select(Image).where(Image.gallery_id == gallery.id)
        )).scalars().all()
        for img in images:
            for suffix in ["original", "medium", "thumbnail"]:
                try:
                    await storage.delete(f"images/{img.id}/{suffix}")
                except Exception:
                    pass

    # Delete logo
    try:
        await storage.delete(f"logos/{current_user.id}.webp")
    except Exception:
        pass

    # Delete from DB (cascades handle galleries, images, share_links, comments, views)
    await db.delete(current_user)
    await db.commit()

    # Delete from Auth0
    await delete_auth0_user(current_user.auth0_sub)

    return {"status": "deleted"}
