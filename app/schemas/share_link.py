import uuid
from datetime import datetime

import bleach
from pydantic import BaseModel, field_validator


def _sanitize(value: str | None) -> str | None:
    if value is None:
        return None
    return bleach.clean(value, tags=[], strip=True).strip()


class ShareLinkCreate(BaseModel):
    permission: str  # "view" or "edit"
    label: str | None = None
    expires_at: datetime | None = None

    @field_validator("label", mode="before")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v)


class ShareLinkUpdate(BaseModel):
    is_active: bool | None = None
    label: str | None = None
    expires_at: datetime | None = None

    @field_validator("label", mode="before")
    @classmethod
    def sanitize(cls, v):
        return _sanitize(v)


class ShareLinkResponse(BaseModel):
    id: uuid.UUID
    gallery_id: uuid.UUID
    token: str
    permission: str
    label: str | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedGalleryResponse(BaseModel):
    gallery_name: str
    gallery_description: str | None
    permission: str
    image_count: int
    branding_name: str | None = None
    branding_logo_url: str | None = None
