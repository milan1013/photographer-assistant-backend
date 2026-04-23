"""
Playwright E2E test for copy count input behavior.
Tests that users can clear '0' and type a new number without getting '01'.
"""

import os
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, create_gallery, login_via_ui, navigate_to_gallery,
    make_test_image, register_user, report_dir, unique_email, upload_images,
)

EMAIL = unique_email("copies")
PASSWORD = "testpassword123"


def screenshot(page, name, sdir):
    path = os.path.join(sdir, f"{name}.png")
    page.screenshot(path=path)
    return path


def run():
    report = TestReport()
    sdir = report_dir("e2e-copies-report")

    # Setup: register, create gallery, upload images via API
    token, h = register_user(EMAIL, PASSWORD, "Copies Tester")
    gid = create_gallery(h, "Copies Test")
    uploaded = upload_images(h, gid, count=3)
    if not uploaded:
        report.add("Setup: Upload images", False, "No images uploaded")
        path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-copies-report.html")
        report.save(path, "Copies Input Test Report")
        report.print_summary(path)
        return report.all_passed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # Login and navigate to gallery
            login_via_ui(page, EMAIL, PASSWORD)
            page.wait_for_timeout(2000)

            navigate_to_gallery(page)

            # Wait for copies inputs to render
            try:
                page.wait_for_selector("input[inputmode='numeric']", timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(1000)

            # --- T1: Thumbnail copies input - clear and type ---
            print("\n--- Thumbnail Copies Input ---")
            copies_inputs = page.query_selector_all("input[inputmode='numeric']")
            report.add("T1: Found copies inputs", len(copies_inputs) >= 3, f"Found {len(copies_inputs)}")

            if len(copies_inputs) >= 1:
                inp = copies_inputs[0]
                inp.click()
                page.wait_for_timeout(300)

                # Select all and delete
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                val_after_clear = page.input_value("input[inputmode='numeric']")
                report.add("T2: Can clear input to empty", val_after_clear == "", f"Value after clear: '{val_after_clear}'", screenshot(page, "t2", sdir))

                # Type '5'
                page.keyboard.type("5")
                page.wait_for_timeout(200)
                val_after_type = page.input_value("input[inputmode='numeric']")
                report.add("T3: Type '5' shows '5' not '05'", val_after_type == "5", f"Value: '{val_after_type}'", screenshot(page, "t3", sdir))

                # Clear and type '12'
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.keyboard.type("12")
                page.wait_for_timeout(200)
                val_twelve = page.input_value("input[inputmode='numeric']")
                report.add("T4: Type '12' shows '12'", val_twelve == "12", f"Value: '{val_twelve}'", screenshot(page, "t4", sdir))

            # --- T5: Batch copies input ---
            print("\n--- Batch Copies Input ---")
            # Select images first
            checkboxes = page.query_selector_all(".aspect-square .absolute")
            if len(checkboxes) >= 2:
                checkboxes[0].click()
                page.wait_for_timeout(300)
                checkboxes[1].click()
                page.wait_for_timeout(500)

            # Find batch input in selection bar
            batch_inputs = page.query_selector_all(".fixed.bottom-0 input[inputmode='numeric']")
            report.add("T5: Found batch copies input", len(batch_inputs) >= 1, f"Found {len(batch_inputs)}")

            if len(batch_inputs) >= 1:
                batch_inp = batch_inputs[0]
                batch_inp.click()
                page.wait_for_timeout(300)

                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                batch_cleared = batch_inp.input_value()
                report.add("T6: Can clear batch input", batch_cleared == "", f"Value: '{batch_cleared}'", screenshot(page, "t6", sdir))

                page.keyboard.type("3")
                page.wait_for_timeout(200)
                batch_typed = batch_inp.input_value()
                report.add("T7: Batch input type '3' shows '3' not '03'", batch_typed == "3", f"Value: '{batch_typed}'", screenshot(page, "t7", sdir))

            # --- T8: Viewer copies input ---
            print("\n--- Viewer Copies Input ---")
            # Clear selection first
            x_btns = page.query_selector_all(".fixed.bottom-0 button")
            if x_btns:
                x_btns[0].click()
                page.wait_for_timeout(500)

            # Click image to open viewer
            image_areas = page.query_selector_all(".aspect-square")
            if image_areas:
                image_areas[0].click()
                page.wait_for_timeout(1000)

            viewer_inputs = page.query_selector_all("input[inputmode='numeric']")
            viewer_inp = None
            for vi in viewer_inputs:
                if vi.is_visible() and "w-20" in (vi.get_attribute("class") or ""):
                    viewer_inp = vi
                    break

            if viewer_inp:
                viewer_inp.click()
                page.wait_for_timeout(300)
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                viewer_cleared = viewer_inp.input_value()
                report.add("T8: Can clear viewer input", viewer_cleared == "", f"Value: '{viewer_cleared}'", screenshot(page, "t8", sdir))

                page.keyboard.type("7")
                page.wait_for_timeout(200)
                viewer_typed = viewer_inp.input_value()
                report.add("T9: Viewer input type '7' shows '7' not '07'", viewer_typed == "7", f"Value: '{viewer_typed}'", screenshot(page, "t9", sdir))
            else:
                report.add("T8: Viewer input found", False, "Could not find viewer copies input")
                report.add("T9: Viewer input typing", False, "Skipped")

        except Exception as e:
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            screenshot(page, "error", sdir)
        finally:
            browser.close()

    path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-copies-report.html")
    report.save(path, "Copies Input Test Report")
    report.print_summary(path)
    return report.all_passed


if __name__ == "__main__":
    exit(0 if run() else 1)
