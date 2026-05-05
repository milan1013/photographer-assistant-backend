import uuid
from datetime import datetime

import bleach
from pydantic import BaseModel, EmailStr, field_validator


def _sanitize(value: str | None, max_len: int = 1000) -> str | None:
    if value is None:
        return None
    cleaned = bleach.clean(value, tags=[], strip=True).strip()
    return cleaned[:max_len] if cleaned else None


class LabApplicationCreate(BaseModel):
    lab_name: str
    lab_email: EmailStr
    lab_address: str | None = None
    lab_phone: str | None = None
    lab_website: str | None = None
    message: str | None = None

    @field_validator("lab_name", mode="before")
    @classmethod
    def sanitize_name(cls, v):
        cleaned = _sanitize(v, 255)
        if not cleaned:
            raise ValueError("Lab name is required")
        return cleaned

    @field_validator("lab_address", mode="before")
    @classmethod
    def sanitize_address(cls, v):
        return _sanitize(v, 500)

    @field_validator("lab_phone", mode="before")
    @classmethod
    def sanitize_phone(cls, v):
        return _sanitize(v, 50)

    @field_validator("lab_website", mode="before")
    @classmethod
    def sanitize_website(cls, v):
        return _sanitize(v, 500)

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, v):
        return _sanitize(v, 2000)


class LabApplicationResponse(BaseModel):
    id: uuid.UUID
    lab_name: str
    lab_email: str
    lab_address: str | None
    lab_phone: str | None
    lab_website: str | None
    message: str | None
    status: str
    rejection_reason: str | None
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    approved_lab_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LabApplicationDecision(BaseModel):
    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def sanitize_reason(cls, v):
        return _sanitize(v, 1000)
