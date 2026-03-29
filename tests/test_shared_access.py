import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shared_gallery_info(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, gallery, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gallery_name"] == gallery["name"]
    assert data["permission"] == "edit"
    assert data["image_count"] == 3


@pytest.mark.asyncio
async def test_shared_list_images(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/images")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_shared_thumbnail(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/thumbnail")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/webp"


@pytest.mark.asyncio
async def test_shared_image_file(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/file?size=medium")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_shared_edit_copies(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.patch(
        f"/api/shared/{token}/images/{images[0]['id']}",
        json={"num_copies": 7},
    )
    assert resp.status_code == 200
    assert resp.json()["num_copies"] == 7


@pytest.mark.asyncio
async def test_shared_batch_update_copies(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    ids = [img["id"] for img in images]
    resp = await client.patch(
        f"/api/shared/{token}/images/batch",
        json={"image_ids": ids, "num_copies": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3

    # Verify all updated
    list_resp = await client.get(f"/api/shared/{token}/images")
    for img in list_resp.json()["images"]:
        assert img["num_copies"] == 5


@pytest.mark.asyncio
async def test_view_only_cannot_edit_copies(client: AsyncClient, view_share_link: tuple[str, dict, list[dict]]):
    token, _, images = view_share_link
    resp = await client.patch(
        f"/api/shared/{token}/images/{images[0]['id']}",
        json={"num_copies": 3},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_view_only_cannot_batch_update(client: AsyncClient, view_share_link: tuple[str, dict, list[dict]]):
    token, _, images = view_share_link
    resp = await client.patch(
        f"/api/shared/{token}/images/batch",
        json={"image_ids": [images[0]["id"]], "num_copies": 3},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_share_token(client: AsyncClient):
    resp = await client.get("/api/shared/invalid-token-here/gallery")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivated_share_link(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    gallery, images, headers = gallery_with_images
    create = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view"},
        headers=headers,
    )
    share = create.json()
    # Deactivate
    await client.patch(f"/api/shares/{share['id']}", json={"is_active": False}, headers=headers)

    resp = await client.get(f"/api/shared/{share['token']}/gallery")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shared_image_wrong_gallery(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    """Shared link should not serve images from other galleries."""
    token, _, _ = edit_share_link
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/shared/{token}/images/{fake_id}/thumbnail")
    assert resp.status_code == 404
