import uuid
from datetime import datetime

from pydantic import BaseModel


class UpdateProfileRequest(BaseModel):
    branding_name: str | None = None
    branding_logo_url: str | None = None
    phone: str | None = None
    website_url: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    bio: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    branding_name: str | None
    branding_logo_url: str | None
    phone: str | None
    website_url: str | None
    instagram_url: str | None
    facebook_url: str | None
    bio: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
