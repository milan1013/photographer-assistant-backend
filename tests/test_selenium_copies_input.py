"""
Selenium E2E test for copy count input behavior.
Tests that users can clear '0' and type a new number without getting '01'.
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
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost"
API_URL = "http://localhost"

EMAIL = f"copies-{int(time.time())}@test.com"
PASSWORD = "testpassword"


def make_image() -> bytes:
    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class Report:
    def __init__(self):
        self.results = []
        self.start = datetime.now()

    def add(self, name, passed, detail="", ss=""):
        self.results.append({"name": name, "passed": passed, "detail": detail, "ss": ss})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))

    def html(self):
        total = len(self.results)
        p = sum(1 for r in self.results if r["passed"])
        dur = (datetime.now() - self.start).total_seconds()
        rows = ""
        for r in self.results:
            c = "#d4edda" if r["passed"] else "#f8d7da"
            s = "PASS" if r["passed"] else "FAIL"
            img = f'<br><img src="{r["ss"]}" style="max-width:600px;margin-top:8px;border:1px solid #ccc;border-radius:4px;">' if r["ss"] else ""
            rows += f'<tr style="background:{c}"><td style="padding:8px;border:1px solid #dee2e6;">{s}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["name"]}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["detail"]}{img}</td></tr>'
        return f"""<!DOCTYPE html><html><head><title>Copies Input Test</title></head>
