import zipfile
import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_download_single_image(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    _, images, headers = gallery_with_images
    token = headers["Authorization"].replace("Bearer ", "")
    resp = await client.get(f"/api/images/{images[0]['id']}/download?token={token}")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_download_zip_all(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    gallery, images, headers = gallery_with_images
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/download/zip",
        json={"image_ids": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    # Verify ZIP contents
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 3


@pytest.mark.asyncio
async def test_download_zip_selected(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    gallery, images, headers = gallery_with_images
    selected = [images[0]["id"], images[1]["id"]]
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/download/zip",
        json={"image_ids": selected},
        headers=headers,
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 2


@pytest.mark.asyncio
async def test_download_zip_empty(client: AsyncClient, gallery_with_auth: tuple[dict, dict]):
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/download/zip",
        json={"image_ids": None},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_shared_download_single(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/download")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_shared_download_zip(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.post(
        f"/api/shared/{token}/download/zip",
        json={"image_ids": None},
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 3


@pytest.mark.asyncio
async def test_shared_download_zip_selected(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.post(
        f"/api/shared/{token}/download/zip",
        json={"image_ids": [images[0]["id"]]},
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 1


@pytest.mark.asyncio
async def test_view_only_can_download(client: AsyncClient, view_share_link: tuple[str, dict, list[dict]]):
    """View-only links should still allow downloads."""
    token, _, images = view_share_link
    resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/download")
    assert resp.status_code == 200

    resp2 = await client.post(f"/api/shared/{token}/download/zip", json={"image_ids": None})
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_download_nonascii_filename(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes):
    """Filenames with non-ASCII chars should not cause 500 (was a bug with Content-Disposition)."""
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("slika_šđčćž.jpg", test_image_bytes, "image/jpeg"))],
    )
    assert resp.status_code == 201
    image_id = resp.json()["uploaded"][0]["id"]
    token = headers["Authorization"].replace("Bearer ", "")

    resp2 = await client.get(f"/api/images/{image_id}/download?token={token}")
    assert resp2.status_code == 200
    assert "attachment" in resp2.headers["content-disposition"]
