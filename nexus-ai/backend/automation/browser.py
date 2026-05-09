"""
Playwright-powered browser automation (sync API for LangChain tool compatibility).
WhatsApp Web flows depend on DOM selectors that Meta may change — selectors live in constants below.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from backend.config import Settings


@dataclass
class BrowserSession:
    playwright: Playwright
    browser: Browser
    page: Page


class PlaywrightController:
    """Keeps a singleton browser session for sequential agent actions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._session: BrowserSession | None = None

    def _launch(self) -> BrowserSession:
        if self._session:
            return self._session
        pw = sync_playwright().start()
        channel = (self.settings.default_browser_channel or "").strip() or None
        launch_kwargs = {"headless": self.settings.playwright_headless}
        if channel:
            browser = pw.chromium.launch(channel=channel, **launch_kwargs)
        else:
            browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context()
        page = context.new_page()
        self._session = BrowserSession(playwright=pw, browser=browser, page=page)
        return self._session

    def ensure_page(self) -> Page:
        return self._launch().page

    def close(self) -> None:
        if not self._session:
            return
        try:
            self._session.browser.close()
        finally:
            self._session.playwright.stop()
            self._session = None


def open_whatsapp_web(controller: PlaywrightController) -> str:
    """Navigate to WhatsApp Web (QR login required on first run)."""
    page = controller.ensure_page()
    page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
    return "Opened WhatsApp Web. Complete QR pairing if prompted."


def whatsapp_send_message(controller: PlaywrightController, contact_query: str, message: str) -> str:
    """
    Attempt to search a chat and send a message.
    User must already be logged into WhatsApp Web in this browser profile.
    """
    page = controller.ensure_page()
    page.goto("https://web.whatsapp.com/", wait_until="networkidle")
    time.sleep(2.0)

    # Search box: role combobox is stable in many WA Web builds
    try:
        search = page.get_by_role("combobox", name="Search input textbox")
        search.click(timeout=10_000)
        search.fill(contact_query)
        time.sleep(1.2)
        page.keyboard.press("Enter")
        time.sleep(1.5)
    except Exception as exc:  # noqa: BLE001
        return f"Could not open chat for '{contact_query}': {exc}"

    # Message composer
    try:
        box = page.locator(
            "div[contenteditable='true'][data-tab='10'], "
            "footer div[contenteditable='true'], "
            "[contenteditable='true'][role='textbox']"
        ).first
        box.click(timeout=10_000)
        box.fill(message)
        page.keyboard.press("Enter")
        return f"Sent WhatsApp message to match '{contact_query}'."
    except Exception as exc:  # noqa: BLE001
        return f"Message compose/send failed: {exc}. Ensure chat is open and UI matches selectors."


def open_youtube(controller: PlaywrightController) -> str:
    page = controller.ensure_page()
    page.goto("https://www.youtube.com/", wait_until="domcontentloaded")
    return "Opened YouTube."


def youtube_search(controller: PlaywrightController, query: str) -> str:
    page = controller.ensure_page()
    q = query.replace(" ", "+")
    page.goto(f"https://www.youtube.com/results?search_query={q}", wait_until="domcontentloaded")
    return f"YouTube search opened for: {query}"


def open_gmail(controller: PlaywrightController) -> str:
    page = controller.ensure_page()
    page.goto("https://mail.google.com/", wait_until="domcontentloaded")
    return "Opened Gmail (login if required)."
