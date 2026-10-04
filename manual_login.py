"""One-time helper: log into LinkedIn manually and save the browser session.

Run this before starting the bot so `browser_session/browser_state.json` contains
a valid logged-in session. The main bot will then detect the saved session and
skip the automatic credential login.

Usage:
    uv run python manual_login.py

A visible Chromium window will open on the LinkedIn login page. Log in manually
(including solving any 2FA / CAPTCHA). The script watches the page and, as soon
as it detects that you are logged in, saves the session and closes the browser.
No keyboard input is required.
"""

import asyncio
import json
import os

from playwright.async_api import async_playwright

from config.constants import BROWSER_STORAGE_STATE

AUTHENTICATED_URL_PATTERNS = (
    "/feed/",
    "/jobs/",
    "/in/",
    "/mynetwork/",
    "/notifications/",
    "/messaging/",
)

AUTHENTICATED_SELECTORS = [
    "nav[aria-label='Primary Navigation']",
    "a[href='https://www.linkedin.com/feed/']",
    "a[href='https://www.linkedin.com/jobs/']",
    "button[aria-label*='Notifications']",
    "button[aria-label*='Messaging']",
    "input[placeholder*='Search']",
]

POLL_INTERVAL_SEC = 3
MAX_WAIT_SEC = 15 * 60  # 15 minutes


def _ensure_session_dir() -> None:
    session_dir = os.path.dirname(BROWSER_STORAGE_STATE)
    if session_dir:
        os.makedirs(session_dir, exist_ok=True)


async def _is_authenticated(page) -> bool:
    current_url = page.url.lower()
    if any(pattern in current_url for pattern in AUTHENTICATED_URL_PATTERNS):
        return True
    for selector in AUTHENTICATED_SELECTORS:
        try:
            if await page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


async def main() -> None:
    _ensure_session_dir()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--window-position=0,0",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        print("\n" + "=" * 70)
        print("A Chromium window has opened on the LinkedIn login page.")
        print("Log in manually now (including 2FA or CAPTCHA if prompted).")
        print("The session will be saved automatically once login is detected.")
        print("=" * 70 + "\n")

        authenticated = False
        waited = 0
        while waited < MAX_WAIT_SEC:
            if await _is_authenticated(page):
                authenticated = True
                break
            await asyncio.sleep(POLL_INTERVAL_SEC)
            waited += POLL_INTERVAL_SEC

        if not authenticated:
            print("WARNING: login was not detected within the time limit.")
            print("Saving whatever session state is currently present...")

        storage_state = await context.storage_state()
        for origin in storage_state.get("origins", []):
            origin.setdefault("localStorage", [])
        storage_state.setdefault("cookies", [])

        with open(BROWSER_STORAGE_STATE, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, ensure_ascii=False, indent=2)

        print(f"Session saved to {BROWSER_STORAGE_STATE}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
