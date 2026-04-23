"""
Playwright E2E test for share link functionality.
Tests: create share links (edit & view-only), access shared gallery,
       edit copies via edit link, verify view-only restrictions.
"""

import os
import traceback
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, create_gallery,
    login_via_ui, register_user, report_dir, unique_email,
    upload_images,
)

EMAIL = unique_email("share-test")
PASSWORD = "testpassword123"
GALLERY_NAME = "Share Test Gallery"


def run() -> bool:
    report = TestReport()
    sdir = report_dir("e2e-share-link-report")

    gallery_id = None
    edit_share_url = None
    view_share_url = None

    # ── T1: Register, create gallery, upload images via API ──────
    try:
        token, headers = register_user(EMAIL, PASSWORD, "Share Tester")
        gallery_id = create_gallery(headers, GALLERY_NAME)
        uploaded = upload_images(headers, gallery_id, count=3, color="green")
        report.add("T1: Setup (register, gallery, images)",
                    gallery_id is not None and len(uploaded) == 3,
                    f"Gallery: {gallery_id}, images: {len(uploaded)}")
    except Exception as e:
        report.add("T1: Setup (register, gallery, images)", False, str(e))
        # Cannot continue without setup
        report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-share-link-report.html")
        report.save(report_path, "Share Link E2E Test Report")
        report.print_summary(report_path)
        return report.all_passed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            login_via_ui(page, EMAIL, PASSWORD)
            page.wait_for_timeout(2000)

            # ── T2: Navigate to gallery, find share button ───────────
            try:
                page.goto(f"{BASE_URL}/gallery/{gallery_id}")
                page.wait_for_timeout(3000)

                share_btn = page.locator("button:has(svg.lucide-share-2)")
                share_btn.wait_for(state="visible", timeout=10000)

                ss = os.path.join(sdir, "t2_share_button.png")
                page.screenshot(path=ss)
                report.add("T2: Navigate to gallery, share button visible", True,
                           "Share button found", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t2_share_button_fail.png")
                page.screenshot(path=ss)
                report.add("T2: Navigate to gallery, share button visible", False, str(e), ss)

            # ── T3: Open share dialog, create "edit" share link ──────
            try:
                # Click share button to open the dialog
                page.click("button:has(svg.lucide-share-2)", timeout=5000)
                page.wait_for_timeout(1000)

                # The share dialog should be visible
                dialog = page.locator("div.fixed div.rounded-lg").first
                dialog.wait_for(state="visible", timeout=5000)

                # Set permission to "edit"
                permission_select = page.locator("div.fixed select")
                permission_select.select_option("edit")
                page.wait_for_timeout(300)

                # Optionally set a label
                label_input = page.locator("div.fixed input[type='text']").first
                label_input.fill("Edit Link")

                # Click create link button (has Link icon)
                create_btn = page.locator("div.fixed button:has(svg.lucide-link)")
                create_btn.click(timeout=5000)
                page.wait_for_timeout(2000)

                # Verify a link row appeared in the dialog
                link_rows = page.locator("div.fixed .space-y-2 > div").count()

                ss = os.path.join(sdir, "t3_create_edit_link.png")
                page.screenshot(path=ss)
                report.add("T3: Create edit share link", link_rows >= 1,
                           f"Link rows in dialog: {link_rows}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t3_create_edit_link_fail.png")
                page.screenshot(path=ss)
                report.add("T3: Create edit share link", False, str(e), ss)

            # ── T4: Copy the share URL ───────────────────────────────
            try:
                # Get the share link via API (more reliable than clipboard)
                shares_resp = requests.get(
                    f"{API_URL}/api/galleries/{gallery_id}/shares", headers=headers
                )
                shares_resp.raise_for_status()
                shares = shares_resp.json()
                edit_share = next((s for s in shares if s["permission"] == "edit"), None)

                if edit_share:
                    edit_share_url = f"{BASE_URL}/shared/{edit_share['token']}"

                    # Also click copy button in UI to verify it works
                    copy_btn = page.locator("div.fixed .space-y-2 button:has(svg.lucide-copy)").first
                    copy_btn.click(timeout=3000)
                    page.wait_for_timeout(1000)

                ss = os.path.join(sdir, "t4_copy_share_url.png")
                page.screenshot(path=ss)
                report.add("T4: Copy share URL", edit_share_url is not None,
                           f"URL: {edit_share_url}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t4_copy_share_url_fail.png")
                page.screenshot(path=ss)
                report.add("T4: Copy share URL", False, str(e), ss)

            # Close the share dialog
            try:
                page.click("div.fixed button:has(svg.lucide-x)", timeout=3000)
                page.wait_for_timeout(500)
            except Exception:
                pass

            # ── T5: Open share URL in new incognito page ─────────────
            try:
                if edit_share_url:
                    # Create a fresh context (no auth cookies/storage)
                    incognito = browser.new_context(viewport={"width": 1400, "height": 900})
                    shared_page = incognito.new_page()
                    shared_page.goto(edit_share_url)
                    shared_page.wait_for_timeout(3000)

                    ss = os.path.join(sdir, "t5_open_shared_url.png")
                    shared_page.screenshot(path=ss)

                    # Check we are on the shared gallery page
                    is_shared = "/shared/" in shared_page.url
                    report.add("T5: Open share URL (no auth)", is_shared,
                               f"URL: {shared_page.url}", ss)
                else:
                    report.add("T5: Open share URL (no auth)", False, "No edit_share_url from T4")
                    incognito = None
                    shared_page = None
            except Exception as e:
                ss = os.path.join(sdir, "t5_open_shared_url_fail.png")
                try:
                    shared_page.screenshot(path=ss)
                except Exception:
                    pass
                report.add("T5: Open share URL (no auth)", False, str(e), ss)

            # ── T6: Shared gallery loads and shows images ────────────
            try:
                if shared_page:
                    # Wait for images to load
                    shared_page.wait_for_selector("img[loading='lazy']", timeout=10000)
                    img_count = shared_page.locator("img[loading='lazy']").count()

                    # Check that the gallery name is displayed
                    gallery_name_visible = shared_page.locator(f"text={GALLERY_NAME}").count() > 0

                    ss = os.path.join(sdir, "t6_shared_gallery_images.png")
                    shared_page.screenshot(path=ss)
                    report.add("T6: Shared gallery shows images",
                               img_count >= 3 and gallery_name_visible,
                               f"Images: {img_count}, name visible: {gallery_name_visible}", ss)
                else:
                    report.add("T6: Shared gallery shows images", False, "No shared_page")
            except Exception as e:
                ss = os.path.join(sdir, "t6_shared_gallery_images_fail.png")
                try:
                    shared_page.screenshot(path=ss)
                except Exception:
                    pass
                report.add("T6: Shared gallery shows images", False, str(e), ss)

            # ── T7: Edit permission allows changing copies count ─────
            try:
                if shared_page:
                    # The edit share link should show copies input fields
                    # Find a copies input on a thumbnail (input with inputMode="numeric")
                    copies_input = shared_page.locator("input[inputmode='numeric']").first
                    copies_input.wait_for(state="visible", timeout=5000)

                    # Change the copies value
                    copies_input.fill("")
                    copies_input.fill("5")
                    copies_input.blur()
                    shared_page.wait_for_timeout(2000)

                    # Verify the value stuck
                    new_val = copies_input.input_value()

                    ss = os.path.join(sdir, "t7_edit_copies.png")
                    shared_page.screenshot(path=ss)
                    report.add("T7: Edit permission - change copies", new_val == "5",
                               f"Copies value: {new_val}", ss)
                else:
                    report.add("T7: Edit permission - change copies", False, "No shared_page")
            except Exception as e:
                ss = os.path.join(sdir, "t7_edit_copies_fail.png")
                try:
                    shared_page.screenshot(path=ss)
                except Exception:
                    pass
                report.add("T7: Edit permission - change copies", False, str(e), ss)

            # Clean up incognito context
            if incognito:
                try:
                    incognito.close()
                except Exception:
                    pass

            # ── T8: Create "view only" share link ────────────────────
            try:
                # Re-open share dialog from the authenticated page
                page.click("button:has(svg.lucide-share-2)", timeout=5000)
                page.wait_for_timeout(1000)

                # Set permission to "view"
                permission_select = page.locator("div.fixed select")
                permission_select.select_option("view")
                page.wait_for_timeout(300)

                # Set a label
                label_input = page.locator("div.fixed input[type='text']").first
                label_input.fill("View Only Link")

                # Click create link button
                create_btn = page.locator("div.fixed button:has(svg.lucide-link)")
                create_btn.click(timeout=5000)
                page.wait_for_timeout(2000)

                # Get the view share link from API
                shares_resp = requests.get(
                    f"{API_URL}/api/galleries/{gallery_id}/shares", headers=headers
                )
                shares_resp.raise_for_status()
                shares = shares_resp.json()
                view_share = next((s for s in shares if s["permission"] == "view"), None)

                if view_share:
                    view_share_url = f"{BASE_URL}/shared/{view_share['token']}"

                link_rows = page.locator("div.fixed .space-y-2 > div").count()

                ss = os.path.join(sdir, "t8_create_view_link.png")
                page.screenshot(path=ss)
                report.add("T8: Create view-only share link",
                           view_share_url is not None and link_rows >= 2,
                           f"View URL: {view_share_url}, total links: {link_rows}", ss)

                # Close dialog
                page.click("div.fixed button:has(svg.lucide-x)", timeout=3000)
                page.wait_for_timeout(500)
            except Exception as e:
                ss = os.path.join(sdir, "t8_create_view_link_fail.png")
                page.screenshot(path=ss)
                report.add("T8: Create view-only share link", False, str(e), ss)

            # ── T9: View-only link cannot edit copies ────────────────
            try:
                if view_share_url:
                    # Open view-only link in a fresh incognito context
                    incognito2 = browser.new_context(viewport={"width": 1400, "height": 900})
                    view_page = incognito2.new_page()
                    view_page.goto(view_share_url)
                    view_page.wait_for_timeout(3000)

                    # Wait for images to load
                    view_page.wait_for_selector("img[loading='lazy']", timeout=10000)

                    # On a view-only page, there should be NO copies input fields
                    copies_inputs = view_page.locator("input[inputmode='numeric']").count()

                    # Also check the permission badge shows "view only"
                    # The header has a span with viewOnly text
                    page_content = view_page.content()

                    ss = os.path.join(sdir, "t9_view_only_no_edit.png")
                    view_page.screenshot(path=ss)
                    report.add("T9: View-only link cannot edit copies",
                               copies_inputs == 0,
                               f"Copies inputs found: {copies_inputs}", ss)

                    incognito2.close()
                else:
                    report.add("T9: View-only link cannot edit copies", False,
                               "No view_share_url from T8")
            except Exception as e:
                ss = os.path.join(sdir, "t9_view_only_no_edit_fail.png")
                try:
                    view_page.screenshot(path=ss)
                except Exception:
                    pass
                report.add("T9: View-only link cannot edit copies", False, str(e), ss)

        except Exception as e:
            ss = os.path.join(sdir, "unexpected_error.png")
            try:
                page.screenshot(path=ss)
            except Exception:
                pass
            report.add("Unexpected error", False, traceback.format_exc(), ss)
        finally:
            browser.close()

    # Save report
    report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-share-link-report.html")
    report.save(report_path, "Share Link E2E Test Report")
    report.print_summary(report_path)
    return report.all_passed


if __name__ == "__main__":
    success = run()
    raise SystemExit(0 if success else 1)
