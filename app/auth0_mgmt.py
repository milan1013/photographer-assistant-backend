"""Auth0 Management API utilities."""

import logging
import secrets
import time

import httpx

from app.config import settings

logger = logging.getLogger("fotomil")

_mgmt_token: str | None = None
_mgmt_token_expires: float = 0


async def _get_mgmt_token() -> str:
    """Get a cached Auth0 Management API token via client_credentials grant."""
    global _mgmt_token, _mgmt_token_expires

    if _mgmt_token and time.time() < _mgmt_token_expires - 300:
        return _mgmt_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{settings.auth0_domain}/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": settings.auth0_mgmt_client_id,
                "client_secret": settings.auth0_mgmt_client_secret,
                "audience": f"https://{settings.auth0_domain}/api/v2/",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _mgmt_token = data["access_token"]
        _mgmt_token_expires = time.time() + data.get("expires_in", 86400)
        return _mgmt_token


async def send_password_reset_email(email: str) -> bool:
    """Send a password reset email via Auth0 (public endpoint, no M2M token)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{settings.auth0_domain}/dbconnections/change_password",
            json={
                "client_id": settings.auth0_client_id,
                "email": email,
                "connection": "Username-Password-Authentication",
            },
        )
        return resp.status_code == 200


async def get_user_identities(auth0_sub: str) -> list[dict]:
    """Get user's connected identity providers from Auth0."""
    token = await _get_mgmt_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://{settings.auth0_domain}/api/v2/users/{auth0_sub}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            logger.warning("Failed to fetch Auth0 identities: %s", resp.text)
            return []
        user_data = resp.json()
        return [
            {"provider": i["provider"], "connection": i["connection"]}
            for i in user_data.get("identities", [])
        ]


async def find_user_by_email(email: str) -> dict | None:
    """Find an Auth0 user by email. Returns user dict or None."""
    token = await _get_mgmt_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://{settings.auth0_domain}/api/v2/users-by-email",
            headers={"Authorization": f"Bearer {token}"},
            params={"email": email.lower()},
        )
        if resp.status_code != 200:
            logger.warning("users-by-email failed: %s", resp.text)
            return None
        users = resp.json()
        return users[0] if users else None


async def create_db_user(email: str, name: str, app_metadata: dict | None = None) -> dict | None:
    """Create an Auth0 db-connection user with a random password.
    Returns user dict on success (including 'user_id'), None on failure.
    The caller should trigger a password reset so the user can set their own password.
    """
    token = await _get_mgmt_token()
    # Generate a random password the user will never use — they reset it via email.
    random_password = secrets.token_urlsafe(32) + "Aa1!"
    payload = {
        "connection": "Username-Password-Authentication",
        "email": email.lower(),
        "name": name,
        "password": random_password,
        "email_verified": False,
        "verify_email": False,
    }
    if app_metadata:
        payload["app_metadata"] = app_metadata
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{settings.auth0_domain}/api/v2/users",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            logger.error("Failed to create Auth0 user %s: %s", email, resp.text)
            return None
        return resp.json()


async def update_user_app_metadata(auth0_sub: str, app_metadata: dict) -> bool:
    """Merge new app_metadata onto an existing Auth0 user."""
    token = await _get_mgmt_token()
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"https://{settings.auth0_domain}/api/v2/users/{auth0_sub}",
            headers={"Authorization": f"Bearer {token}"},
            json={"app_metadata": app_metadata},
        )
        if resp.status_code != 200:
            logger.error("Failed to update app_metadata for %s: %s", auth0_sub, resp.text)
            return False
        return True


async def delete_auth0_user(auth0_sub: str) -> bool:
    """Delete a user from Auth0."""
    token = await _get_mgmt_token()
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"https://{settings.auth0_domain}/api/v2/users/{auth0_sub}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code not in (200, 204):
            logger.error("Failed to delete Auth0 user %s: %s", auth0_sub, resp.text)
            return False
        return True
