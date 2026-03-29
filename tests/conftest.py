import io
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from PIL import Image

from app.config import settings
from app.database import Base, get_db
from app.main import app

TEST_DB_URL = settings.database_url.replace("/photographer_assistant", "/photographer_assistant_test")

# One-time DB creation (sync, runs before any async tests)
_db_created = False


def _ensure_test_db():
    global _db_created
    if _db_created:
        return
    import psycopg2
    sync_admin = settings.database_url.replace("+asyncpg", "").replace("/photographer_assistant", "/postgres")
    # parse manually for psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5433, user="postgres", password="postgres", dbname="postgres"
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='photographer_assistant_test'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE photographer_assistant_test")
    cur.close()
    conn.close()
    _db_created = True


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide async test client with a fresh DB engine per test."""
    _ensure_test_db()

    # Disable rate limiting for tests
    from app.rate_limit import limiter
    limiter.enabled = False

    engine = create_async_engine(TEST_DB_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

    # Clean up tables
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE users, galleries, images, share_links, refresh_tokens CASCADE"
        ))
    await engine.dispose()


async def create_user_and_token(client: AsyncClient, email: str | None = None) -> tuple[dict, str]:
    """Helper: register a user via API, return (user_data, access_token)."""
    email = email or f"test-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/auth/register", json={
        "email": email,
        "password": "testpassword",
        "full_name": "Test User",
    })
    token = resp.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    return me.json(), token


@pytest_asyncio.fixture
async def auth(client: AsyncClient) -> tuple[dict, dict]:
    """Create a user and return (user_data, auth_headers)."""
    user, token = await create_user_and_token(client)
    return user, {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def gallery_with_auth(client: AsyncClient, auth: tuple[dict, dict]) -> tuple[dict, dict]:
    """Create a gallery and return (gallery_data, auth_headers)."""
    _, headers = auth
    resp = await client.post("/api/galleries", json={
        "name": "Test Gallery",
        "description": "For testing",
    }, headers=headers)
    return resp.json(), headers


@pytest_asyncio.fixture
async def gallery_with_images(client: AsyncClient, gallery_with_auth: tuple[dict, dict], test_image_bytes: bytes) -> tuple[dict, list[dict], dict]:
    """Create a gallery with 3 images. Returns (gallery, images, auth_headers)."""
    gallery, headers = gallery_with_auth
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/images",
        headers=headers,
        files=[
            ("files", ("img1.jpg", test_image_bytes, "image/jpeg")),
            ("files", ("img2.jpg", test_image_bytes, "image/jpeg")),
            ("files", ("img3.jpg", test_image_bytes, "image/jpeg")),
        ],
    )
    images = resp.json()["uploaded"]
    return gallery, images, headers


@pytest_asyncio.fixture
async def edit_share_link(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]) -> tuple[str, dict, list[dict]]:
    """Create an edit share link. Returns (token, gallery, images)."""
    gallery, images, headers = gallery_with_images
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "edit", "label": "Test Edit Link"},
        headers=headers,
    )
    return resp.json()["token"], gallery, images


@pytest_asyncio.fixture
async def view_share_link(client: AsyncClient, gallery_with_images: tuple[dict, list[dict], dict]) -> tuple[str, dict, list[dict]]:
    """Create a view-only share link. Returns (token, gallery, images)."""
    gallery, images, headers = gallery_with_images
    resp = await client.post(
        f"/api/galleries/{gallery['id']}/shares",
        json={"permission": "view", "label": "Test View Link"},
        headers=headers,
    )
    return resp.json()["token"], gallery, images


@pytest.fixture
def test_image_bytes() -> bytes:
    """Generate a minimal valid JPEG image."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def test_image_bytes_with_exif() -> bytes:
    """Generate a JPEG with EXIF data containing IFDRational values."""
    from PIL.ExifTags import Base as ExifBase
    img = Image.new("RGB", (100, 100), color="blue")
    from PIL import Image as PILImage
    exif = img.getexif()
    exif[ExifBase.Make] = "TestCamera"
    exif[ExifBase.Model] = "TestModel"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()
