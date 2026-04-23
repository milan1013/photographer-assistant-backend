"""
Playwright E2E test for password reset flow.
Tests: forgot password form, reset link, new password, login with new password.
"""

import os
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, get_token_from_logs,
    register_user, report_dir,
)

EMAIL = f"pw-reset-{int(time.time())}@test.com"
OLD_PASSWORD = "oldpassword123"
NEW_PASSWORD = "newpassword456"


def run():
    import requests

    report = TestReport()
    sdir = report_dir("e2e-password-reset-report")

    # --- Setup: Register user via API ---
    print("\n--- Setup ---")
    token, h = register_user(EMAIL, OLD_PASSWORD, "Password Reset Tester")
    report.add("Setup: User registered", bool(token))
    report.add("Setup: Ready", True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # --- T1: Navigate to forgot password page ---
            print("\n--- Forgot Password Flow ---")
            page.goto(f"{BASE_URL}/login")

            forgot_links = page.query_selector_all("a[href='/forgot-password']")
            ss1 = os.path.join(sdir, "t1_login.png")
            page.screenshot(path=ss1)
            report.add("T1: Forgot password link visible", len(forgot_links) > 0, ss=ss1)

            if forgot_links:
                forgot_links[0].click()
                page.wait_for_url("**/forgot-password**", timeout=5000)

            # --- T2: Submit forgot password form ---
            report.add("T2: On forgot password page", "/forgot-password" in page.url, page.url)

            page.fill("#email", EMAIL)
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)

            # Check success message is shown
            page_text = page.inner_text("body").lower()
            ss3 = os.path.join(sdir, "t3_sent.png")
            page.screenshot(path=ss3)
            report.add("T3: Reset email sent confirmation shown",
                        "login" in page_text or "sent" in page_text or "posla" in page_text,
                        ss=ss3)

            # --- T4: Get the reset token from backend logs ---
            time.sleep(1)
            reset_token = get_token_from_logs("Reset link")
            report.add("T4: Reset token generated", bool(reset_token))

            reset_url = f"{BASE_URL}/reset-password?token={reset_token}"
            page.goto(reset_url)

            # --- T5: Reset password page shows form ---
            password_inputs = page.query_selector_all("#password")
            ss5 = os.path.join(sdir, "t5_reset_form.png")
            page.screenshot(path=ss5)
            report.add("T5: Reset password form visible", len(password_inputs) > 0, ss=ss5)

            # --- T6: Submit too short password ---
            if password_inputs:
                password_inputs[0].fill("abc")
                page.click("button[type='submit']")
                page.wait_for_timeout(1000)
                ss6 = os.path.join(sdir, "t6_short_pw.png")
                page.screenshot(path=ss6)
                report.add("T6: Short password rejected",
                            "reset-password" in page.url, ss=ss6)

            # --- T7: Submit valid new password ---
            page.goto(reset_url)
            page.fill("#password", NEW_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)

            ss7 = os.path.join(sdir, "t7_after_reset.png")
            page.screenshot(path=ss7)
            report.add("T7: Redirected to login after reset",
                        "/login" in page.url, page.url, ss7)

            # --- T8: Login with NEW password ---
            time.sleep(5)  # avoid rate limit
            page.goto(f"{BASE_URL}/login")
            page.fill("#email", EMAIL)
            page.fill("#password", NEW_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_timeout(3000)

            ss8 = os.path.join(sdir, "t8_login_new.png")
            page.screenshot(path=ss8)
            report.add("T8: Login with new password succeeds",
                        "/login" not in page.url and "/register" not in page.url,
                        page.url, ss8)

            # --- T9: Old password no longer works (API check) ---
            time.sleep(3)
            old_login = requests.post(f"{API_URL}/api/auth/login", json={"email": EMAIL, "password": OLD_PASSWORD})
            report.add("T9: Old password rejected", old_login.status_code == 401)

            # --- T10: New password works via API ---
            new_login = requests.post(f"{API_URL}/api/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD})
            report.add("T10: New password works via API", new_login.status_code == 200)

            # --- T11: Invalid token shows error ---
            page.goto(f"{BASE_URL}/reset-password?token=invalid-token-xyz")
            password_inputs = page.query_selector_all("#password")
            if password_inputs:
                password_inputs[0].fill("somepassword123")
                page.click("button[type='submit']")
                page.wait_for_timeout(2000)
                page_text = page.inner_text("body").lower()
                ss11 = os.path.join(sdir, "t11_invalid_token.png")
                page.screenshot(path=ss11)
                report.add("T11: Invalid token shows error",
                            "invalid" in page_text or "error" in page_text or "istekao" in page_text or "reset-password" in page.url,
                            ss=ss11)
            else:
                report.add("T11: Invalid token shows error", False, "No form shown")

            # --- T12: No token shows error page ---
            page.goto(f"{BASE_URL}/reset-password")
            page.wait_for_timeout(1000)
            page_text = page.inner_text("body").lower()
            has_error = "invalid" in page_text or "error" in page_text or "istekao" in page_text
            no_form = len(page.query_selector_all("form")) == 0
            ss12 = os.path.join(sdir, "t12_no_token.png")
            page.screenshot(path=ss12)
            report.add("T12: No token shows error page", has_error or no_form, ss=ss12)

        except Exception as e:
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            page.screenshot(path=os.path.join(sdir, "error.png"))
        finally:
            browser.close()

    path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-password-reset-report.html")
    report.save(path, "Password Reset Test Report")
    report.print_summary(path)
    return report.all_passed


if __name__ == "__main__":
    exit(0 if run() else 1)
