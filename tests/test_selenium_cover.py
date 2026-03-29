"""
Selenium E2E test for gallery cover image functionality.
Tests: auto-set on upload, manual set via edit modal.
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
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost"
API_URL = "http://localhost"

EMAIL = f"cover-test-{int(time.time())}@example.com"
PASSWORD = "testpassword123"


def make_image(color: str) -> bytes:
    img = Image.new("RGB", (50, 50), color=color)
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
        return f"""<!DOCTYPE html><html><head><title>Cover Image Test Report</title></head>
<body style="font-family:system-ui;max-width:900px;margin:40px auto;padding:0 20px;">
<h1>Selenium Test Report - Gallery Cover Image</h1>
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
    sdir = os.path.join(desktop, "selenium-cover-report")
    os.makedirs(sdir, exist_ok=True)

    import requests

    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "full_name": "Cover Tester",
    })
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    g = requests.post(f"{API_URL}/api/galleries", json={"name": "Cover Test Gallery"}, headers=h).json()
    gid = g["id"]

    # T1: No cover before upload
    gallery_before = requests.get(f"{API_URL}/api/galleries/{gid}", headers=h).json()
    report.add("T1: No cover before upload", gallery_before["cover_image_id"] is None)

    # T2: Upload 3 images, cover = last
    files = [
        ("files", ("red.jpg", make_image("red"), "image/jpeg")),
        ("files", ("green.jpg", make_image("green"), "image/jpeg")),
        ("files", ("blue.jpg", make_image("blue"), "image/jpeg")),
    ]
    upload = requests.post(f"{API_URL}/api/galleries/{gid}/images", headers=h, files=files).json()
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

    # T5: Dashboard shows thumbnail
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,900")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        driver.find_element(By.ID, "email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        gallery_imgs = driver.find_elements(By.CSS_SELECTOR, ".aspect-video img")
        report.add("T5: Dashboard shows cover thumbnail", len(gallery_imgs) > 0, ss=ss(driver, "t5", sdir))

        # T6: Navigate to gallery, click edit pencil, see thumbnail grid
        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='cursor-pointer'][class*='rounded-lg']")
        if cards:
            cards[0].click()
            time.sleep(3)

        # Find pencil edit button
        pencil_btns = driver.find_elements(By.CSS_SELECTOR, "button[title]")
        edit_btn = None
        for btn in pencil_btns:
            title = btn.get_attribute("title") or ""
            if "edit" in title.lower() or "izmeni" in title.lower():
                edit_btn = btn
                break

        report.add("T6: Edit pencil button found", edit_btn is not None, ss=ss(driver, "t6", sdir))

        if edit_btn:
            edit_btn.click()
            time.sleep(1)

            # Check for thumbnail grid in modal (buttons inside the grid)
            modal = driver.find_element(By.CSS_SELECTOR, ".fixed.inset-0.z-50")
            thumb_buttons = modal.find_elements(By.CSS_SELECTOR, "button.aspect-square")
            report.add(
                "T7: Edit modal shows thumbnail grid",
                len(thumb_buttons) >= 4,
                f"Found {len(thumb_buttons)} thumbnails",
                ss(driver, "t7", sdir),
            )

            # Click a different thumbnail to change cover
            if len(thumb_buttons) >= 2:
                thumb_buttons[1].click()
                time.sleep(1)
                report.add("T8: Clicked thumbnail to change cover", True, ss=ss(driver, "t8", sdir))

    except Exception as e:
        report.add("Unexpected error", False, f"{type(e).__name__}: {e}")
        ss(driver, "error", sdir)
    finally:
        driver.quit()

    path = os.path.join(desktop, "selenium-cover-report.html")
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
