"""Optional browser smoke test (not part of the normal unit tests).

It starts the app on a temporary database and walks one full journey in a real browser:
write -> review -> approve -> publish -> change a fact -> see the alert.

Run:  pip install playwright && playwright install chromium && python tests/ui_smoke.py
Set CP_CHROMIUM_PATH to use a browser that is already installed."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("PORT", "5099"))
URL = f"http://127.0.0.1:{PORT}/"


def login(pg, label):
    pg.goto(URL)
    pg.wait_for_selector("text=Demo accounts")
    pg.click(f"button:has-text('{label}')")
    pg.click("button:has-text('Sign in')")
    pg.wait_for_selector(".hero")


def main():
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "CP_DB_PATH": f"{tmp}/ui.db", "CP_UPLOAD_DIR": f"{tmp}/up", "PORT": str(PORT)}
    server = subprocess.Popen([sys.executable, "run.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(URL + "api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        errors = []
        with sync_playwright() as p:
            exe = os.environ.get("CP_CHROMIUM_PATH")
            b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()
            pg = b.new_page(viewport={"width": 1360, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("dialog", lambda d: d.accept())
            login(pg, "Creator: Rohan")
            pg.goto(URL + "#/new")
            pg.fill("input[name=title]", "Smoke test")
            pg.fill("textarea[name=text]", "The Starter plan costs Rs. 499 per month. Terms apply.")
            pg.click("button:has-text('Check my content')")
            pg.wait_for_selector("text=No issues found")
            pg.click("button:has-text('Submit for review')")
            pg.wait_for_selector(".pill.in_review")
            pg.click("[data-act=logout]")
            login(pg, "Reviewer")
            pg.goto(URL + "#/content")
            pg.fill("#csearch", "Smoke")
            pg.click("#clist tr.clickable >> nth=0")
            pg.click("button:has-text('Approve')")
            pg.click(".modal button.primary")
            pg.wait_for_selector(".pill.approved")
            pg.click("[data-act=logout]")
            login(pg, "Manager")
            pg.goto(URL + "#/content")
            pg.fill("#csearch", "Smoke")
            pg.click("#clist tr.clickable >> nth=0")
            pg.click("button:has-text('Publish')")
            pg.click(".modal button.primary")
            pg.wait_for_selector(".pill.published")
            # interactive extras: command palette, theme, filters
            pg.keyboard.press("Control+k")
            pg.wait_for_selector("#cmdk-in")
            pg.fill("#cmdk-in", "vault")
            pg.keyboard.press("Enter")
            pg.wait_for_selector("h1:has-text('Brand Vault')")
            pg.click("[data-act=theme]")
            assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
            pg.click("[data-act=theme]")
            # change a fact: the watcher must flag the published page
            pg.wait_for_selector("[data-fact*='price_starter']")
            pg.locator("[data-fact*='price_starter'] button[data-act=fact-edit]").click()
            pg.fill(".modal input[name=statement]", "The Starter plan costs Rs. 549 per month.")
            pg.fill(".modal input[name=value]", "Rs. 549")
            pg.click(".modal button.primary")
            pg.wait_for_selector("text=published page(s) now need a fix")
            pg.goto(URL + "#/inbox")
            pg.wait_for_selector("button:has-text('Apply as new draft')")
            for route, text in (("#/dashboard", "Truth Debt"), ("#/passports", "Claim Passports"), ("#/insights", "Insights"),
                                ("#/proof", "Proof Time Machine"), ("#/feed", "Truth Feed"), ("#/audit", "Audit trail")):
                pg.goto(URL + route)
                pg.wait_for_selector(f"h1:has-text('{text}'), .lbl:has-text('{text}')")
            b.close()
        assert not errors, errors
        print("UI smoke test passed")
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