<body style="font-family:system-ui;max-width:900px;margin:40px auto;padding:0 20px;">
<h1>Selenium Test Report - Copies Input Behavior</h1>
<p>Date: {self.start.strftime("%Y-%m-%d %H:%M:%S")} | Duration: {dur:.1f}s</p>
<p><strong>Total: {total}</strong> | <span style="color:green">Passed: {p}</span> | <span style="color:red">Failed: {total-p}</span></p>
<table style="width:100%;border-collapse:collapse;margin-top:20px;">
<tr style="background:#343a40;color:white;"><th style="padding:8px;border:1px solid #dee2e6;width:60px;">Status</th><th style="padding:8px;border:1px solid #dee2e6;">Test</th><th style="padding:8px;border:1px solid #dee2e6;">Detail</th></tr>
{rows}</table></body></html>"""


def ss(driver, name, d):
    p = os.path.join(d, f"{name}.png")
    driver.save_screenshot(p)
    return p


def run():
    report = Report()
    desktop = str(Path.home() / "Desktop")
    sdir = os.path.join(desktop, "selenium-copies-report")
    os.makedirs(sdir, exist_ok=True)

    import requests

    # Setup: register, create gallery, upload images
    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "full_name": "Copies Tester",
    })
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    g = requests.post(f"{API_URL}/api/galleries", json={"name": "Copies Test"}, headers=h).json()
    gid = g["id"]
    files = [("files", (f"img{i}.jpg", make_image(), "image/jpeg")) for i in range(3)]
    requests.post(f"{API_URL}/api/galleries/{gid}/images", headers=h, files=files)

    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,900")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Login
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        # Navigate to gallery
        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='cursor-pointer'][class*='rounded-lg']")
        if cards:
            cards[0].click()
            time.sleep(3)

        # --- T1: Thumbnail copies input - clear and type ---
        print("\n--- Thumbnail Copies Input ---")
        copies_inputs = driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric']")
        report.add("T1: Found copies inputs", len(copies_inputs) >= 3, f"Found {len(copies_inputs)}")

        if len(copies_inputs) >= 1:
            inp = copies_inputs[0]
            inp.click()
            time.sleep(0.3)

            # Select all and delete
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(Keys.DELETE)
            time.sleep(0.2)
            val_after_clear = inp.get_attribute("value")
            report.add("T2: Can clear input to empty", val_after_clear == "", f"Value after clear: '{val_after_clear}'", ss(driver, "t2", sdir))

            # Type '5'
            inp.send_keys("5")
            time.sleep(0.2)
            val_after_type = inp.get_attribute("value")
            report.add("T3: Type '5' shows '5' not '05'", val_after_type == "5", f"Value: '{val_after_type}'", ss(driver, "t3", sdir))

            # Clear and type '12'
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(Keys.DELETE)
            inp.send_keys("12")
            time.sleep(0.2)
            val_twelve = inp.get_attribute("value")
            report.add("T4: Type '12' shows '12'", val_twelve == "12", f"Value: '{val_twelve}'", ss(driver, "t4", sdir))

        # --- T5: Batch copies input ---
        print("\n--- Batch Copies Input ---")
        # Select images first
        checkboxes = driver.find_elements(By.CSS_SELECTOR, ".aspect-square .absolute")
        if len(checkboxes) >= 2:
            checkboxes[0].click()
            time.sleep(0.3)
            checkboxes[1].click()
            time.sleep(0.5)

        # Find batch input in selection bar
        batch_inputs = driver.find_elements(By.CSS_SELECTOR, ".fixed.bottom-0 input[inputmode='numeric']")
        report.add("T5: Found batch copies input", len(batch_inputs) >= 1, f"Found {len(batch_inputs)}")

        if len(batch_inputs) >= 1:
            batch_inp = batch_inputs[0]
            batch_inp.click()
            time.sleep(0.3)

            # Select all and delete
            batch_inp.send_keys(Keys.CONTROL + "a")
            batch_inp.send_keys(Keys.DELETE)
            time.sleep(0.2)
            batch_cleared = batch_inp.get_attribute("value")
            report.add("T6: Can clear batch input", batch_cleared == "", f"Value: '{batch_cleared}'", ss(driver, "t6", sdir))

            # Type '3'
            batch_inp.send_keys("3")
            time.sleep(0.2)
            batch_typed = batch_inp.get_attribute("value")
            report.add("T7: Batch input type '3' shows '3' not '03'", batch_typed == "3", f"Value: '{batch_typed}'", ss(driver, "t7", sdir))

        # --- T8: Viewer copies input ---
        print("\n--- Viewer Copies Input ---")
        # Clear selection first
        x_btns = driver.find_elements(By.CSS_SELECTOR, ".fixed.bottom-0 button")
        if x_btns:
            x_btns[0].click()
            time.sleep(0.5)

        # Click image to open viewer
        image_areas = driver.find_elements(By.CSS_SELECTOR, ".aspect-square")
        if image_areas:
            image_areas[0].click()
            time.sleep(1)

        viewer_inputs = driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric']")
        # The viewer input should be the one in the bottom bar
        viewer_inp = None
        for vi in viewer_inputs:
            if vi.is_displayed() and vi.get_attribute("class") and "w-20" in (vi.get_attribute("class") or ""):
                viewer_inp = vi
                break

        if viewer_inp:
            viewer_inp.click()
            time.sleep(0.3)
            viewer_inp.send_keys(Keys.CONTROL + "a")
            viewer_inp.send_keys(Keys.DELETE)
            time.sleep(0.2)
            viewer_cleared = viewer_inp.get_attribute("value")
            report.add("T8: Can clear viewer input", viewer_cleared == "", f"Value: '{viewer_cleared}'", ss(driver, "t8", sdir))

            viewer_inp.send_keys("7")
            time.sleep(0.2)
            viewer_typed = viewer_inp.get_attribute("value")
            report.add("T9: Viewer input type '7' shows '7' not '07'", viewer_typed == "7", f"Value: '{viewer_typed}'", ss(driver, "t9", sdir))
        else:
            report.add("T8: Viewer input found", False, "Could not find viewer copies input")
            report.add("T9: Viewer input typing", False, "Skipped")

    except Exception as e:
        report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        ss(driver, "error", sdir)
    finally:
        driver.quit()

    path = os.path.join(desktop, "selenium-copies-report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report.html())

    total = len(report.results)
    passed = sum(1 for r in report.results if r["passed"])
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"Report: {path}")
    return passed == total


if __name__ == "__main__":
    exit(0 if run() else 1)
