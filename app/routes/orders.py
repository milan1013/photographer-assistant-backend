import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_active_share_link
from app.models.user import User
from app.models.gallery import Gallery
from app.models.image import Image
from app.models.share_link import ShareLink
from app.crud.labs import get_lab
from app.crud.orders import create_order, get_orders_by_gallery, get_orders_by_owner, get_order, update_order_status
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.email_service import send_order_notification_to_lab, send_order_notification_to_photographer

logger = logging.getLogger("fotomil")
router = APIRouter()


async def _build_order(
    db: AsyncSession,
    body: OrderCreate,
    gallery: Gallery,
    share_link_id=None,
    ordered_by_user_id=None,
    client_name=None,
    client_email=None,
    client_phone=None,
):
    """Validate and create an order. Shared logic for both client and photographer flows."""
    lab = await get_lab(db, body.lab_id)
    if not lab or not lab.is_active:
        raise HTTPException(status_code=400, detail="Lab not found or inactive")

    if not body.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    # Build product lookup for this lab
    product_map = {p.id: p for p in lab.products}

    # Validate items and build order item data
    items_data = []
    total = Decimal("0")
    for item in body.items:
        # Validate image belongs to gallery
        img_result = await db.execute(
            select(Image).where(Image.id == item.image_id, Image.gallery_id == gallery.id)
        )
        image = img_result.scalar_one_or_none()
        if not image:
            raise HTTPException(status_code=400, detail=f"Image {item.image_id} not found in gallery")

        product = product_map.get(item.product_id)
        if not product:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found for this lab")

        if item.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")

        line_total = product.price * item.quantity
        total += line_total

        items_data.append({
            "image_id": image.id,
            "image_filename": image.filename,
            "quantity": item.quantity,
            "product_id": product.id,
            "product_name": product.name,
            "unit_price": product.price,
            "line_total": line_total,
        })

    order = await create_order(
        db=db,
        gallery_id=gallery.id,
        lab_id=lab.id,
        total_price=total,
        currency=lab.products[0].currency if lab.products else "RSD",
        items_data=items_data,
        share_link_id=share_link_id,
        ordered_by_user_id=ordered_by_user_id,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        note=body.note,
    )

    # Generate a magic-link token for the lab so they can access the portal from email
    from app.lab_auth import create_lab_token
    from app.config import settings
    lab_token = create_lab_token(str(lab.id))
    base_url = settings.app_url.rstrip("/")

    # Send email notifications (fire and forget)
    email_data = {
        "gallery_name": gallery.name,
        "gallery_id": str(gallery.id),
        "lab_name": lab.name,
        "client_name": client_name or "Fotograf",
        "client_email": client_email or "",
        "client_phone": client_phone or "",
        "note": body.note,
        "total_price": str(total),
        "currency": lab.products[0].currency if lab.products else "RSD",
        "item_count": len(items_data),
        "lab_portal_url": f"{base_url}/lab/login?token={lab_token}",
        "items": [
            {
                "filename": i["image_filename"],
                "product": i["product_name"],
                "quantity": i["quantity"],
                "unit_price": str(i["unit_price"]),
                "line_total": str(i["line_total"]),
            }
            for i in items_data
        ],
    }
    send_order_notification_to_lab(lab.email, email_data)

    # Notify gallery owner
    owner_result = await db.execute(select(User).where(User.id == gallery.owner_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        send_order_notification_to_photographer(owner.email, email_data)

    return order


# ── Client creates order via share link ──────────────────────────────
@router.post("/shared/{token}/orders", response_model=OrderResponse, status_code=201)
async def client_create_order(
    token: str,
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    if link.permission != "edit":
        raise HTTPException(status_code=403, detail="Edit permission required to place orders")

    gallery_result = await db.execute(select(Gallery).where(Gallery.id == link.gallery_id))
    gallery = gallery_result.scalar_one_or_none()
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    if not body.client_info:
        raise HTTPException(status_code=400, detail="Client info required for shared orders")

    order = await _build_order(
        db, body, gallery,
        share_link_id=link.id,
        client_name=body.client_info.name,
        client_email=body.client_info.email,
        client_phone=body.client_info.phone,
    )
    return order


# ── Photographer creates order ───────────────────────────────────────
@router.post("/galleries/{gallery_id}/orders", response_model=OrderResponse, status_code=201)
async def photographer_create_order(
    gallery_id: str,
    body: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery_result = await db.execute(
        select(Gallery).where(Gallery.id == gallery_id, Gallery.owner_id == current_user.id)
    )
    gallery = gallery_result.scalar_one_or_none()
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    order = await _build_order(
        db, body, gallery,
        ordered_by_user_id=current_user.id,
        client_name=body.client_info.name if body.client_info else None,
        client_email=body.client_info.email if body.client_info else None,
        client_phone=body.client_info.phone if body.client_info else None,
    )
    return order


# ── Photographer views orders for a gallery ──────────────────────────
@router.get("/galleries/{gallery_id}/orders", response_model=list[OrderResponse])
async def list_gallery_orders(
    gallery_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery_result = await db.execute(
        select(Gallery).where(Gallery.id == gallery_id, Gallery.owner_id == current_user.id)
    )
    if not gallery_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Gallery not found")

    return await get_orders_by_gallery(db, gallery_id)


# ── Photographer views all their orders ──────────────────────────────
@router.get("/orders", response_model=list[OrderResponse])
async def list_all_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_orders_by_owner(db, current_user.id)


# ── Photographer updates order status ────────────────────────────────
@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_status(
    order_id: str,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify ownership
    gallery_result = await db.execute(
        select(Gallery).where(Gallery.id == order.gallery_id, Gallery.owner_id == current_user.id)
    )
    if not gallery_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not your order")

    if body.status not in ("pending", "confirmed", "completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")

    return await update_order_status(db, order, body.status)
