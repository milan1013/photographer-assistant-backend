"""
Playwright E2E test for gallery CRUD operations.
Tests: create gallery via UI, verify on dashboard, navigate, upload images,
       edit gallery name, delete gallery.
"""

import os
import traceback
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport,
    login_via_ui, register_user, report_dir, unique_email,
    upload_images,
)

EMAIL = unique_email("crud-test")
PASSWORD = "testpassword123"
GALLERY_NAME = "CRUD Test Gallery"
UPDATED_GALLERY_NAME = "Renamed Gallery"


def run() -> bool:
    report = TestReport()
    sdir = report_dir("e2e-gallery-crud-report")

    token, headers = register_user(EMAIL, PASSWORD, "CRUD Tester")
    gallery_id = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            login_via_ui(page, EMAIL, PASSWORD)
            page.wait_for_timeout(2000)

            # ── T1: Create a gallery via UI ──
            try:
                # The create button has Plus icon + text, it's the primary button
                page.click("button:has(svg.lucide-plus)", timeout=5000)
                page.wait_for_timeout(500)

                # Dialog opens with autoFocus input
                name_input = page.locator(".fixed.inset-0 input[type='text']").first
                name_input.wait_for(state="visible", timeout=5000)
                name_input.fill(GALLERY_NAME)

                page.click(".fixed.inset-0 button[type='submit']")
                page.wait_for_timeout(3000)

                ss = os.path.join(sdir, "t1.png")
                page.screenshot(path=ss)
                report.add("T1: Create gallery via UI", True, ss=ss)
            except Exception as e:
                ss = os.path.join(sdir, "t1_fail.png")
                page.screenshot(path=ss)
                report.add("T1: Create gallery via UI", False, str(e), ss)

            # ── T2: Gallery appears on dashboard ──
            try:
                page.wait_for_timeout(1000)
                body = page.inner_text("body")
                found = GALLERY_NAME in body

                ss = os.path.join(sdir, "t2.png")
                page.screenshot(path=ss)
                report.add("T2: Gallery appears on dashboard", found, ss=ss)
            except Exception as e:
                report.add("T2: Gallery appears on dashboard", False, str(e))

            # ── T3: Navigate to gallery ──
            try:
                # Click the gallery card (the h3 with the name)
                page.click(f"h3:text('{GALLERY_NAME}')", timeout=5000)
                page.wait_for_url("**/gallery/**", timeout=10000)

                current_url = page.url
                gallery_id = current_url.split("/gallery/")[-1].split("?")[0].split("#")[0]

                ss = os.path.join(sdir, "t3.png")
                page.screenshot(path=ss)
                report.add("T3: Navigate to gallery", bool(gallery_id), f"ID: {gallery_id}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t3_fail.png")
                page.screenshot(path=ss)
                report.add("T3: Navigate to gallery", False, str(e), ss)

            # ── T4: Upload images via API ──
            try:
                if gallery_id:
                    uploaded = upload_images(headers, gallery_id, count=3, color="blue")
                    page.reload()
                    page.wait_for_timeout(3000)

                    ss = os.path.join(sdir, "t4.png")
                    page.screenshot(path=ss)
                    report.add("T4: Upload images via API", len(uploaded) == 3,
                               f"Uploaded {len(uploaded)}", ss)
                else:
                    report.add("T4: Upload images via API", False, "No gallery_id")
            except Exception as e:
                report.add("T4: Upload images via API", False, str(e))

            # ── T5: Images appear in gallery ──
            try:
                page.wait_for_selector(".aspect-square", timeout=10000)
                count = len(page.query_selector_all(".aspect-square"))

                ss = os.path.join(sdir, "t5.png")
                page.screenshot(path=ss)
                report.add("T5: Images appear in gallery", count >= 3, f"Found {count}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t5_fail.png")
                page.screenshot(path=ss)
                report.add("T5: Images appear in gallery", False, str(e), ss)

            # ── T6: Edit gallery name via API ──
            try:
                if gallery_id:
                    requests.patch(
                        f"{API_URL}/api/galleries/{gallery_id}",
                        json={"name": UPDATED_GALLERY_NAME},
                        headers=headers,
                    )
                    page.reload()
                    page.wait_for_timeout(2000)

                    body = page.inner_text("body")
                    ss = os.path.join(sdir, "t6.png")
                    page.screenshot(path=ss)
                    report.add("T6: Edit gallery name", UPDATED_GALLERY_NAME in body, ss=ss)
                else:
                    report.add("T6: Edit gallery name", False, "No gallery_id")
            except Exception as e:
                report.add("T6: Edit gallery name", False, str(e))

            # ── T7: Delete gallery via API ──
            try:
                if gallery_id:
                    resp = requests.delete(
                        f"{API_URL}/api/galleries/{gallery_id}",
                        headers=headers,
                    )
                    ss = os.path.join(sdir, "t7.png")
                    page.screenshot(path=ss)
                    report.add("T7: Delete gallery", resp.status_code in (200, 204),
                               f"HTTP {resp.status_code}", ss)
                else:
                    report.add("T7: Delete gallery", False, "No gallery_id")
            except Exception as e:
                report.add("T7: Delete gallery", False, str(e))

            # ── T8: Gallery removed from dashboard ──
            try:
                page.wait_for_timeout(2000)
                page.reload()
                page.wait_for_timeout(3000)

                body = page.inner_text("body")
                gone = UPDATED_GALLERY_NAME not in body

                ss = os.path.join(sdir, "t8.png")
                page.screenshot(path=ss)
                report.add("T8: Gallery removed from dashboard", gone, ss=ss)
            except Exception as e:
                report.add("T8: Gallery removed from dashboard", False, str(e))

        except Exception as e:
            ss = os.path.join(sdir, "error.png")
            try:
                page.screenshot(path=ss)
            except Exception:
                pass
            report.add("Unexpected error", False, traceback.format_exc(), ss)
        finally:
            browser.close()

    report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-gallery-crud-report.html")
    report.save(report_path, "Gallery CRUD E2E Test Report")
    report.print_summary(report_path)
    return report.all_passed


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
