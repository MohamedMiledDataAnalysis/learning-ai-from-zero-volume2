"""Take the book's screenshots of the Dash app: start it, click through it in Chromium, save PNGs.

    python python/vol2/ch27/screenshot.py

Author tool. Needs Playwright (pip install playwright, then playwright install chromium), which is not in
requirements.txt.

Writes book/figures/v2-ch27-extract.png, v2-ch27-analysis.png and v2-ch27-surveillance.png.
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "book" / "figures"
PORT = 8061

server = subprocess.Popen([sys.executable, str(Path(__file__).with_name("app.py")), str(PORT)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(120):                           # wait until the app answers, at most a minute
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2)
        page.goto(f"http://127.0.0.1:{PORT}/")
        page.wait_for_selector("#sample_severn")

        # Severn, both layers, simulated model: the Terms tab.
        page.click("#sample_severn")
        page.wait_for_selector("text=Loaded: Severn")
        page.locator("#layer").get_by_label("both").check()
        page.click("#extract")
        page.wait_for_selector("text=16 of 16 fields found")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "v2-ch27-extract.png"), full_page=False)

        # The Analysis tab of the same deal.
        page.get_by_text("Analysis", exact=True).click()
        page.wait_for_selector("#capital .main-svg")
        page.wait_for_timeout(1000)
        page.locator("#capital").screenshot(path=str(OUT / "v2-ch27-analysis.png"))   # the chart alone: readable in print

        # Thames, rules only: the Surveillance tab with the extracted limits.
        page.get_by_text("Deal terms", exact=True).click()
        page.click("#sample_thames")
        page.wait_for_selector("text=Loaded: Thames")
        page.locator("#layer").get_by_label("rules").check()
        page.click("#extract")
        page.wait_for_selector("text=Answer key: 50 of 50")
        page.get_by_text("Surveillance", exact=True).click()
        page.get_by_label("Use the Thames sample data").check()
        page.wait_for_selector("text=12 period(s) tested")
        page.wait_for_timeout(800)
        page.locator("#surveillance").screenshot(path=str(OUT / "v2-ch27-surveillance.png"))   # the table alone
        browser.close()
    print("Saved 3 screenshots in book/figures/")
finally:
    server.terminate()
    server.wait()
