import uuid
from decimal import Decimal

from pydantic import BaseModel


class LabProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    currency: str
    sort_order: int
    is_active: bool = True

    model_config = {"from_attributes": True}


class LabResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    phone: str | None
    email: str
    website: str | None
    is_active: bool = True
    products: list[LabProductResponse] = []

    model_config = {"from_attributes": True}


class LabCreate(BaseModel):
    name: str
    email: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None


class LabUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    is_active: bool | None = None


class LabProductCreate(BaseModel):
    name: str
    price: Decimal
    currency: str = "RSD"


class LabProductUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
