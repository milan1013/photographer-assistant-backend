import uuid
from datetime import datetime

from pydantic import BaseModel


class ImageResponse(BaseModel):
    id: uuid.UUID
    gallery_id: uuid.UUID
    filename: str
    file_size: int | None
    width: int | None
    height: int | None
    mime_type: str | None
    exif_data: dict | None
    sort_order: int
    num_copies: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImageUpdateCopies(BaseModel):
    num_copies: int


class BatchUpdateCopies(BaseModel):
    image_ids: list[uuid.UUID]
    num_copies: int


class ImageListResponse(BaseModel):
    images: list[ImageResponse]
    total: int


class UploadResponse(BaseModel):
    uploaded: list[ImageResponse]
    skipped: list[str]
