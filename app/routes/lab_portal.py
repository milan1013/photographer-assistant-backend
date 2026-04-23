"""Lab portal endpoints — magic-link authenticated."""

import io
import zipfile
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_lab
from app.models.lab import Lab
from app.models.print_order import PrintOrder, OrderItem
from app.models.image import Image
from app.models.gallery import Gallery
from app.schemas.order import OrderResponse, OrderStatusUpdate
from app.lab_auth import create_lab_token
from app.email_service import send_lab_magic_link
from sqlalchemy.orm import selectinload

logger = logging.getLogger("fotomil")
router = APIRouter()


class LabLoginRequest(BaseModel):
    email: str


class LabMeResponse(BaseModel):
    id: str
    name: str
    email: str


@router.post("/lab/login")
async def lab_login(body: LabLoginRequest, db: AsyncSession = Depends(get_db)):
    """Send a magic link to the lab's registered email."""
    result = await db.execute(select(Lab).where(Lab.email == body.email.strip(), Lab.is_active == True))
    lab = result.scalar_one_or_none()
    if not lab:
        # Don't reveal whether email exists
        return {"status": "ok"}

    token = create_lab_token(str(lab.id))
    send_lab_magic_link(lab.email, token)
    return {"status": "ok"}


@router.get("/lab/me", response_model=LabMeResponse)
async def lab_me(lab: Lab = Depends(get_current_lab)):
    return LabMeResponse(id=str(lab.id), name=lab.name, email=lab.email)


@router.get("/lab/products")
async def lab_list_products(
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.lab import LabProductResponse
    result = await db.execute(
        select(Lab).where(Lab.id == lab.id).options(selectinload(Lab.products))
    )
    lab_full = result.scalar_one()
    return [LabProductResponse.model_validate(p, from_attributes=True) for p in lab_full.products]


@router.post("/lab/products", status_code=201)
async def lab_add_product(
    body: dict,
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    from app.models.lab import LabProduct
    from app.schemas.lab import LabProductResponse
    from decimal import Decimal
    product = LabProduct(
        lab_id=lab.id,
        name=body.get("name", "").strip()[:255],
        price=Decimal(str(body.get("price", 0))),
        currency=body.get("currency", "RSD"),
        sort_order=int(body.get("sort_order", 0)),
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return LabProductResponse.model_validate(product, from_attributes=True)


@router.patch("/lab/products/{product_id}")
async def lab_update_product(
    product_id: str,
    body: dict,
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    from app.models.lab import LabProduct
    from app.schemas.lab import LabProductResponse
    from decimal import Decimal
    result = await db.execute(
        select(LabProduct).where(LabProduct.id == product_id, LabProduct.lab_id == lab.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if "name" in body and body["name"] is not None:
        product.name = body["name"].strip()[:255]
    if "price" in body and body["price"] is not None:
        product.price = Decimal(str(body["price"]))
    if "sort_order" in body and body["sort_order"] is not None:
        product.sort_order = int(body["sort_order"])
    if "is_active" in body and body["is_active"] is not None:
        product.is_active = bool(body["is_active"])

    await db.commit()
    await db.refresh(product)
    return LabProductResponse.model_validate(product, from_attributes=True)


@router.delete("/lab/products/{product_id}", status_code=204)
async def lab_delete_product(
    product_id: str,
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    from app.models.lab import LabProduct
    result = await db.execute(
        select(LabProduct).where(LabProduct.id == product_id, LabProduct.lab_id == lab.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()


@router.get("/lab/orders", response_model=list[OrderResponse])
async def lab_list_orders(
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.lab_id == lab.id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
        .order_by(PrintOrder.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/lab/orders/{order_id}/status", response_model=OrderResponse)
async def lab_update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.id == order_id, PrintOrder.lab_id == lab.id)
        .options(selectinload(PrintOrder.items), selectinload(PrintOrder.lab))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if body.status not in ("pending", "confirmed", "completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")
    order.status = body.status
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/lab/orders/{order_id}/download")
async def lab_download_order_images(
    order_id: str,
    lab: Lab = Depends(get_current_lab),
    db: AsyncSession = Depends(get_db),
):
    """Download all original images for an order as a ZIP."""
    from app.storage import get_storage

    result = await db.execute(
        select(PrintOrder)
        .where(PrintOrder.id == order_id, PrintOrder.lab_id == lab.id)
        .options(selectinload(PrintOrder.items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    storage = get_storage()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for item in order.items:
            if not item.image_id:
                continue
            img_result = await db.execute(select(Image).where(Image.id == item.image_id))
            image = img_result.scalar_one_or_none()
            if not image:
                continue
            try:
                data = await storage.get(image.storage_key)
                zf.writestr(f"{item.quantity}x_{image.filename}", data)
            except Exception as e:
                logger.warning("Could not include image %s in ZIP: %s", image.id, e)

    buf.seek(0)
    filename = f"order_{order_id[:8]}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
