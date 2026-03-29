import io

from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}


def _open_and_fix_orientation(image_data: bytes) -> Image.Image:
    """Open image and apply EXIF orientation to fix rotated photos."""
    img = Image.open(io.BytesIO(image_data))
    img = ImageOps.exif_transpose(img)
    return img


def generate_thumbnail(image_data: bytes, max_size: int = 300) -> bytes:
    img = _open_and_fix_orientation(image_data)
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def generate_medium(image_data: bytes, max_size: int = 1200) -> bytes:
    img = _open_and_fix_orientation(image_data)
    if img.width <= max_size and img.height <= max_size:
        # Still need to save with corrected orientation
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def get_image_dimensions(image_data: bytes) -> tuple[int, int]:
    img = _open_and_fix_orientation(image_data)
    return img.width, img.height


import json


def _make_json_safe(value):
    """Convert EXIF values to plain Python types that are JSON-serializable.

    Pillow returns IFDRational, IFD types etc. that pass isinstance checks
    for int/float but aren't actually serializable by json.dumps.
    Force conversion to plain Python types using type constructors.
    """
    if isinstance(value, bytes):
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        return str(value)
    # Force to plain float first (catches IFDRational which is a fraction type)
    try:
        f = float(value)
        # If it's a whole number, store as int
        if f == int(f):
            return int(f)
        return f
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        pass
    if isinstance(value, (tuple, list)):
        items = [_make_json_safe(v) for v in value]
        return [v for v in items if v is not None]
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items() if _make_json_safe(v) is not None}
    try:
        return str(value)
    except (TypeError, ValueError):
        return None


def extract_exif(image_data: bytes) -> dict | None:
    try:
        img = Image.open(io.BytesIO(image_data))
        exif_raw = img.getexif()
        if not exif_raw:
            return None
        exif = {}
        for tag_id, value in exif_raw.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            safe_value = _make_json_safe(value)
            if safe_value is not None:
                exif[tag_name] = safe_value
        if not exif:
            return None
        # Final safety check — if anything slipped through, discard all EXIF
        json.dumps(exif)
        return exif
    except Exception:
        return None


def apply_watermark(image_data: bytes, text: str = "PREVIEW", output_format: str = "JPEG") -> bytes:
    """Apply a diagonal repeating text watermark to an image."""
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    w, h = img.size

    # Create transparent overlay
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Font size relative to image
    font_size = max(20, min(w, h) // 15)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default(size=font_size)

    # Get text dimensions
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Draw repeating diagonal text
    step_x = tw + font_size * 3
    step_y = th + font_size * 4

    for y in range(-h, h * 2, step_y):
        for x in range(-w, w * 2, step_x):
            draw.text((x, y), text, fill=(255, 255, 255, 60), font=font)

    # Rotate overlay 30 degrees
    overlay = overlay.rotate(30, center=(w // 2, h // 2), expand=False)

    # Composite
    result = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    fmt = "WEBP" if output_format.upper() == "WEBP" else "JPEG"
    result.save(buf, format=fmt, quality=85)
    return buf.getvalue()
