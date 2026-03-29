import csv
import io
import uuid
import zipfile

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image as RLImage, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from PIL import Image as PILImage

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_active_share_link
from app.models.user import User
from app.crud.galleries import get_gallery
from app.crud.images import get_images_by_gallery, get_image
from app.storage import get_storage, StorageBackend

router = APIRouter()

_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


def _content_disposition(filename: str) -> str:
    """Build a Content-Disposition header safe for non-ASCII filenames."""
    from urllib.parse import quote
    # ASCII-safe fallback + RFC 5987 UTF-8 encoded name
    ascii_name = filename.encode("ascii", "replace").decode("ascii")
    encoded = quote(filename)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def _generate_csv(images) -> io.StringIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["filename", "copies"])
    for img in images:
        writer.writerow([img.filename, img.num_copies])
    output.seek(0)
    return output


@router.get("/galleries/{gallery_id}/export/csv")
async def export_csv(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    images = await get_images_by_gallery(db, gallery_id)
    output = _generate_csv(images)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": _content_disposition(f"{gallery.name}.csv")},
    )


@router.get("/shared/{token}/export/csv")
async def shared_export_csv(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    gallery = await get_gallery(db, link.gallery_id)
    if not gallery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    images = await get_images_by_gallery(db, link.gallery_id)
    output = _generate_csv(images)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": _content_disposition(f"{gallery.name}.csv")},
    )


# --- PDF contact sheet ---

