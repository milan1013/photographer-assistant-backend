import pytest
from unittest.mock import patch
from httpx import AsyncClient

from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_max_galleries_limit(client: AsyncClient):
    """User should not be able to create more galleries than the limit."""
    user, token = await create_user_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Patch limit to 3 for testing
    with patch("app.routes.galleries.settings") as mock_settings:
        mock_settings.max_galleries_per_user = 3

        for i in range(3):
            resp = await client.post("/api/galleries", json={"name": f"Gallery {i}"}, headers=headers)
            assert resp.status_code == 201

        # 4th should fail
        resp = await client.post("/api/galleries", json={"name": "Gallery overflow"}, headers=headers)
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_max_images_limit(client: AsyncClient, test_image_bytes: bytes):
    """User should not be able to upload more images than the limit."""
    user, token = await create_user_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/galleries", json={"name": "Limited Gallery"}, headers=headers)
    gallery_id = resp.json()["id"]

    with patch("app.routes.images.settings") as mock_settings:
        mock_settings.max_images_per_gallery = 2
        mock_settings.max_upload_size_mb = 20
        mock_settings.thumbnail_max_size = 300
        mock_settings.medium_max_size = 1200

        # Upload 2 images
        resp = await client.post(
            f"/api/galleries/{gallery_id}/images",
            headers=headers,
            files=[
                ("files", ("img1.jpg", test_image_bytes, "image/jpeg")),
                ("files", ("img2.jpg", test_image_bytes, "image/jpeg")),
            ],
        )
        assert resp.status_code == 201

        # 3rd should fail
        resp = await client.post(
            f"/api/galleries/{gallery_id}/images",
            headers=headers,
            files=[("files", ("img3.jpg", test_image_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_default_limits_are_generous(client: AsyncClient):
    """Default limits should allow normal usage (50 galleries, 500 images)."""
    from app.config import settings
    assert settings.max_galleries_per_user >= 50
    assert settings.max_images_per_gallery >= 500
