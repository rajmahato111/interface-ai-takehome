"""Long-lived Playwright persistent context owned by a run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright


@dataclass
class LiveSession:
    session_id: str
    playwright: Playwright
    context: BrowserContext
    page: Page
    user_data_dir: Path

    def close(self) -> None:
        self.context.close()
        self.playwright.stop()


def open_session(
    session_id: str,
    *,
    user_data_dir: Path,
    headless: bool = True,
    start_url: str | None = None,
) -> LiveSession:
    user_data_dir.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        str(user_data_dir),
        headless=headless,
        viewport={"width": 1280, "height": 800},
    )
    page = context.pages[0] if context.pages else context.new_page()
    if start_url:
        page.goto(start_url)
    return LiveSession(session_id, pw, context, page, user_data_dir)
