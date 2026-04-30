import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab_application import LabApplication
from app.models.lab import Lab


async def create_application(db: AsyncSession, **kwargs) -> LabApplication:
    app = LabApplication(**kwargs)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def get_application(db: AsyncSession, app_id: uuid.UUID) -> LabApplication | None:
    result = await db.execute(select(LabApplication).where(LabApplication.id == app_id))
    return result.scalar_one_or_none()


async def list_applications(db: AsyncSession, status: str | None = None) -> list[LabApplication]:
    stmt = select(LabApplication)
    if status:
        stmt = stmt.where(LabApplication.status == status)
    stmt = stmt.order_by(LabApplication.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_pending_application_by_email(db: AsyncSession, email: str) -> LabApplication | None:
    result = await db.execute(
        select(LabApplication).where(
            LabApplication.lab_email == email,
            LabApplication.status == "pending",
        )
    )
    return result.scalar_one_or_none()


async def get_lab_by_email(db: AsyncSession, email: str) -> Lab | None:
    result = await db.execute(select(Lab).where(Lab.email == email))
    return result.scalar_one_or_none()


async def update_application(db: AsyncSession, app: LabApplication, **kwargs) -> LabApplication:
    for key, value in kwargs.items():
        setattr(app, key, value)
    await db.commit()
    await db.refresh(app)
    return app
