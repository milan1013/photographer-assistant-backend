"""
Playwright E2E test for 'Show more' / 'Show less' on shared gallery description.
Tests: long description is truncated with a 'Show more' button,
       clicking it expands the text, clicking 'Show less' collapses it.
       Short description has no button.
"""

import os
import subprocess
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import BASE_URL, TestReport, report_dir

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

LONG_DESC = (
    "This is a very long gallery description that should definitely exceed "
    "the one hundred and fifty character limit set for truncation. "
    "We add even more text here to make absolutely sure it triggers the show more button. "
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
)
SHORT_DESC = "Short description."


def _db_exec(sql: str) -> str:
    """Run SQL via docker exec on the DB container."""
    result = subprocess.run(
        ["docker", "exec", "photographer-assistant-web-db-1",
         "psql", "-U", "postgres", "-d", "photographer_assistant",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    out = result.stdout.strip()
    # psql -t -A with RETURNING outputs value followed by "INSERT 0 1" line
    lines = [l for l in out.splitlines() if l and not l.startswith("INSERT ")]
    return lines[0] if lines else ""


def _setup_test_gallery(description: str, name: str) -> str | None:
    """Create a gallery + share link directly in DB. Returns share token."""
    # Get any existing user
    user_id = _db_exec("SELECT id FROM users LIMIT 1;")
    if not user_id:
        return None

    # Create gallery with description
    gallery_id = _db_exec(
        f"INSERT INTO galleries (id, owner_id, name, description, created_at, updated_at) "
        f"VALUES (gen_random_uuid(), '{user_id}', '{name}', $${description}$$, now(), now()) "
        f"RETURNING id;"
    )
    if not gallery_id:
        return None

    # Create share link
    import secrets
    token = secrets.token_urlsafe(32)
    _db_exec(
        f"INSERT INTO share_links (id, gallery_id, token, permission, label, is_active, created_at) "
        f"VALUES (gen_random_uuid(), '{gallery_id}', '{token}', 'view', 'e2e-test', true, now());"
    )
    return token


def run() -> bool:
    report = TestReport()
    sdir = report_dir("e2e-show-more-report")

    # ── Setup: Create test galleries via DB ──
    token_long = None
    token_short = None
    try:
        token_long = _setup_test_gallery(LONG_DESC, "ShowMore Long Desc")
        token_short = _setup_test_gallery(SHORT_DESC, "ShowMore Short Desc")
        report.add("T0: Setup (create test galleries)",
                    token_long is not None and token_short is not None,
                    f"Long token: {token_long}, Short token: {token_short}")
    except Exception as e:
        report.add("T0: Setup", False, traceback.format_exc())
        report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-show-more-report.html")
        report.save(report_path, "Show More E2E Test Report")
        report.print_summary(report_path)
        return report.all_passed

    if not token_long or not token_short:
        report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-show-more-report.html")
        report.save(report_path, "Show More E2E Test Report")
        report.print_summary(report_path)
        return report.all_passed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # ── T1: Long description shows truncated with 'Show more' button ──
            try:
                page.goto(f"{BASE_URL}/shared/{token_long}")
                page.wait_for_timeout(3000)

                desc_p = page.locator("main p.text-muted-foreground").first
                desc_p.wait_for(state="visible", timeout=10000)
                desc_text = desc_p.inner_text()

                show_more_btn = desc_p.locator("button")
                has_show_more = show_more_btn.count() > 0
                is_truncated = "\u2026" in desc_text

                ss = os.path.join(sdir, "t1_truncated.png")
                page.screenshot(path=ss)
                report.add("T1: Long description is truncated with 'Show more'",
                           is_truncated and has_show_more,
                           f"Truncated: {is_truncated}, Button: {has_show_more}, "
                           f"Text length: {len(desc_text)}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t1_truncated_fail.png")
                page.screenshot(path=ss)
                report.add("T1: Long description is truncated", False, str(e), ss)

            # ── T2: Clicking 'Show more' expands the full text ──
            try:
                show_more_btn = page.locator("main p.text-muted-foreground button").first
                btn_text_before = show_more_btn.inner_text()
                show_more_btn.click()
                page.wait_for_timeout(500)

                desc_text_expanded = page.locator("main p.text-muted-foreground").first.inner_text()
                is_expanded = len(desc_text_expanded) > len(desc_text)

                btn_text_after = page.locator("main p.text-muted-foreground button").first.inner_text()
                button_changed = btn_text_before != btn_text_after

                ss = os.path.join(sdir, "t2_expanded.png")
                page.screenshot(path=ss)
                report.add("T2: Click 'Show more' expands text",
                           is_expanded and button_changed,
                           f"Expanded: {is_expanded}, Button changed: {button_changed} "
                           f"('{btn_text_before}' -> '{btn_text_after}')", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t2_expanded_fail.png")
                page.screenshot(path=ss)
                report.add("T2: Click 'Show more' expands text", False, str(e), ss)

            # ── T3: Clicking 'Show less' collapses back ──
            try:
                show_less_btn = page.locator("main p.text-muted-foreground button").first
                show_less_btn.click()
                page.wait_for_timeout(500)

                desc_text_collapsed = page.locator("main p.text-muted-foreground").first.inner_text()
                is_collapsed = "\u2026" in desc_text_collapsed

                ss = os.path.join(sdir, "t3_collapsed.png")
                page.screenshot(path=ss)
                report.add("T3: Click 'Show less' collapses text",
                           is_collapsed,
                           f"Collapsed again: {is_collapsed}", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t3_collapsed_fail.png")
                page.screenshot(path=ss)
                report.add("T3: Click 'Show less' collapses text", False, str(e), ss)

            # ── T4: Short description has NO 'Show more' button ──
            try:
                page.goto(f"{BASE_URL}/shared/{token_short}")
                page.wait_for_timeout(3000)

                desc_p = page.locator("main p.text-muted-foreground").first
                desc_p.wait_for(state="visible", timeout=10000)
                desc_text_short = desc_p.inner_text()

                show_more_btns = desc_p.locator("button").count()
                no_truncation = "\u2026" not in desc_text_short

                ss = os.path.join(sdir, "t4_short_no_button.png")
                page.screenshot(path=ss)
                report.add("T4: Short description has no 'Show more'",
                           show_more_btns == 0 and no_truncation,
                           f"Buttons: {show_more_btns}, No ellipsis: {no_truncation}, "
                           f"Text: '{desc_text_short}'", ss)
            except Exception as e:
                ss = os.path.join(sdir, "t4_short_no_button_fail.png")
                page.screenshot(path=ss)
                report.add("T4: Short description has no 'Show more'", False, str(e), ss)

        except Exception as e:
            ss = os.path.join(sdir, "unexpected_error.png")
            try:
                page.screenshot(path=ss)
            except Exception:
                pass
            report.add("Unexpected error", False, traceback.format_exc(), ss)
        finally:
            browser.close()

    # Cleanup test data
    try:
        _db_exec(f"DELETE FROM share_links WHERE token = '{token_long}';")
        _db_exec(f"DELETE FROM share_links WHERE token = '{token_short}';")
        _db_exec("DELETE FROM galleries WHERE name LIKE 'ShowMore %';")
    except Exception:
        pass

    report_path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-show-more-report.html")
    report.save(report_path, "Show More E2E Test Report")
    report.print_summary(report_path)
    return report.all_passed


if __name__ == "__main__":
    success = run()
    raise SystemExit(0 if success else 1)
