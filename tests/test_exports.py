import csv
import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    gallery, images, headers = gallery_with_images
    # Set some copies first
    await client.patch(f"/api/images/{images[0]['id']}", json={"num_copies": 3}, headers=headers)
    await client.patch(f"/api/images/{images[1]['id']}", json={"num_copies": 5}, headers=headers)

    token = headers["Authorization"].replace("Bearer ", "")
    resp = await client.get(f"/api/galleries/{gallery['id']}/export/csv?token={token}")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]

    # Parse CSV
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert rows[0] == ["filename", "copies"]
    assert len(rows) == 4  # header + 3 images


@pytest.mark.asyncio
async def test_export_csv_format_matches_desktop(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]):
    """CSV format should match the desktop app: filename,copies."""
    gallery, images, headers = gallery_with_images
    token = headers["Authorization"].replace("Bearer ", "")
    resp = await client.get(f"/api/galleries/{gallery['id']}/export/csv?token={token}")

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    # Every row should have exactly 2 columns
    for row in rows:
        assert len(row) == 2
    # Copies column should be numeric strings
    for row in rows[1:]:
        assert row[1].isdigit()


@pytest.mark.asyncio
async def test_shared_export_csv(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    token, _, images = edit_share_link
    resp = await client.get(f"/api/shared/{token}/export/csv")
    assert resp.status_code == 200
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 4  # header + 3 images


@pytest.mark.asyncio
async def test_export_csv_nonascii_gallery_name(client: AsyncClient, auth: tuple[dict, dict], test_image_bytes: bytes):
    """Gallery names with non-ASCII chars should not crash CSV export."""
    _, headers = auth
    resp = await client.post("/api/galleries", json={"name": "Galerija šđčćž"}, headers=headers)
    gallery = resp.json()
    await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[("files", ("img.jpg", test_image_bytes, "image/jpeg"))],
    )
    token = headers["Authorization"].replace("Bearer ", "")
    resp2 = await client.get(f"/api/galleries/{gallery['id']}/export/csv?token={token}")
    assert resp2.status_code == 200
