"""Magic-link JWT authentication for photo labs (no password)."""

from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.config import settings


def create_lab_token(lab_id: str, expires_hours: int | None = None) -> str:
    """Create a signed JWT for a lab session."""
    hours = expires_hours if expires_hours is not None else settings.lab_token_expire_hours
    payload = {
        "sub": str(lab_id),
        "type": "lab",
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_lab_token(token: str) -> str | None:
    """Decode a lab JWT. Returns lab_id on success, None on failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        if payload.get("type") != "lab":
            return None
        return payload.get("sub")
    except JWTError:
        return None
