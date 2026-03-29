import pytest
from httpx import AsyncClient

from app.auth import create_password_reset_token, decode_password_reset_token


def test_create_and_decode_reset_token():
    token = create_password_reset_token("test@example.com")
    email = decode_password_reset_token(token)
    assert email == "test@example.com"


def test_decode_invalid_token():
    assert decode_password_reset_token("invalid.token.here") is None


def test_decode_access_token_as_reset():
    """Access tokens should not work as reset tokens."""
    from app.auth import create_access_token
    token = create_access_token("some-user-id")
    assert decode_password_reset_token(token) is None


@pytest.mark.asyncio
async def test_forgot_password_existing_email(client: AsyncClient):
    # Register a user
    await client.post("/api/auth/register", json={
        "email": "reset@example.com", "password": "oldpass123", "full_name": "Reset User",
    })

    resp = await client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower() or "sent" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email(client: AsyncClient):
    """Should return 200 even for nonexistent emails (prevent enumeration)."""
    resp = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_flow(client: AsyncClient):
    # Register
    await client.post("/api/auth/register", json={
        "email": "flow@example.com", "password": "oldpass123", "full_name": "Flow User",
    })

    # Create reset token directly (simulating email link)
    token = create_password_reset_token("flow@example.com")

    # Reset password
    resp = await client.post("/api/auth/reset-password", json={
        "token": token, "new_password": "newpass456",
    })
    assert resp.status_code == 200

    # Login with new password
    login_resp = await client.post("/api/auth/login", json={
        "email": "flow@example.com", "password": "newpass456",
    })
    assert login_resp.status_code == 200

    # Old password should not work
    old_resp = await client.post("/api/auth/login", json={
        "email": "flow@example.com", "password": "oldpass123",
    })
    assert old_resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    resp = await client.post("/api/auth/reset-password", json={
        "token": "invalid.token", "new_password": "newpass123",
    })
    assert resp.status_code == 400
