"""
Playwright E2E test for email verification flow.
Tests: register sends verify email, verify link works, invalid token rejected,
resend verification, already verified handled.
"""

import os
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import (
    API_URL, BASE_URL, TestReport, get_token_from_logs,
    register_user, report_dir, DEFAULT_PASSWORD,
)

EMAIL = f"verify-{int(time.time())}@test.com"
PASSWORD = DEFAULT_PASSWORD


def run():
    import requests

    report = TestReport()
    sdir = report_dir("e2e-email-verify-report")

    # --- Setup: Register via API (returns token, avoids login rate limit) ---
    print("\n--- Setup ---")
    access_token, h = register_user(EMAIL, PASSWORD, "Verify Tester")
    report.add("Setup: User registered", bool(access_token))

    time.sleep(1)
    verify_token = get_token_from_logs("Verify link")
    report.add("T1: Verification token generated on register", bool(verify_token))

    # --- T2: User is not verified after registration ---
    me_resp = requests.get(f"{API_URL}/api/auth/me", headers=h).json()
    report.add("T2: User not verified after registration",
                me_resp.get("email_verified") is False,
                f"email_verified={me_resp.get('email_verified')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # --- T3: Visit verify-email page with valid token ---
            print("\n--- Email Verification ---")
            verify_url = f"{BASE_URL}/verify-email?token={verify_token}"
            page.goto(verify_url)
            page.wait_for_timeout(3000)

            success_icons = page.query_selector_all(".text-green-500")
            page_text = page.inner_text("body").lower()
            ss3 = os.path.join(sdir, "t3_verified.png")
            page.screenshot(path=ss3)
            report.add("T3: Verification page shows success",
                        len(success_icons) > 0 or "verified" in page_text or "potvrd" in page_text,
                        ss=ss3)

            # --- T4: User is now verified (API check) ---
            me_resp2 = requests.get(f"{API_URL}/api/auth/me", headers=h).json()
            report.add("T4: User verified after clicking link",
                        me_resp2.get("email_verified") is True,
                        f"email_verified={me_resp2.get('email_verified')}")

            # --- T5: Dashboard link visible on success page ---
            dashboard_links = page.query_selector_all("a[href='/']")
            ss5 = os.path.join(sdir, "t5_dashboard_link.png")
            page.screenshot(path=ss5)
            report.add("T5: Dashboard link visible on success page",
                        len(dashboard_links) > 0, ss=ss5)

            # --- T6: Using same token again still works (idempotent) ---
            page.goto(verify_url)
            page.wait_for_timeout(3000)
            success_icons2 = page.query_selector_all(".text-green-500")
            ss6 = os.path.join(sdir, "t6_reuse_token.png")
            page.screenshot(path=ss6)
            report.add("T6: Re-using token is idempotent (no error)",
                        len(success_icons2) > 0, ss=ss6)

            # --- T7: Invalid token shows error ---
            page.goto(f"{BASE_URL}/verify-email?token=invalid-token-xyz")
            page.wait_for_timeout(3000)
            error_icons = page.query_selector_all(".text-destructive")
            ss7 = os.path.join(sdir, "t7_invalid_token.png")
            page.screenshot(path=ss7)
            report.add("T7: Invalid token shows error",
                        len(error_icons) > 0, ss=ss7)

            # --- T8: No token shows error ---
            page.goto(f"{BASE_URL}/verify-email")
            page.wait_for_timeout(3000)
            error_icons2 = page.query_selector_all(".text-destructive")
            ss8 = os.path.join(sdir, "t8_no_token.png")
            page.screenshot(path=ss8)
            report.add("T8: No token shows error",
                        len(error_icons2) > 0, ss=ss8)

            # --- T9: Resend verification for already-verified user ---
            time.sleep(5)  # avoid rate limit
            resend_resp = requests.post(f"{API_URL}/api/auth/resend-verification", headers=h)
            report.add("T9: Resend for verified user succeeds",
                        resend_resp.status_code == 200,
                        f"HTTP {resend_resp.status_code}")

            # --- T10: Register new unverified user and test resend ---
            time.sleep(10)  # avoid register rate limit
            email2 = f"verify2-{int(time.time())}@test.com"
            reg2_resp = requests.post(f"{API_URL}/api/auth/register", json={
                "email": email2, "password": PASSWORD, "full_name": "Verify Tester 2",
            })
            if reg2_resp.status_code == 429:
                time.sleep(20)
                reg2_resp = requests.post(f"{API_URL}/api/auth/register", json={
                    "email": email2, "password": PASSWORD, "full_name": "Verify Tester 2",
                })
            access_token2 = reg2_resp.json().get("access_token", "")
            h2 = {"Authorization": f"Bearer {access_token2}"}
            report.add("T10: Second user registered", reg2_resp.status_code == 201,
                        f"HTTP {reg2_resp.status_code}")

            time.sleep(5)  # avoid rate limit
            resend2 = requests.post(f"{API_URL}/api/auth/resend-verification", headers=h2)
            report.add("T11: Resend verification for unverified user",
                        resend2.status_code == 200,
                        f"HTTP {resend2.status_code}")

            # --- T12: Verify the resent token works ---
            time.sleep(1)
            resent_token = get_token_from_logs("Verify link")
            report.add("T12: Resent verification token found", bool(resent_token))

            if resent_token:
                page.goto(f"{BASE_URL}/verify-email?token={resent_token}")
                page.wait_for_timeout(3000)
                success_icons3 = page.query_selector_all(".text-green-500")
                ss13 = os.path.join(sdir, "t13_resent_verified.png")
                page.screenshot(path=ss13)
                report.add("T13: Resent token verifies successfully",
                            len(success_icons3) > 0, ss=ss13)

                me3 = requests.get(f"{API_URL}/api/auth/me", headers=h2).json()
                report.add("T14: Second user now verified",
                            me3.get("email_verified") is True,
                            f"email_verified={me3.get('email_verified')}")
            else:
                report.add("T13: Resent token verifies successfully", False, "No token found")
                report.add("T14: Second user now verified", False, "Skipped")

        except Exception as e:
            report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            page.screenshot(path=os.path.join(sdir, "error.png"))
        finally:
            browser.close()

    path = os.path.join(str(Path(__file__).resolve().parent), "reports", "e2e-email-verify-report.html")
    report.save(path, "Email Verification Test Report")
    report.print_summary(path)
    return report.all_passed


if __name__ == "__main__":
    exit(0 if run() else 1)
