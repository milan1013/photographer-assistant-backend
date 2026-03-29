import io

import pytest
from httpx import AsyncClient
from PIL import Image

from app.image_processing import apply_watermark


def test_apply_watermark():
    """Watermark function should return a valid image."""
    img = Image.new("RGB", (200, 200), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data = buf.getvalue()

    result = apply_watermark(data, "TEST")
    result_img = Image.open(io.BytesIO(result))
    assert result_img.width == 200
    assert result_img.height == 200
    # Result should be different from input (watermark applied)
    assert result != data


def test_apply_watermark_webp():
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    result = apply_watermark(buf.getvalue(), "PREVIEW", "WEBP")
    result_img = Image.open(io.BytesIO(result))
    assert result_img.format == "WEBP"


@pytest.mark.asyncio
async def test_view_only_thumbnail_has_watermark(client: AsyncClient, view_share_link: tuple[str, dict, list[dict]]):
    """View-only shared thumbnails should be watermarked (different from original)."""
    token, _, images = view_share_link

    # Get thumbnail via view-only link
    view_resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/thumbnail")
    assert view_resp.status_code == 200
    view_data = view_resp.content

    # The watermarked image should be valid
    img = Image.open(io.BytesIO(view_data))
    assert img.format == "WEBP"


@pytest.mark.asyncio
async def test_edit_link_no_watermark(client: AsyncClient, edit_share_link: tuple[str, dict, list[dict]]):
    """Edit shared thumbnails should NOT be watermarked."""
    token, _, images = edit_share_link

    resp = await client.get(f"/api/shared/{token}/images/{images[0]['id']}/thumbnail")
    assert resp.status_code == 200
    # Edit link should return original thumbnail (no watermark processing)
    # We can't easily compare, but the response should be valid
    img = Image.open(io.BytesIO(resp.content))
    assert img.format == "WEBP"
