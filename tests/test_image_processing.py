import io
import json

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from app.image_processing import (
    generate_thumbnail,
    generate_medium,
    get_image_dimensions,
    extract_exif,
    _make_json_safe,
)


@pytest.fixture
def jpeg_bytes() -> bytes:
    img = Image.new("RGB", (200, 300), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def large_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (3000, 2000), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_generate_thumbnail(jpeg_bytes: bytes):
    thumb = generate_thumbnail(jpeg_bytes, max_size=100)
    img = Image.open(io.BytesIO(thumb))
    assert img.format == "WEBP"
    assert img.width <= 100
    assert img.height <= 100


def test_generate_medium_no_resize_needed(jpeg_bytes: bytes):
    """Image smaller than max_size should preserve dimensions."""
    medium = generate_medium(jpeg_bytes, max_size=1200)
    img = Image.open(io.BytesIO(medium))
    assert img.width == 200
    assert img.height == 300


def test_generate_medium_resizes_large(large_jpeg_bytes: bytes):
    medium = generate_medium(large_jpeg_bytes, max_size=1200)
    img = Image.open(io.BytesIO(medium))
    assert img.width <= 1200
    assert img.height <= 1200


def test_get_image_dimensions(jpeg_bytes: bytes):
    w, h = get_image_dimensions(jpeg_bytes)
    assert w == 200
    assert h == 300


def test_extract_exif_no_exif(jpeg_bytes: bytes):
    """Synthetic images have no EXIF — should return None."""
    result = extract_exif(jpeg_bytes)
    assert result is None


def test_extract_exif_invalid_data():
    result = extract_exif(b"not an image")
    assert result is None


def test_make_json_safe_ifd_rational():
    r = IFDRational(72, 1)
    result = _make_json_safe(r)
    assert result == 72
    assert isinstance(result, int)
    json.dumps(result)  # should not raise


def test_make_json_safe_ifd_rational_fraction():
    r = IFDRational(1, 3)
    result = _make_json_safe(r)
    assert isinstance(result, float)
    assert abs(result - 0.333333) < 0.001
    json.dumps(result)  # should not raise


def test_make_json_safe_bytes():
    assert _make_json_safe(b"binary data") is None


def test_make_json_safe_nested():
    data = {"key": IFDRational(72, 1), "list": [IFDRational(1, 2), "text"]}
    safe = _make_json_safe(data)
    # Should be fully JSON serializable
    json.dumps(safe)
    assert safe["key"] == 72
    assert safe["list"][0] == 0.5
    assert safe["list"][1] == "text"
