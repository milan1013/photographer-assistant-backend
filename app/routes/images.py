import os
import uuid
import mimetypes

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.image import ImageResponse, ImageUpdateCopies, BatchUpdateCopies, ImageListResponse, UploadResponse
from app.crud.galleries import get_gallery, get_image_count
from app.crud.images import (
    get_images_by_gallery,
    get_image,
    get_existing_filenames,
    create_image,
    update_image_copies,
    batch_update_copies,
    delete_image,
    get_next_sort_order,
)
from app.storage import get_storage, StorageBackend
from app.image_processing import (
    SUPPORTED_EXTENSIONS,
    generate_thumbnail,
    generate_medium,
    get_image_dimensions,
    extract_exif,
)

router = APIRouter()

_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


@router.get("/galleries/{gallery_id}/images", response_model=ImageListResponse)
async def list_images(
    gallery_id: uuid.UUID,
    sort_by: str = "sort_order",
    sort_dir: str = "asc",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    images = await get_images_by_gallery(db, gallery_id, sort_by, sort_dir)
    return ImageListResponse(images=images, total=len(images))


@router.post("/galleries/{gallery_id}/images", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_images(
    gallery_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    # Check image count limit
    current_count = await get_image_count(db, gallery_id)
    if current_count >= settings.max_images_per_gallery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.max_images_per_gallery} images per gallery allowed",
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024
    created_images = []
    skipped = []

    # Check for duplicate filenames
    incoming_names = [f.filename or "" for f in files]
    existing = await get_existing_filenames(db, gallery_id, incoming_names)

    for file in files:
        if file.filename in existing:
            skipped.append(file.filename)
            continue
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}",
            )

        data = await file.read()
        if len(data) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} exceeds {settings.max_upload_size_mb}MB limit",
            )

        file_id = uuid.uuid4()
        original_key = f"originals/{gallery_id}/{file_id}{ext}"
        thumbnail_key = f"thumbnails/{gallery_id}/{file_id}.webp"
        medium_key = f"medium/{gallery_id}/{file_id}{ext}"

        # Generate variants
        thumbnail_data = generate_thumbnail(data, settings.thumbnail_max_size)
        medium_data = generate_medium(data, settings.medium_max_size)
        width, height = get_image_dimensions(data)
        exif = extract_exif(data)

        # Store files
        await _get_storage().save(original_key, data)
        await _get_storage().save(thumbnail_key, thumbnail_data)
        await _get_storage().save(medium_key, medium_data)

        sort_order = await get_next_sort_order(db, gallery_id)

        mime_type = mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

        image = await create_image(
            db,
            id=file_id,
            gallery_id=gallery_id,
            filename=file.filename or f"{file_id}{ext}",
            storage_key=original_key,
            thumbnail_key=thumbnail_key,
            medium_key=medium_key,
            file_size=len(data),
            width=width,
            height=height,
            mime_type=mime_type,
            exif_data=exif,
            sort_order=sort_order,
        )
        created_images.append(image)

    # Auto-set cover image to last uploaded image
    if created_images:
        await db.refresh(gallery)
        gallery.cover_image_id = created_images[-1].id
        await db.commit()

    return UploadResponse(uploaded=created_images, skipped=skipped)


@router.get("/images/{image_id}", response_model=ImageResponse)
async def get_image_route(
    image_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


@router.get("/images/{image_id}/file")
async def serve_image_file(
    image_id: uuid.UUID,
    size: str = "original",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
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
    return Response(content=data, media_type=media_type)


@router.get("/images/{image_id}/thumbnail")
async def serve_thumbnail(
    image_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    data = await _get_storage().get(image.thumbnail_key)
    return Response(content=data, media_type="image/webp")


@router.patch("/images/{image_id}", response_model=ImageResponse)
async def update_copies(
    image_id: uuid.UUID,
    body: ImageUpdateCopies,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    if body.num_copies < 0 or body.num_copies > 999:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="num_copies must be 0-999")

    image = await update_image_copies(db, image, body.num_copies)
    return image


@router.patch("/galleries/{gallery_id}/images/batch", response_model=dict)
async def batch_update(
    gallery_id: uuid.UUID,
    body: BatchUpdateCopies,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    if body.num_copies < 0 or body.num_copies > 999:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="num_copies must be 0-999")

    count = await batch_update_copies(db, body.image_ids, gallery_id, body.num_copies)
    return {"updated": count}


@router.post("/galleries/{gallery_id}/reorder")
async def reorder_images(
    gallery_id: uuid.UUID,
    image_ids: list[uuid.UUID] = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    for i, img_id in enumerate(image_ids):
        image = await get_image(db, img_id)
        if image and image.gallery_id == gallery_id:
            image.sort_order = i
    await db.commit()
    return {"reordered": len(image_ids)}


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image_route(
    image_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Delete files from storage
    await _get_storage().delete(image.storage_key)
    await _get_storage().delete(image.thumbnail_key)
    if image.medium_key:
        await _get_storage().delete(image.medium_key)

    await delete_image(db, image)
