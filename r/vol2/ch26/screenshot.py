"""Chapter 26: take the screenshots of the Prospectus Analyser printed in the book.

Run from the repository root (needs R with shiny, and Python's playwright with Chromium):

    python r/vol2/ch26/screenshot.py book/figures

It loads the Severn sample, extracts with both layers and the simulated model, and saves
v2-ch26-terms.png, v2-ch26-analysis.png and v2-ch26-ask.png.
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
port = 8791
app = subprocess.Popen(["Rscript", "-e", f'shiny::runApp("r/vol2/ch26", port = {port}, launch.browser = FALSE)'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):                                   # wait until the app answers
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
            break
        except OSError:
            time.sleep(1)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1500}, device_scale_factor=2)
        page.goto(f"http://127.0.0.1:{port}")
        page.click("#sample_severn")
        page.check("input[name='layer'][value='both']")
        page.check("input[name='mode'][value='simulated']")
        page.click("#extract")
        page.wait_for_function("document.querySelectorAll('#terms table tbody tr').length >= 10")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out / "v2-ch26-terms.png"), full_page=True)
        page.click("a[data-value='Analysis']")
        page.wait_for_selector("#capital img")
        page.wait_for_timeout(800)
        page.screenshot(path=str(out / "v2-ch26-analysis.png"), full_page=True)
        page.click("a[data-value='Ask']")
        page.click("#ask")
        page.wait_for_function("document.querySelector('#answer').innerText.length > 10")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out / "v2-ch26-ask.png"))
        browser.close()
finally:
    app.terminate()
    app.wait()
print("Wrote v2-ch26-terms.png, v2-ch26-analysis.png, v2-ch26-ask.png")
