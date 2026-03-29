"""
Selenium E2E test for shift-click range selection.
Registers a user, creates a gallery, uploads images, then tests selection.
Exports HTML report to Desktop.
"""

import io
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost"
API_URL = "http://localhost"

EMAIL = f"selenium-test-{int(time.time())}@example.com"
PASSWORD = "testpassword123"
FULL_NAME = "Selenium Tester"


def generate_test_image(name: str) -> tuple[str, bytes]:
    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return name, buf.getvalue()


class TestReport:
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()

    def add(self, name: str, passed: bool, detail: str = "", screenshot: str = ""):
        self.results.append({
            "name": name, "passed": passed, "detail": detail,
            "screenshot": screenshot, "time": datetime.now().isoformat(),
        })
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))

    def to_html(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        duration = (datetime.now() - self.start_time).total_seconds()
        rows = ""
        for r in self.results:
            color = "#d4edda" if r["passed"] else "#f8d7da"
            status = "PASS" if r["passed"] else "FAIL"
            ss = f'<br><img src="{r["screenshot"]}" style="max-width:600px;margin-top:8px;border:1px solid #ccc;border-radius:4px;">' if r["screenshot"] else ""
            rows += f'<tr style="background:{color}"><td style="padding:8px;border:1px solid #dee2e6;">{status}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["name"]}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["detail"]}{ss}</td></tr>'
        return f"""<!DOCTYPE html><html><head><title>Selenium Test Report</title></head>
<body style="font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;">
<h1>Selenium Test Report — Selection</h1>
<p>Date: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")} | Duration: {duration:.1f}s</p>
<p><strong>Total: {total}</strong> | <span style="color:green">Passed: {passed}</span> | <span style="color:red">Failed: {failed}</span></p>
<table style="width:100%;border-collapse:collapse;margin-top:20px;">
<tr style="background:#343a40;color:white;"><th style="padding:8px;border:1px solid #dee2e6;width:60px;">Status</th><th style="padding:8px;border:1px solid #dee2e6;">Test</th><th style="padding:8px;border:1px solid #dee2e6;">Detail</th></tr>
{rows}</table></body></html>"""


def screenshot(driver, name, report_dir):
    path = os.path.join(report_dir, f"{name}.png")
    driver.save_screenshot(path)
    return path


def count_selected(driver):
    return len(driver.find_elements(By.CSS_SELECTOR, "[class*='ring-blue']"))


def shift_click(driver, element):
    """Shift-click using ActionChains with explicit pauses."""
    ActionChains(driver)\
        .key_down(Keys.SHIFT)\
        .pause(0.1)\
        .click(element)\
        .pause(0.1)\
        .key_up(Keys.SHIFT)\
        .perform()


def ctrl_click(driver, element):
    """Ctrl-click using ActionChains with explicit pauses."""
    ActionChains(driver)\
        .key_down(Keys.CONTROL)\
        .pause(0.1)\
        .click(element)\
        .pause(0.1)\
        .key_up(Keys.CONTROL)\
        .perform()


def clear_selection(driver):
    """Click the X button in the selection bar to clear."""
    bars = driver.find_elements(By.CSS_SELECTOR, ".fixed.bottom-0 button")
    if bars:
        bars[0].click()
        time.sleep(0.5)


def get_checkboxes(driver):
    return driver.find_elements(By.CSS_SELECTOR, ".aspect-square .absolute")


def get_image_areas(driver):
    return driver.find_elements(By.CSS_SELECTOR, ".aspect-square")


def run_tests():
    report = TestReport()
    desktop = str(Path.home() / "Desktop")
    report_dir = os.path.join(desktop, "selenium-report")
    os.makedirs(report_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,900")

    print("Starting Chrome...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    wait = WebDriverWait(driver, 10)

    try:
        # --- Setup: Register, create gallery, upload images ---
        print("\n--- Setup ---")
        driver.get(f"{BASE_URL}/register")
        time.sleep(1)
        driver.find_element(By.ID, "fullName").send_keys(FULL_NAME)
        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        report.add("Register", "/register" not in driver.current_url, driver.current_url)

        # Create gallery
        buttons = driver.find_elements(By.CSS_SELECTOR, "button")
        for btn in buttons:
            if "+" in btn.text or "Nova" in btn.text or "New" in btn.text:
                btn.click()
                break
        time.sleep(1)
        driver.find_element(By.CSS_SELECTOR, "input[type='text']").send_keys("Selenium Gallery")
        driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
        time.sleep(2)

        # Navigate to gallery
        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='cursor-pointer'][class*='rounded-lg']")
        if cards:
            cards[0].click()
            time.sleep(2)

        gallery_id = driver.current_url.split("/gallery/")[1].split("?")[0]
        report.add("Setup gallery", bool(gallery_id), f"ID: {gallery_id}")

        # Upload via API
        import requests
        login_resp = requests.post(f"{API_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login_resp.json()["access_token"]
        files = [("files", (f"img_{i+1}.jpg", generate_test_image(f"img_{i+1}.jpg")[1], "image/jpeg")) for i in range(6)]
        upload_resp = requests.post(f"{API_URL}/api/galleries/{gallery_id}/images", headers={"Authorization": f"Bearer {token}"}, files=files)
        report.add("Upload 6 images", len(upload_resp.json().get("uploaded", [])) == 6)

        driver.refresh()
        time.sleep(3)

        # --- Test 1: Click checkbox on image 1 ---
        print("\n--- Selection Tests ---")
        cb = get_checkboxes(driver)
        report.add("Found 6 checkboxes", len(cb) >= 6, f"Found {len(cb)}")

        cb[0].click()
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T1: Click checkbox 1 -> 1 selected", sel == 1, f"Got {sel}",
                    screenshot(driver, "t1_click_cb1", report_dir))

        # --- Test 2: Shift+click checkbox 4 (range 1-4) ---
        cb = get_checkboxes(driver)
        shift_click(driver, cb[3])
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T2: Shift+click checkbox 4 -> 4 selected (range 1-4)", sel == 4, f"Got {sel}",
                    screenshot(driver, "t2_shift_cb4", report_dir))

        # --- Clear ---
        clear_selection(driver)
        time.sleep(0.5)

        # --- Test 3: Click checkbox 2 ---
        cb = get_checkboxes(driver)
        cb[1].click()
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T3: Click checkbox 2 -> 1 selected", sel == 1, f"Got {sel}",
                    screenshot(driver, "t3_click_cb2", report_dir))

        # --- Test 4: Shift+click checkbox 5 (range 2-5) ---
        cb = get_checkboxes(driver)
        shift_click(driver, cb[4])
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T4: Shift+click checkbox 5 -> 4 selected (range 2-5)", sel == 4, f"Got {sel}",
                    screenshot(driver, "t4_shift_cb5", report_dir))

        # --- Clear ---
        clear_selection(driver)
        time.sleep(0.5)

        # --- Test 5: Ctrl+click image area of image 1 ---
        areas = get_image_areas(driver)
        ctrl_click(driver, areas[0])
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T5: Ctrl+click image 1 -> 1 selected", sel == 1, f"Got {sel}",
                    screenshot(driver, "t5_ctrl_img1", report_dir))

        # --- Test 6: Shift+click image area of image 6 (range 1-6) ---
        areas = get_image_areas(driver)
        shift_click(driver, areas[5])
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T6: Shift+click image 6 -> 6 selected (range 1-6)", sel == 6, f"Got {sel}",
                    screenshot(driver, "t6_shift_img6", report_dir))

        # --- Clear ---
        clear_selection(driver)
        time.sleep(0.5)

        # --- Test 7: Click checkbox 3, shift+click checkbox 6 ---
        cb = get_checkboxes(driver)
        cb[2].click()
        time.sleep(0.3)
        cb = get_checkboxes(driver)
        shift_click(driver, cb[5])
        time.sleep(0.5)
        sel = count_selected(driver)
        report.add("T7: Click cb3, shift+click cb6 -> 4 selected (range 3-6)", sel == 4, f"Got {sel}",
                    screenshot(driver, "t7_cb3_shift_cb6", report_dir))

    except Exception as e:
        report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        screenshot(driver, "error", report_dir)
    finally:
        driver.quit()

    report_path = os.path.join(desktop, "selenium-report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.to_html())

    total = len(report.results)
    passed = sum(1 for r in report.results if r["passed"])
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"Report: {report_path}")
    print(f"Screenshots: {report_dir}")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
