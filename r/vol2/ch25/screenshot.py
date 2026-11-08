"""Chapter 25: take the screenshot of the surveillance app printed in the book.

Run from the repository root (needs R with shiny, and Python's playwright with Chromium):

    python r/vol2/ch25/screenshot.py book/figures/v2-ch25-app.png
"""

import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

out = sys.argv[1] if len(sys.argv) > 1 else "app.png"
port = 8766
app = subprocess.Popen(["Rscript", "-e", f'shiny::runApp("r/vol2/ch25", port = {port}, launch.browser = FALSE)'],
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
        page = browser.new_page(viewport={"width": 700, "height": 900}, device_scale_factor=3)
        page.goto(f"http://127.0.0.1:{port}")
        page.wait_for_selector("#triggers table")
        page.click("#ask")
        page.wait_for_function("document.querySelector('#answer').innerText.length > 10")
        page.screenshot(path=out)              # the first screen: sidebar, trigger tests, arrears by region
        browser.close()
finally:
    app.terminate()
    app.wait()
print("Wrote", out)
