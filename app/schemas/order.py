import uuid
from datetime import datetime
from decimal import Decimal

import bleach
from pydantic import BaseModel, field_validator


class OrderItemCreate(BaseModel):
    image_id: uuid.UUID
    quantity: int
    product_id: uuid.UUID


class ClientInfo(BaseModel):
    name: str
    email: str
    phone: str | None = None

    @field_validator("name", "email", mode="before")
    @classmethod
    def sanitize(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True).strip()


class OrderCreate(BaseModel):
    lab_id: uuid.UUID
    items: list[OrderItemCreate]
    client_info: ClientInfo | None = None
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def sanitize_note(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True).strip()[:500]


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    image_id: uuid.UUID | None
    image_filename: str
    quantity: int
    product_name: str
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderLabInfo(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    gallery_id: uuid.UUID
    lab: OrderLabInfo
    status: str
    total_price: Decimal
    currency: str
    client_name: str | None
    client_email: str | None
    client_phone: str | None
    ordered_by_user_id: uuid.UUID | None
    note: str | None
    items: list[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str