def _generate_pdf(images, gallery_name: str, storage) -> bytes:
    """Generate a PDF contact sheet with thumbnails and copy counts."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"<b>{gallery_name}</b>", styles["Title"]))
    elements.append(Spacer(1, 5 * mm))

    # Build rows: 4 images per row
    COLS = 4
    THUMB_SIZE = 35 * mm
    rows = []
    current_row = []

    for img in images:
        # Load thumbnail
        import asyncio
        try:
            thumb_data = asyncio.get_event_loop().run_until_complete(storage.get(img.thumbnail_key))
            thumb_buf = io.BytesIO(thumb_data)
            rl_img = RLImage(thumb_buf, width=THUMB_SIZE, height=THUMB_SIZE)
        except Exception:
            rl_img = Paragraph("?", styles["Normal"])

        cell = [
            rl_img,
            Paragraph(f"<font size=7>{img.filename[:20]}</font>", styles["Normal"]),
            Paragraph(f"<font size=8><b>{img.num_copies}</b> copies</font>", styles["Normal"]),
        ]
        # Wrap in a mini table for vertical stacking
        mini = Table([[c] for c in cell], colWidths=[THUMB_SIZE + 5 * mm])
        mini.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        current_row.append(mini)

        if len(current_row) == COLS:
            rows.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < COLS:
            current_row.append("")
        rows.append(current_row)

    if rows:
        col_w = (A4[0] - 30 * mm) / COLS
        table = Table(rows, colWidths=[col_w] * COLS)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        elements.append(table)

    doc.build(elements)
    return buf.getvalue()


@router.get("/galleries/{gallery_id}/export/pdf")
async def export_pdf(
    gallery_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    images = await get_images_by_gallery(db, gallery_id)

    storage = _get_storage()
    # Need to load thumbnails - use sync wrapper since reportlab is sync
    import asyncio

    async def load_thumbs():
        for img in images:
            img._thumb_data = await storage.get(img.thumbnail_key)

    await load_thumbs()

    # Generate PDF synchronously
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"<b>{gallery.name}</b>", styles["Title"]))
    elements.append(Spacer(1, 5 * mm))

    COLS = 4
    THUMB_SIZE = 35 * mm
    rows = []
    current_row = []

    for img in images:
        try:
            thumb_buf = io.BytesIO(img._thumb_data)
            rl_img = RLImage(thumb_buf, width=THUMB_SIZE, height=THUMB_SIZE)
        except Exception:
            rl_img = Paragraph("?", styles["Normal"])

        cell = [
            rl_img,
            Paragraph(f"<font size=7>{img.filename[:25]}</font>", styles["Normal"]),
            Paragraph(f"<font size=9><b>{img.num_copies}</b> kopija</font>", styles["Normal"]),
        ]
        mini = Table([[c] for c in cell], colWidths=[THUMB_SIZE + 5 * mm])
        mini.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        current_row.append(mini)

        if len(current_row) == COLS:
            rows.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < COLS:
            current_row.append("")
        rows.append(current_row)

    if rows:
        col_w = (A4[0] - 30 * mm) / COLS
        table = Table(rows, colWidths=[col_w] * COLS)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        elements.append(table)

    doc.build(elements)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(f"{gallery.name}.pdf")},
    )


# --- Invoice generation ---

@router.get("/galleries/{gallery_id}/export/invoice")
async def export_invoice(
    gallery_id: uuid.UUID,
    price_per_copy: float = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.config import settings as app_settings

    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")
    images = await get_images_by_gallery(db, gallery_id)

    price = price_per_copy if price_per_copy is not None else app_settings.default_price_per_copy
    currency = app_settings.currency

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"<b>INVOICE</b>", styles["Title"]))
    elements.append(Paragraph(f"Gallery: {gallery.name}", styles["Normal"]))
    from datetime import datetime
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles["Normal"]))
    elements.append(Spacer(1, 10 * mm))

    # Table header
    data = [["#", "Filename", "Copies", f"Price ({currency})", f"Total ({currency})"]]

    total_copies = 0
    grand_total = 0.0

    for i, img in enumerate(images):
        if img.num_copies > 0:
            line_total = img.num_copies * price
            total_copies += img.num_copies
            grand_total += line_total
            data.append([
                str(i + 1),
                img.filename[:30],
                str(img.num_copies),
                f"{price:.2f}",
                f"{line_total:.2f}",
            ])

    if len(data) == 1:
        elements.append(Paragraph("No images with copies > 0", styles["Normal"]))
    else:
        # Summary row
        data.append(["", "", str(total_copies), "", f"{grand_total:.2f}"])

        col_widths = [30, 180, 60, 80, 80]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
            ("LINEABOVE", (0, -1), (-1, -1), 1.5, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 15 * mm))
    elements.append(Paragraph(f"<b>Total: {grand_total:.2f} {currency}</b>", styles["Heading2"]))

    doc.build(elements)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(f"Invoice - {gallery.name}.pdf")},
    )


# --- Image download endpoints ---


@router.get("/images/{image_id}/download")
async def download_single_image(
    image_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a single image as its original file."""
    image = await get_image(db, image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    gallery = await get_gallery(db, image.gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    data = await _get_storage().get(image.storage_key)
    return Response(
        content=data,
        media_type=image.mime_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(image.filename)},
    )


@router.post("/galleries/{gallery_id}/download/zip")
async def download_images_zip(
    gallery_id: uuid.UUID,
    image_ids: list[uuid.UUID] = Body(default=None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download images as a ZIP archive. If image_ids is null/empty, downloads all images."""
    gallery = await get_gallery(db, gallery_id)
    if not gallery or gallery.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    all_images = await get_images_by_gallery(db, gallery_id)

    if image_ids:
        id_set = set(image_ids)
        images = [img for img in all_images if img.id in id_set]
    else:
        images = all_images

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No images to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            data = await _get_storage().get(img.storage_key)
            zf.writestr(img.filename, data)
    buf.seek(0)

    filename = f"{gallery.name}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


# Shared access download endpoints

@router.get("/shared/{token}/images/{image_id}/download")
async def shared_download_single(
    token: str,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    image = await get_image(db, image_id)
    if not image or image.gallery_id != link.gallery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    data = await _get_storage().get(image.storage_key)
    return Response(
        content=data,
        media_type=image.mime_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(image.filename)},
    )


@router.post("/shared/{token}/download/zip")
async def shared_download_zip(
    token: str,
    image_ids: list[uuid.UUID] = Body(default=None, embed=True),
    db: AsyncSession = Depends(get_db),
):
    link = await get_active_share_link(token, db)
    gallery = await get_gallery(db, link.gallery_id)
    if not gallery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gallery not found")

    all_images = await get_images_by_gallery(db, link.gallery_id)

    if image_ids:
        id_set = set(image_ids)
        images = [img for img in all_images if img.id in id_set]
    else:
        images = all_images

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No images to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            data = await _get_storage().get(img.storage_key)
            zf.writestr(img.filename, data)
    buf.seek(0)

    filename = f"{gallery.name}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(filename)},
    )
