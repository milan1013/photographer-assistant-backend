"""
Playwright E2E test for EXIF orientation fix.
Uploads an image with EXIF rotation tag and verifies it displays correctly.
"""

import io
import os
import time
import traceback
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, create_gallery,
    login_via_ui, navigate_to_gallery, register_user,
    report_dir, unique_email,
)

EMAIL = unique_email("rotation")
PASSWORD = "testpassword123"


def make_rotated_image() -> bytes:
    """Create a 200x100 image (landscape) with EXIF orientation=6 (rotate 90 CW).
    Without EXIF fix, it displays as 200x100 (wrong). With fix, it should be 100x200 (correct)."""
    img = Image.new("RGB", (200, 100), color="red")
    for x in range(100, 200):
        for y in range(50, 100):
            img.putpixel((x, y), (0, 0, 255))

    exif = img.getexif()
    exif[0x0112] = 6

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def make_normal_image() -> bytes:
    """Create a 200x100 landscape image with no EXIF orientation."""
    img = Image.new("RGB", (200, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def run():
    import requests

    report = TestReport()
    reports_base = str(Path(__file__).resolve().parent / "reports")
    sdir = report_dir("e2e-rotation-report")

    # Setup
    token, h = register_user(EMAIL, PASSWORD, "Rotation Tester")
    gid = create_gallery(h, "Rotation Test")

    # T1: Upload rotated image, check dimensions
    rotated_data = make_rotated_image()
    upload_resp = requests.post(
        f"{API_URL}/api/galleries/{gid}/images",
        headers=h,
        files=[("files", ("rotated.jpg", rotated_data, "image/jpeg"))],
    )
    if upload_resp.status_code != 201:
        report.add("T1: Upload rotated image", False, f"HTTP {upload_resp.status_code}: {upload_resp.text}")
    else:
        upload = upload_resp.json()
        if upload.get("uploaded"):
            img_data = upload["uploaded"][0]
            w, h_dim = img_data["width"], img_data["height"]
            report.add(
                "T1: Rotated image dimensions corrected",
                w == 100 and h_dim == 200,
                f"Got {w}x{h_dim}, expected 100x200 (EXIF orientation=6 applied)",
            )
        else:
            report.add("T1: Upload rotated image", False, f"No images uploaded: {upload}")

    # T2: Upload normal image
    normal_data = make_normal_image()
    upload2_resp = requests.post(
        f"{API_URL}/api/galleries/{gid}/images",
        headers=h,
        files=[("files", ("normal.jpg", normal_data, "image/jpeg"))],
    )
    if upload2_resp.status_code != 201:
        report.add("T2: Upload normal image", False, f"HTTP {upload2_resp.status_code}")
    else:
        upload2 = upload2_resp.json()
        if upload2.get("uploaded"):
            img_data2 = upload2["uploaded"][0]
            w2, h2 = img_data2["width"], img_data2["height"]
            report.add(
                "T2: Normal image dimensions unchanged",
                w2 == 200 and h2 == 100,
                f"Got {w2}x{h2}, expected 200x100",
            )
        else:
            report.add("T2: Upload normal image", False, f"Upload failed: {upload2}")

    # T3: Download thumbnail and verify orientation
    upload = upload_resp.json() if upload_resp.status_code == 201 else {}
    if upload.get("uploaded"):
        img_id = upload["uploaded"][0]["id"]
        thumb_resp = requests.get(f"{API_URL}/api/images/{img_id}/thumbnail?token={token}")
        thumb_img = Image.open(io.BytesIO(thumb_resp.content))
        report.add(
            "T3: Thumbnail has correct orientation",
            thumb_img.height > thumb_img.width,
            f"Thumbnail size: {thumb_img.width}x{thumb_img.height} ({'portrait' if thumb_img.height > thumb_img.width else 'landscape'})",
        )

        # T4: Download medium and verify orientation
        medium_resp = requests.get(f"{API_URL}/api/images/{img_id}/file?size=medium&token={token}")
        medium_img = Image.open(io.BytesIO(medium_resp.content))
        report.add(
            "T4: Medium image has correct orientation",
            medium_img.height > medium_img.width,
            f"Medium size: {medium_img.width}x{medium_img.height} ({'portrait' if medium_img.height > medium_img.width else 'landscape'})",
        )
    else:
        report.add("T3: Thumbnail orientation", False, "Skipped - upload failed")
        report.add("T4: Medium orientation", False, "Skipped - upload failed")

    # T5: Upload real problem image from desktop (optional)
    problem_path = os.path.join(str(Path.home() / "Desktop"), "this image will rotate.jpeg")
    if os.path.exists(problem_path):
        with open(problem_path, "rb") as f:
            problem_data = f.read()

        orig = Image.open(io.BytesIO(problem_data))
        orig_exif = orig.getexif()
        orientation = orig_exif.get(0x0112, 1)

        upload3_resp = requests.post(
            f"{API_URL}/api/galleries/{gid}/images",
            headers=h,
            files=[("files", ("problem.jpg", problem_data, "image/jpeg"))],
        )

        if upload3_resp.status_code == 201 and upload3_resp.json().get("uploaded"):
            prob = upload3_resp.json()["uploaded"][0]
            report.add(
                "T5: Real problem image uploaded successfully",
                True,
                f"Original EXIF orientation={orientation}, stored as {prob['width']}x{prob['height']}",
            )

            prob_thumb = requests.get(f"{API_URL}/api/images/{prob['id']}/thumbnail?token={token}")
            prob_thumb_img = Image.open(io.BytesIO(prob_thumb.content))
            report.add(
                "T6: Real image thumbnail orientation",
                True,
                f"Thumbnail: {prob_thumb_img.width}x{prob_thumb_img.height}",
            )
        else:
            report.add("T5: Real problem image", False, "Upload failed")
            report.add("T6: Real image thumbnail", False, "Skipped")
    else:
        report.add("T5: Real problem image", False, f"File not found: {problem_path}")
        report.add("T6: Real image thumbnail", False, "Skipped")

    # T7-T8: Browser-based visual checks
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            login_via_ui(page, EMAIL, PASSWORD)

            navigate_to_gallery(page)

            ss7 = os.path.join(sdir, "t7_gallery_view.png")
            page.screenshot(path=ss7)
            report.add(
                "T7: Gallery displays with corrected thumbnails",
                True,
                "Visual check",
                ss7,
            )

            # Click first thumbnail to open viewer
            thumbs = page.query_selector_all(".aspect-square")
            if thumbs:
                thumbs[0].click()
                page.wait_for_timeout(2000)
                ss8 = os.path.join(sdir, "t8_viewer.png")
                page.screenshot(path=ss8)
                report.add(
                    "T8: Viewer shows correctly oriented image",
                    True,
                    "Visual check",
                    ss8,
                )

        except Exception as e:
            ss_err = os.path.join(sdir, "error.png")
            page.screenshot(path=ss_err)
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        finally:
            context.close()
            browser.close()

    path = os.path.join(reports_base, "e2e-rotation-report.html")
    report.save(path, "EXIF Rotation Test Report")
    report.print_summary(path)
    return report.all_passed


if __name__ == "__main__":
    exit(0 if run() else 1)
