import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_single_image(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("photo.jpg", test_image_bytes, "image/jpeg"))],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["filename"] == "photo.jpg"
    assert data["skipped"] == []


@pytest.mark.asyncio
async def test_upload_multiple_images(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[
            ("files", ("img1.jpg", test_image_bytes, "image/jpeg")),
            ("files", ("img2.jpg", test_image_bytes, "image/jpeg")),
        ],
    )
    assert resp.status_code == 201
    assert len(resp.json()["uploaded"]) == 2


@pytest.mark.asyncio
async def test_upload_duplicate_skipped(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("dup.jpg", test_image_bytes, "image/jpeg"))],
    )
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("dup.jpg", test_image_bytes, "image/jpeg"))],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["uploaded"]) == 0
    assert "dup.jpg" in data["skipped"]


@pytest.mark.asyncio
async def test_list_images(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("list1.jpg", test_image_bytes, "image/jpeg"))],
    )
    resp = await client.get(f"/api/galleries/{gallery['id']}/images", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_update_copies(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("copies.jpg", test_image_bytes, "image/jpeg"))],
    )
    image_id = upload.json()["uploaded"][0]["id"]

    resp = await client.patch(f"/api/images/{image_id}", json={"num_copies": 5}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["num_copies"] == 5


@pytest.mark.asyncio
async def test_update_copies_invalid_range(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("range.jpg", test_image_bytes, "image/jpeg"))],
    )
    image_id = upload.json()["uploaded"][0]["id"]

    resp = await client.patch(f"/api/images/{image_id}", json={"num_copies": 1000}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_update_copies(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[
            ("files", ("b1.jpg", test_image_bytes, "image/jpeg")),
            ("files", ("b2.jpg", test_image_bytes, "image/jpeg")),
        ],
    )
    ids = [img["id"] for img in upload.json()["uploaded"]]

    resp = await client.patch(
        f"/api/galleries/{gallery['id']}/images/batch",
        json={"image_ids": ids, "num_copies": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2


@pytest.mark.asyncio
async def test_serve_thumbnail(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("thumb.jpg", test_image_bytes, "image/jpeg"))],
    )
    image_id = upload.json()["uploaded"][0]["id"]
    token = headers["Authorization"].replace("Bearer ", "")

    resp = await client.get(f"/api/images/{image_id}/thumbnail?token={token}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/webp"


@pytest.mark.asyncio
async def test_delete_image(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("del.jpg", test_image_bytes, "image/jpeg"))],
    )
    image_id = upload.json()["uploaded"][0]["id"]

    resp = await client.delete(f"/api/images/{image_id}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/api/images/{image_id}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("doc.pdf", b"fake pdf content", "application/pdf"))],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_with_exif(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes_with_exif: bytes):
    """Images with EXIF data (including IFDRational) should upload without 500 error."""
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("exif.jpg", test_image_bytes_with_exif, "image/jpeg"))],
    )
    assert resp.status_code == 201
    data = resp.json()["uploaded"][0]
    assert data["filename"] == "exif.jpg"
    # EXIF should be extracted
    if data["exif_data"]:
        assert "Make" in data["exif_data"] or "Model" in data["exif_data"]


@pytest.mark.asyncio
async def test_auth_via_query_param(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    """Image endpoints should accept auth via ?token= query param (for <img> tags)."""
    gallery, headers = gallery_with_auth
    upload = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("qp.jpg", test_image_bytes, "image/jpeg"))],
    )
    image_id = upload.json()["uploaded"][0]["id"]
    token = headers["Authorization"].replace("Bearer ", "")

    # Query param auth
    resp = await client.get(f"/api/images/{image_id}/thumbnail?token={token}")
    assert resp.status_code == 200

    # No auth at all
    resp2 = await client.get(f"/api/images/{image_id}/thumbnail")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_delete_multiple_images(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    """Gallery owner should be able to delete multiple images."""
    gallery, images, headers = gallery_with_images
    for img in images[:2]:
        resp = await client.delete(f"/api/images/{img['id']}", headers=headers)
        assert resp.status_code == 204

    # Only 1 image should remain
    list_resp = await client.get(f"/api/galleries/{gallery['id']}/images", headers=headers)
    assert list_resp.json()["total"] == 1
