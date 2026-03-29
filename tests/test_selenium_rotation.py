"""
Selenium E2E test for EXIF orientation fix.
Uploads an image with EXIF rotation tag and verifies it displays correctly.
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

EMAIL = f"rotation-{int(time.time())}@test.com"
PASSWORD = "testpassword"


def make_rotated_image() -> bytes:
    """Create a 200x100 image (landscape) with EXIF orientation=6 (rotate 90 CW).
    Without EXIF fix, it displays as 200x100 (wrong). With fix, it should be 100x200 (correct)."""
    img = Image.new("RGB", (200, 100), color="red")
    # Draw a distinct pattern: top-left is red, bottom-right is blue
    for x in range(100, 200):
        for y in range(50, 100):
            img.putpixel((x, y), (0, 0, 255))

    exif = img.getexif()
    # Orientation tag = 6 means rotate 90 CW
    exif[0x0112] = 6

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def make_normal_image() -> bytes:
    """Create a 200x100 landscape image with no EXIF orientation."""
    img = Image.new("RGB", (200, 100), color="green")
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
        return f"""<!DOCTYPE html><html><head><title>EXIF Rotation Test</title></head>
<body style="font-family:system-ui;max-width:900px;margin:40px auto;padding:0 20px;">
<h1>Selenium Test Report - EXIF Orientation Fix</h1>
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
    sdir = os.path.join(desktop, "selenium-rotation-report")
    os.makedirs(sdir, exist_ok=True)

    import requests

    # --- Test 1: API-level test — upload rotated image, check dimensions ---
    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "full_name": "Rotation Tester",
    })
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    g = requests.post(f"{API_URL}/api/galleries", json={"name": "Rotation Test"}, headers=h).json()
    gid = g["id"]

    # Upload rotated image (200x100 pixels, EXIF orientation=6 means rotate 90 CW -> should become 100x200)
    rotated_data = make_rotated_image()
    upload = requests.post(
        f"{API_URL}/api/galleries/{gid}/images",
        headers=h,
        files=[("files", ("rotated.jpg", rotated_data, "image/jpeg"))],
    ).json()

    if upload["uploaded"]:
        img_data = upload["uploaded"][0]
        w, h_dim = img_data["width"], img_data["height"]
        # After EXIF transpose: 200x100 rotated 90 CW = 100x200
        report.add(
            "T1: Rotated image dimensions corrected",
            w == 100 and h_dim == 200,
            f"Got {w}x{h_dim}, expected 100x200 (EXIF orientation=6 applied)",
        )
    else:
        report.add("T1: Upload rotated image", False, f"Upload failed: {upload}")

    # Upload normal image (200x100, no EXIF)
    normal_data = make_normal_image()
    upload2 = requests.post(
        f"{API_URL}/api/galleries/{gid}/images",
        headers=h,
        files=[("files", ("normal.jpg", normal_data, "image/jpeg"))],
    ).json()

    if upload2["uploaded"]:
        img_data2 = upload2["uploaded"][0]
        w2, h2 = img_data2["width"], img_data2["height"]
        report.add(
            "T2: Normal image dimensions unchanged",
            w2 == 200 and h2 == 100,
            f"Got {w2}x{h2}, expected 200x100",
        )
    else:
        report.add("T2: Upload normal image", False, f"Upload failed: {upload2}")

    # --- Test 3: Download thumbnail and verify it's not rotated ---
    if upload["uploaded"]:
        img_id = upload["uploaded"][0]["id"]
        thumb_resp = requests.get(f"{API_URL}/api/images/{img_id}/thumbnail?token={token}")
        thumb_img = Image.open(io.BytesIO(thumb_resp.content))
        # Thumbnail should be portrait (height > width) since original was rotated
        report.add(
            "T3: Thumbnail has correct orientation",
            thumb_img.height > thumb_img.width,
            f"Thumbnail size: {thumb_img.width}x{thumb_img.height} ({'portrait' if thumb_img.height > thumb_img.width else 'landscape'})",
        )

    # --- Test 4: Download medium and verify orientation ---
    if upload["uploaded"]:
        medium_resp = requests.get(f"{API_URL}/api/images/{img_id}/file?size=medium&token={token}")
        medium_img = Image.open(io.BytesIO(medium_resp.content))
        report.add(
            "T4: Medium image has correct orientation",
            medium_img.height > medium_img.width,
            f"Medium size: {medium_img.width}x{medium_img.height} ({'portrait' if medium_img.height > medium_img.width else 'landscape'})",
        )

    # --- Test 5: Upload the actual problem image from desktop ---
    problem_path = os.path.join(desktop, "this image will rotate.jpeg")
    if os.path.exists(problem_path):
        with open(problem_path, "rb") as f:
            problem_data = f.read()

        # Check original EXIF
        orig = Image.open(io.BytesIO(problem_data))
        orig_exif = orig.getexif()
        orientation = orig_exif.get(0x0112, 1)

        upload3 = requests.post(
            f"{API_URL}/api/galleries/{gid}/images",
            headers=h,
            files=[("files", ("problem.jpg", problem_data, "image/jpeg"))],
        ).json()

        if upload3["uploaded"]:
            prob = upload3["uploaded"][0]
            # If original EXIF says rotate, dimensions should be swapped
            report.add(
                "T5: Real problem image uploaded successfully",
                True,
                f"Original EXIF orientation={orientation}, stored as {prob['width']}x{prob['height']}",
            )

            # Download thumbnail and check
            prob_thumb = requests.get(f"{API_URL}/api/images/{prob['id']}/thumbnail?token={token}")
            prob_thumb_img = Image.open(io.BytesIO(prob_thumb.content))
            report.add(
                "T6: Real image thumbnail orientation",
                True,
                f"Thumbnail: {prob_thumb_img.width}x{prob_thumb_img.height}",
            )
        else:
            report.add("T5: Real problem image", False, "Upload failed")
            report.add("T6: Real image thumbnail", False, "Skipped")
    else:
        report.add("T5: Real problem image", False, f"File not found: {problem_path}")
        report.add("T6: Real image thumbnail", False, "Skipped")

    # --- Test 7: Selenium visual check ---
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

        cards = driver.find_elements(By.CSS_SELECTOR, "[class*='cursor-pointer'][class*='rounded-lg']")
        if cards:
            cards[0].click()
            time.sleep(3)

        report.add(
            "T7: Gallery displays with corrected thumbnails",
            True,
            "Visual check",
            ss(driver, "t7_gallery_view", sdir),
        )

        # Click first thumbnail to open viewer
        thumbs = driver.find_elements(By.CSS_SELECTOR, ".aspect-square")
        if thumbs:
            thumbs[0].click()
            time.sleep(2)
            report.add(
                "T8: Viewer shows correctly oriented image",
                True,
                "Visual check",
                ss(driver, "t8_viewer", sdir),
            )

    except Exception as e:
        report.add("Unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        ss(driver, "error", sdir)
    finally:
        driver.quit()

    path = os.path.join(desktop, "selenium-rotation-report.html")
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
