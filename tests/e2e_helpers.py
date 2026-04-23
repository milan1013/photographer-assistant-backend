"""Shared helpers for Playwright E2E tests."""

import io
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost")
API_URL = os.environ.get("E2E_API_URL", "http://localhost")
DEFAULT_PASSWORD = "testpassword123"
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)


def unique_email(prefix: str = "test") -> str:
    return f"{prefix}-{int(time.time())}@example.com"


def make_test_image(color: str = "red", size: tuple[int, int] = (50, 50)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def register_user(email: str, password: str = DEFAULT_PASSWORD, name: str = "Test User") -> tuple[str, dict]:
    """Register a user via API. Returns (access_token, headers)."""
    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email": email, "password": password, "full_name": name,
    })
    r.raise_for_status()
    token = r.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def create_gallery(headers: dict, name: str = "Test Gallery") -> str:
    """Create a gallery via API. Returns gallery ID."""
    g = requests.post(f"{API_URL}/api/galleries", json={"name": name}, headers=headers)
    g.raise_for_status()
    return g.json()["id"]


def upload_images(headers: dict, gallery_id: str, count: int = 3, color: str = "red") -> list[dict]:
    """Upload test images via API. Returns uploaded image data."""
    files = [("files", (f"img_{i}.jpg", make_test_image(color), "image/jpeg")) for i in range(count)]
    resp = requests.post(f"{API_URL}/api/galleries/{gallery_id}/images", headers=headers, files=files)
    resp.raise_for_status()
    return resp.json().get("uploaded", [])


def login_via_ui(page: Page, email: str, password: str = DEFAULT_PASSWORD):
    """Login via the UI."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_url(lambda url: "/login" not in url, timeout=10000)


def navigate_to_gallery(page: Page):
    """Click the first gallery card on the dashboard."""
    page.click("[class*='cursor-pointer'][class*='rounded-lg']", timeout=5000)
    page.wait_for_timeout(2000)


def get_token_from_logs(keyword: str = "Reset link") -> str | None:
    """Extract a token from backend docker logs."""
    for compose_file in ["docker-compose.prod.yml", "docker-compose.yml"]:
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "logs", "backend", "--tail", "30"],
                capture_output=True, text=True, cwd=PROJECT_ROOT,
            )
            for line in reversed(result.stdout.splitlines()):
                if keyword in line and "token=" in line:
                    match = re.search(r"token=([A-Za-z0-9_\-\.]+)", line)
                    if match:
                        return match.group(1)
        except Exception:
            pass
    return None


def report_dir(name: str) -> str:
    d = os.path.join(str(Path(__file__).resolve().parent), "reports", name)
    os.makedirs(d, exist_ok=True)
    return d


class TestReport:
    def __init__(self):
        self.results: list[dict] = []
        self.start = datetime.now()

    def add(self, name: str, passed: bool, detail: str = "", ss: str = ""):
        self.results.append({"name": name, "passed": passed, "detail": detail, "ss": ss})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))

    def save(self, path: str, title: str = "Test Report"):
        total = len(self.results)
        p = sum(1 for r in self.results if r["passed"])
        dur = (datetime.now() - self.start).total_seconds()
        rows = ""
        for r in self.results:
            c = "#d4edda" if r["passed"] else "#f8d7da"
            s = "PASS" if r["passed"] else "FAIL"
            img = f'<br><img src="{r["ss"]}" style="max-width:600px;margin-top:8px;border:1px solid #ccc;border-radius:4px;">' if r["ss"] else ""
            rows += f'<tr style="background:{c}"><td style="padding:8px;border:1px solid #dee2e6;">{s}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["name"]}</td><td style="padding:8px;border:1px solid #dee2e6;">{r["detail"]}{img}</td></tr>'
        html = f"""<!DOCTYPE html><html><head><title>{title}</title></head>
<body style="font-family:system-ui;max-width:900px;margin:40px auto;padding:0 20px;">
<h1>{title}</h1>
<p>Date: {self.start.strftime("%Y-%m-%d %H:%M:%S")} | Duration: {dur:.1f}s</p>
<p><strong>Total: {total}</strong> | <span style="color:green">Passed: {p}</span> | <span style="color:red">Failed: {total-p}</span></p>
<table style="width:100%;border-collapse:collapse;margin-top:20px;">
<tr style="background:#343a40;color:white;"><th style="padding:8px;border:1px solid #dee2e6;width:60px;">Status</th><th style="padding:8px;border:1px solid #dee2e6;">Test</th><th style="padding:8px;border:1px solid #dee2e6;">Detail</th></tr>
{rows}</table></body></html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    @property
    def all_passed(self) -> bool:
        return all(r["passed"] for r in self.results)

    def print_summary(self, report_path: str):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        print(f"\n{'='*60}")
        print(f"Results: {passed}/{total} passed")
        print(f"Report: {report_path}")
