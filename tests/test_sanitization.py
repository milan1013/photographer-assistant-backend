import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_gallery_name_xss_stripped(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    resp = await client.post("/api/galleries", json={
        "name": '<script>alert("xss")</script>My Gallery',
        "description": '<img onerror="alert(1)" src=x>Nice photos',
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    # HTML tags stripped, text content preserved (harmless as plain text)
    assert "<script>" not in data["name"]
    assert "</script>" not in data["name"]
    assert "My Gallery" in data["name"]
    assert "<img" not in data["description"]
    assert "onerror" not in data["description"]
    assert "Nice photos" in data["description"]


@pytest.mark.asyncio
async def test_gallery_update_xss_stripped(client: AsyncClient, auth: tuple[dict, dict]):
    _, headers = auth
    create = await client.post("/api/galleries", json={"name": "Clean"}, headers=headers)
    gid = create.json()["id"]

    resp = await client.patch(f"/api/galleries/{gid}", json={
        "name": '<b onmouseover="hack()">Bold</b>',
    }, headers=headers)
    assert resp.status_code == 200
    assert "<b" not in resp.json()["name"]
    assert "Bold" in resp.json()["name"]


@pytest.mark.asyncio
async def test_share_label_xss_stripped(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(f"/api/galleries/{gallery['id']}/shares", json={
        "permission": "view",
        "label": '<script>steal()</script>For Client',
    }, headers=headers)
    assert resp.status_code == 201
    assert "<script>" not in resp.json()["label"]
    assert "For Client" in resp.json()["label"]


@pytest.mark.asyncio
async def test_normal_text_preserved(client: AsyncClient, auth: tuple[dict, dict]):
    """Normal text with special chars should not be mangled."""
    _, headers = auth
    resp = await client.post("/api/galleries", json={
        "name": "Fotografije - Marka & Ane (2026)",
        "description": "Slike sa vencanja, 100+ fotografija",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Fotografije - Marka &amp; Ane (2026)"
    assert resp.json()["description"] == "Slike sa vencanja, 100+ fotografija"
