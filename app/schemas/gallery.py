import uuid
from datetime import datetime

import bleach
from pydantic import BaseModel, field_validator


def _sanitize(value: str | None) -> str | None:
    if value is None:
        return None
    return bleach.clean(value, tags=[], strip=True).strip()


class GalleryCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v)


class GalleryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_image_id: uuid.UUID | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v)


class GalleryResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    cover_image_id: uuid.UUID | None
    image_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GalleryListResponse(BaseModel):
    galleries: list[GalleryResponse]
