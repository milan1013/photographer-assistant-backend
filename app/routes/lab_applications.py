"""Public lab partnership application + admin review endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.lab_auth import create_lab_token
from app.models.user import User
from app.rate_limit import limiter
from app.crud.lab_applications import (
    create_application, get_application, list_applications,
    get_pending_application_by_email, get_lab_by_email, update_application,
)
from app.crud.labs import create_lab
from app.schemas.lab_application import (
    LabApplicationCreate, LabApplicationResponse, LabApplicationDecision,
)
from app.email_service import (
    send_application_received_to_lab, send_application_to_admin,
    send_application_approved, send_application_rejected,
)

logger = logging.getLogger("fotomil")
router = APIRouter()


def _check_admin(user: User):
    if settings.admin_emails and user.email not in settings.admin_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


# ── Public ────────────────────────────────────────────────────────────

@router.post("/labs/apply", status_code=201)
@limiter.limit("5/hour")
async def submit_application(
    request: Request,
    body: LabApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — labs apply to become FotoMil partners."""
    email = body.lab_email.lower().strip()

    # Reject duplicate pending applications
    existing_pending = await get_pending_application_by_email(db, email)
    if existing_pending:
        raise HTTPException(status_code=409, detail="An application from this email is already under review.")

    # Reject if already a partner
    existing_lab = await get_lab_by_email(db, email)
    if existing_lab:
        raise HTTPException(status_code=409, detail="A lab with this email is already a FotoMil partner.")

    app = await create_application(
        db,
        lab_name=body.lab_name,
        lab_email=email,
        lab_address=body.lab_address,
        lab_phone=body.lab_phone,
        lab_website=body.lab_website,
        message=body.message,
    )

    # Best-effort emails
    try:
        send_application_received_to_lab(email, app.lab_name)
    except Exception as e:
        logger.warning("Failed to send applicant receipt: %s", e)

    application_data = {
        "lab_name": app.lab_name,
        "lab_email": app.lab_email,
        "lab_phone": app.lab_phone,
        "lab_address": app.lab_address,
        "lab_website": app.lab_website,
        "message": app.message,
    }
    for admin_email in settings.admin_emails:
        try:
            send_application_to_admin(admin_email, application_data)
        except Exception as e:
            logger.warning("Failed to send admin alert to %s: %s", admin_email, e)

    return {"status": "ok"}


# ── Admin ─────────────────────────────────────────────────────────────

@router.get("/admin/lab-applications", response_model=list[LabApplicationResponse])
async def admin_list_applications(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    return await list_applications(db, status=status)


@router.post("/admin/lab-applications/{app_id}/approve", response_model=LabApplicationResponse)
async def admin_approve_application(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    app = await get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != "pending":
        raise HTTPException(status_code=400, detail=f"Application is already {app.status}")

    # Create the actual lab
    lab = await create_lab(
        db,
        name=app.lab_name,
        email=app.lab_email,
        address=app.lab_address,
        phone=app.lab_phone,
        website=app.lab_website,
    )

    updated = await update_application(
        db, app,
        status="approved",
        reviewed_by_user_id=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
        approved_lab_id=lab.id,
    )

    # Send approval email with magic-link
    token = create_lab_token(str(lab.id))
    base_url = settings.app_url.rstrip("/")
    magic_link = f"{base_url}/lab/login?token={token}"
    try:
        send_application_approved(lab.email, lab.name, magic_link)
    except Exception as e:
        logger.warning("Failed to send approval email: %s", e)

    return updated


@router.post("/admin/lab-applications/{app_id}/reject", response_model=LabApplicationResponse)
async def admin_reject_application(
    app_id: str,
    body: LabApplicationDecision,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_admin(current_user)
    app = await get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != "pending":
        raise HTTPException(status_code=400, detail=f"Application is already {app.status}")

    updated = await update_application(
        db, app,
        status="rejected",
        rejection_reason=body.reason,
        reviewed_by_user_id=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
    )

    try:
        send_application_rejected(app.lab_email, app.lab_name, body.reason)
    except Exception as e:
        logger.warning("Failed to send rejection email: %s", e)

    return updated
