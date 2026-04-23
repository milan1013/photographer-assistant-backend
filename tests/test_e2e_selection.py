"""
Playwright E2E test for shift-click range selection.
Registers a user, creates a gallery, uploads images, then tests selection.
Exports HTML report to Desktop.
"""

import os
import time
import traceback
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, login_via_ui, make_test_image,
    report_dir, unique_email,
)

EMAIL = unique_email("selection")
PASSWORD = "testpassword123"
FULL_NAME = "Playwright Tester"


def screenshot(page, name, sdir):
    path = os.path.join(sdir, f"{name}.png")
    page.screenshot(path=path)
    return path


def count_selected(page):
    return len(page.query_selector_all("[class*='ring-blue']"))


def get_checkboxes(page):
    return page.query_selector_all(".aspect-square .absolute")


def get_image_areas(page):
    return page.query_selector_all(".aspect-square")


def clear_selection(page):
    bars = page.query_selector_all(".fixed.bottom-0 button")
    if bars:
        bars[0].click()
        page.wait_for_timeout(500)


def run():
    report = TestReport()
    reports_base = str(Path(__file__).resolve().parent / "reports")
    sdir = report_dir("e2e-selection-report")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # --- Setup: Register via UI ---
            print("\n--- Setup ---")
            page.goto(f"{BASE_URL}/register")
            page.wait_for_timeout(1000)
            page.fill("#fullName", FULL_NAME)
            page.fill("#email", EMAIL)
            page.fill("#password", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)
            report.add("Register", "/register" not in page.url, page.url)

            # Create gallery via UI
            buttons = page.query_selector_all("button")
            for btn in buttons:
                text = btn.text_content() or ""
                if "+" in text or "Nova" in text or "New" in text:
                    btn.click()
                    break
            page.wait_for_timeout(1000)
            page.fill("input[type='text']", "Playwright Gallery")
            page.click("form button[type='submit']")
            page.wait_for_timeout(2000)

            # Navigate to gallery
            cards = page.query_selector_all("[class*='cursor-pointer'][class*='rounded-lg']")
            if cards:
                cards[0].click()
                page.wait_for_timeout(2000)

            gallery_id = page.url.split("/gallery/")[1].split("?")[0]
            report.add("Setup gallery", bool(gallery_id), f"ID: {gallery_id}")

            # Upload via API
            login_resp = requests.post(f"{API_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
            token = login_resp.json()["access_token"]
            h = {"Authorization": f"Bearer {token}"}
            files = [("files", (f"img_{i+1}.jpg", make_test_image(), "image/jpeg")) for i in range(6)]
            upload_resp = requests.post(f"{API_URL}/api/galleries/{gallery_id}/images", headers=h, files=files)
            uploaded = upload_resp.json().get("uploaded", [])
            report.add("Upload 6 images", len(uploaded) == 6, f"Uploaded {len(uploaded)}")

            page.reload()
            page.wait_for_timeout(3000)

            # --- Test 1: Click checkbox on image 1 ---
            print("\n--- Selection Tests ---")
            cb = get_checkboxes(page)
            report.add("Found 6 checkboxes", len(cb) >= 6, f"Found {len(cb)}")

            cb[0].click()
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T1: Click checkbox 1 -> 1 selected", sel == 1, f"Got {sel}",
                        screenshot(page, "t1_click_cb1", sdir))

            # --- Test 2: Shift+click checkbox 4 (range 1-4) ---
            cb = get_checkboxes(page)
            cb[3].click(modifiers=["Shift"])
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T2: Shift+click checkbox 4 -> 4 selected (range 1-4)", sel == 4, f"Got {sel}",
                        screenshot(page, "t2_shift_cb4", sdir))

            # --- Clear ---
            clear_selection(page)

            # --- Test 3: Click checkbox 2 ---
            cb = get_checkboxes(page)
            cb[1].click()
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T3: Click checkbox 2 -> 1 selected", sel == 1, f"Got {sel}",
                        screenshot(page, "t3_click_cb2", sdir))

            # --- Test 4: Shift+click checkbox 5 (range 2-5) ---
            cb = get_checkboxes(page)
            cb[4].click(modifiers=["Shift"])
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T4: Shift+click checkbox 5 -> 4 selected (range 2-5)", sel == 4, f"Got {sel}",
                        screenshot(page, "t4_shift_cb5", sdir))

            # --- Clear ---
            clear_selection(page)

            # --- Test 5: Ctrl+click image area of image 1 ---
            areas = get_image_areas(page)
            areas[0].click(modifiers=["Control"])
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T5: Ctrl+click image 1 -> 1 selected", sel == 1, f"Got {sel}",
                        screenshot(page, "t5_ctrl_img1", sdir))

            # --- Test 6: Shift+click image area of image 6 (range 1-6) ---
            areas = get_image_areas(page)
            areas[5].click(modifiers=["Shift"])
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T6: Shift+click image 6 -> 6 selected (range 1-6)", sel == 6, f"Got {sel}",
                        screenshot(page, "t6_shift_img6", sdir))

            # --- Clear ---
            clear_selection(page)

            # --- Test 7: Click checkbox 3, shift+click checkbox 6 ---
            cb = get_checkboxes(page)
            cb[2].click()
            page.wait_for_timeout(300)
            cb = get_checkboxes(page)
            cb[5].click(modifiers=["Shift"])
            page.wait_for_timeout(500)
            sel = count_selected(page)
            report.add("T7: Click cb3, shift+click cb6 -> 4 selected (range 3-6)", sel == 4, f"Got {sel}",
                        screenshot(page, "t7_cb3_shift_cb6", sdir))

        except Exception as e:
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            screenshot(page, "error", sdir)
        finally:
            browser.close()

    report_path = os.path.join(reports_base, "e2e-selection-report.html")
    report.save(report_path, "Selection Test Report")
    report.print_summary(report_path)
    return report.all_passed


if __name__ == "__main__":
    success = run()
    exit(0 if success else 1)
