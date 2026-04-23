from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.crud.labs import (
    get_active_labs, get_all_labs, get_lab, create_lab, update_lab, delete_lab,
    create_lab_product, update_lab_product, delete_lab_product, get_lab_product,
)
from app.schemas.lab import (
    LabResponse, LabCreate, LabUpdate,
    LabProductCreate, LabProductUpdate, LabProductResponse,
)

router = APIRouter()


def _check_admin(user: User):
    if settings.admin_emails and user.email not in settings.admin_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("/admin/check")
async def admin_check(current_user: User = Depends(get_current_user)):
    """Returns whether the current user is an admin."""
    is_admin = not settings.admin_emails or current_user.email in settings.admin_emails
    return {"is_admin": is_admin}


# ── Public ────────────────────────────────────────────────────────────

@router.get("/labs", response_model=list[LabResponse])
async def list_labs(db: AsyncSession = Depends(get_db)):
    return await get_active_labs(db)


# ── Admin: Labs ───────────────────────────────────────────────────────

@router.get("/admin/labs", response_model=list[LabResponse])
async def admin_list_labs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    return await get_all_labs(db)


@router.post("/admin/labs", response_model=LabResponse, status_code=201)
async def admin_create_lab(
    body: LabCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    lab = await create_lab(db, name=body.name, email=body.email, address=body.address, phone=body.phone, website=body.website)
    return lab


@router.patch("/admin/labs/{lab_id}", response_model=LabResponse)
async def admin_update_lab(
    lab_id: str,
    body: LabUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    lab = await get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return await update_lab(db, lab, **body.model_dump(exclude_none=True))


@router.delete("/admin/labs/{lab_id}", status_code=204)
async def admin_delete_lab(
    lab_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    lab = await get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    await delete_lab(db, lab)


# ── Admin: Products ───────────────────────────────────────────────────

@router.post("/admin/labs/{lab_id}/products", response_model=LabProductResponse, status_code=201)
async def admin_add_product(
    lab_id: str,
    body: LabProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    lab = await get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return await create_lab_product(db, lab_id=lab_id, name=body.name, price=body.price, currency=body.currency)


@router.patch("/admin/products/{product_id}", response_model=LabProductResponse)
async def admin_update_product(
    product_id: str,
    body: LabProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    product = await get_lab_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return await update_lab_product(db, product, **body.model_dump(exclude_none=True))


@router.delete("/admin/products/{product_id}", status_code=204)
async def admin_delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    product = await get_lab_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await delete_lab_product(db, product)
