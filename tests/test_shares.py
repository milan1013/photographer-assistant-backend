import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_create_view_share_link(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view", "label": "For client"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["permission"] == "view"
    assert data["label"] == "For client"
    assert data["is_active"] is True
    assert len(data["token"]) > 30


@pytest.mark.asyncio
async def test_create_edit_share_link(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "edit"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["permission"] == "edit"


@pytest.mark.asyncio
async def test_create_share_invalid_permission(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "admin"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_shares(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    await client.post(f"/api/galleries/{gallery['id']}/shares", json={"permission": "view"}, headers=headers)
    await client.post(f"/api/galleries/{gallery['id']}/shares", json={"permission": "edit"}, headers=headers)

    resp = await client.get(f"/api/galleries/{gallery['id']}/shares", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_deactivate_share_link(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    create = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view"},
        headers=headers,
    )
    share_id = create.json()["id"]

    resp = await client.patch(f"/api/shares/{share_id}", json={"is_active": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_share_link(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    create = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view"},
        headers=headers,
    )
    share_id = create.json()["id"]

    resp = await client.delete(f"/api/shares/{share_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_share_link_ownership(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    """Other user cannot manage share links of another user's gallery."""
    gallery, headers = gallery_with_auth
    create = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view"},
        headers=headers,
    )
    share_id = create.json()["id"]

    _, other_token = await create_user_and_token(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = await client.get(f"/api/galleries/{gallery['id']}/shares", headers=other_headers)
    assert resp.status_code == 404

    resp2 = await client.delete(f"/api/shares/{share_id}", headers=other_headers)
    assert resp2.status_code == 404
