import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_create_gallery(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    resp = await client.post("/api/galleries", json={
        "name": "My Gallery", "description": "Photos from trip",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Gallery"
    assert data["description"] == "Photos from trip"
    assert data["image_count"] == 0


@pytest.mark.asyncio
async def test_list_galleries(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    await client.post("/api/galleries", json={"name": "G1"}, headers=headers)
    await client.post("/api/galleries", json={"name": "G2"}, headers=headers)

    resp = await client.get("/api/galleries", headers=headers)
    assert resp.status_code == 200
    galleries = resp.json()["galleries"]
    assert len(galleries) == 2


@pytest.mark.asyncio
async def test_get_gallery(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.get(f"/api/galleries/{gallery['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Gallery"


@pytest.mark.asyncio
async def test_update_gallery(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.patch(f"/api/galleries/{gallery['id']}", json={
        "name": "Updated Name",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_gallery(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    create = await client.post("/api/galleries", json={"name": "To Delete"}, headers=headers)
    gallery_id = create.json()["id"]

    resp = await client.delete(f"/api/galleries/{gallery_id}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/api/galleries/{gallery_id}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_gallery_not_found(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/galleries/{fake_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gallery_ownership_isolation(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    """User B should not see User A's gallery."""
    gallery, _ = gallery_with_auth

    # Create second user
    _, other_token = await create_user_and_token(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = await client.get(f"/api/galleries/{gallery['id']}", headers=other_headers)
    assert resp.status_code == 404

    resp2 = await client.get("/api/galleries", headers=other_headers)
    gallery_ids = [g["id"] for g in resp2.json()["galleries"]]
    assert gallery["id"] not in gallery_ids
