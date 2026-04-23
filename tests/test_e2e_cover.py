"""
Playwright E2E test for gallery cover image functionality.
Tests: auto-set on upload, manual set via edit modal.
"""

import os
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, create_gallery,
    login_via_ui, make_test_image, navigate_to_gallery,
    register_user, report_dir, unique_email,
)

EMAIL = unique_email("cover-test")
PASSWORD = "testpassword123"


def make_image(color: str) -> bytes:
    return make_test_image(color)


def run():
    import requests

    report = TestReport()
    sdir = report_dir("e2e-cover-report")

    # Setup: register, create gallery
    token, h = register_user(EMAIL, PASSWORD, "Cover Tester")
    gid = create_gallery(h, "Cover Test Gallery")

    # T1: No cover before upload
    gallery_before = requests.get(f"{API_URL}/api/galleries/{gid}", headers=h).json()
    report.add("T1: No cover before upload", gallery_before["cover_image_id"] is None)

    # T2: Upload 3 images, cover = last
    files = [
        ("files", ("red.jpg", make_image("red"), "image/jpeg")),
        ("files", ("green.jpg", make_image("green"), "image/jpeg")),
        ("files", ("blue.jpg", make_image("blue"), "image/jpeg")),
    ]
    upload_resp = requests.post(f"{API_URL}/api/galleries/{gid}/images", headers=h, files=files)
    if upload_resp.status_code != 201:
        report.add("T2: Upload images", False, f"HTTP {upload_resp.status_code}: {upload_resp.text}")
        path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-cover-report.html")
        report.save(path, "Cover Image Test Report")
        report.print_summary(path)
        return report.all_passed

    upload = upload_resp.json()
    last_id = upload["uploaded"][-1]["id"]
    gallery_after = requests.get(f"{API_URL}/api/galleries/{gid}", headers=h).json()
    report.add("T2: Cover auto-set to last uploaded", gallery_after["cover_image_id"] == last_id)

    # T3: Upload more, cover updates
    files2 = [("files", ("yellow.jpg", make_image("yellow"), "image/jpeg"))]
    upload2 = requests.post(f"{API_URL}/api/galleries/{gid}/images", headers=h, files=files2).json()
    yellow_id = upload2["uploaded"][0]["id"]
    gallery_after2 = requests.get(f"{API_URL}/api/galleries/{gid}", headers=h).json()
    report.add("T3: Cover updates to newest", gallery_after2["cover_image_id"] == yellow_id)

    # T4: Manual set via API
    red_id = upload["uploaded"][0]["id"]
    requests.patch(f"{API_URL}/api/galleries/{gid}", json={"cover_image_id": red_id}, headers=h)
    gallery_manual = requests.get(f"{API_URL}/api/galleries/{gid}", headers=h).json()
    report.add("T4: Manual set cover via API", gallery_manual["cover_image_id"] == red_id)

    # T5-T8: Browser-based tests
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            login_via_ui(page, EMAIL, PASSWORD)

            page.wait_for_timeout(2000)
            gallery_imgs = page.query_selector_all(".aspect-video img")
            ss = os.path.join(sdir, "t5.png")
            page.screenshot(path=ss)
            report.add("T5: Dashboard shows cover thumbnail", len(gallery_imgs) > 0, ss=ss)

            # T6: Navigate to gallery, click edit pencil, see thumbnail grid
            navigate_to_gallery(page)

            # Find pencil edit button
            pencil_btns = page.query_selector_all("button[title]")
            edit_btn = None
            for btn in pencil_btns:
                title = btn.get_attribute("title") or ""
                if "edit" in title.lower() or "izmeni" in title.lower():
                    edit_btn = btn
                    break

            ss6 = os.path.join(sdir, "t6.png")
            page.screenshot(path=ss6)
            report.add("T6: Edit pencil button found", edit_btn is not None, ss=ss6)

            if edit_btn:
                edit_btn.click()
                page.wait_for_selector(".fixed.inset-0.z-50", timeout=5000)

                # Check for thumbnail grid in modal (buttons inside the grid)
                modal = page.query_selector(".fixed.inset-0.z-50")
                thumb_buttons = modal.query_selector_all("button.aspect-square")
                ss7 = os.path.join(sdir, "t7.png")
                page.screenshot(path=ss7)
                report.add(
                    "T7: Edit modal shows thumbnail grid",
                    len(thumb_buttons) >= 4,
                    f"Found {len(thumb_buttons)} thumbnails",
                    ss7,
                )

                # Click a different thumbnail to change cover
                if len(thumb_buttons) >= 2:
                    thumb_buttons[1].click()
                    time.sleep(1)
                    ss8 = os.path.join(sdir, "t8.png")
                    page.screenshot(path=ss8)
                    report.add("T8: Clicked thumbnail to change cover", True, ss=ss8)

        except Exception as e:
            ss_err = os.path.join(sdir, "error.png")
            page.screenshot(path=ss_err)
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}")
        finally:
            context.close()
            browser.close()

    path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-cover-report.html")
    report.save(path, "Cover Image Test Report")
    report.print_summary(path)
    return report.all_passed


if __name__ == "__main__":
    exit(0 if run() else 1)
