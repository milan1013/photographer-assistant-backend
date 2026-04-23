import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_auth0_token
from app.database import get_db
from app.models.user import User
from app.models.share_link import ShareLink

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try Bearer header first, then query param
    jwt_token = None
    if credentials:
        jwt_token = credentials.credentials
    elif token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_auth0_token(jwt_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    auth0_sub = payload.get("sub")
    if not auth0_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Find user by Auth0 sub, or auto-create on first login
    result = await db.execute(select(User).where(User.auth0_sub == auth0_sub))
    user = result.scalar_one_or_none()

    # Extract email/name from token claims (Auth0 action adds these)
    token_email = (
        payload.get("email")
        or payload.get("https://fotomil.xyz/email")
        or ""
    )
    token_name = (
        payload.get("name")
        or payload.get("https://fotomil.xyz/name")
        or ""
    )

    if user is None:
        # Auto-create user on first login
        user = User(
            auth0_sub=auth0_sub,
            email=token_email or f"{auth0_sub}@auth0",
            full_name=token_name or (token_email.split("@")[0] if token_email else "User"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Sync email/name from Auth0 token if stored data is placeholder
        dirty = False
        if token_email and user.email != token_email:
            user.email = token_email
            dirty = True
        if token_name and user.full_name != token_name:
            user.full_name = token_name
            dirty = True
        if dirty:
            await db.commit()
            await db.refresh(user)

    return user


async def get_current_lab(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a lab via Bearer token from magic link, or query param."""
    from app.lab_auth import decode_lab_token
    from app.models.lab import Lab

    jwt_token = credentials.credentials if credentials else token
    if not jwt_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    lab_id = decode_lab_token(jwt_token)
    if not lab_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired lab token")

    result = await db.execute(select(Lab).where(Lab.id == lab_id))
    lab = result.scalar_one_or_none()
    if not lab or not lab.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Lab not found or inactive")
    return lab


async def get_active_share_link(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> ShareLink:
    result = await db.execute(select(ShareLink).where(ShareLink.token == token, ShareLink.is_active == True))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or inactive")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share link has expired")
    return link
