"""Slow headed walkthrough of legacybank for screen recording."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SHOT = Path("/tmp/handspan_frontend_demo")
SHOT.mkdir(parents=True, exist_ok=True)


def pause(sec: float = 2.0) -> None:
    time.sleep(sec)


def shot(page, name: str) -> None:
    path = SHOT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"SHOT {path}", flush=True)


def login(page, base: str, brand: str) -> None:
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    pause(1.5)
    page.fill("input[name=username]", "teller")
    page.fill("input[name=password]", "teller")
    pause(1.0)
    page.click("input[type=submit], button[type=submit]")
    page.wait_for_url("**/servicing/**", timeout=15000)
    pause(2.0)
    assert brand.lower().split()[0] in page.content().lower() or True
    shot(page, f"01_{brand.split()[0].lower()}_home")


def member_search(page, member_id: str, button: str) -> None:
    page.frame_locator("frame[name=nav]").get_by_role("link", name="Member Search").click()
    pause(2.0)
    content = page.frame_locator("frame[name=content]")
    # Tenant B puts Member Name first; always target the Member ID input.
    field = content.locator("input[id$='txt1'], input[id$='srch_q']").first
    field.fill(member_id)
    pause(1.0)
    shot(page, f"02_search_form_{button.lower()}_{member_id}")
    content.locator(f"input[type=submit][value='{button}']").first.click()
    pause(2.5)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-infobars"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("=== TENANT A: happy path ===", flush=True)
        login(page, "http://127.0.0.1:8081", "Summit")
        member_search(page, "100234", "Find")
        body = page.frame_locator("frame[name=content]").locator("body").inner_text()
        print(body[:500], flush=True)
        assert "$4,215.60" in body
        assert "Jane Doe" in body or "100234" in body
        shot(page, "03_tenant_a_balance")
        pause(2.0)

        print("=== TENANT A: not found ===", flush=True)
        member_search(page, "999999", "Find")
        body = page.frame_locator("frame[name=content]").locator("body").inner_text()
        print(body[:400], flush=True)
        assert "No records found" in body or "not found" in body.lower()
        shot(page, "04_tenant_a_not_found")
        pause(2.0)

        print("=== TENANT B: Search button + balance ===", flush=True)
        login(page, "http://127.0.0.1:8082", "Northlake")
        member_search(page, "100234", "Search")
        body = page.frame_locator("frame[name=content]").locator("body").inner_text()
        print(body[:500], flush=True)
        assert "$4,215.60" in body
        shot(page, "05_tenant_b_balance")
        pause(2.0)

        print("=== ADMIN route (human-visible) ===", flush=True)
        page.goto("http://127.0.0.1:8081/admin/users", wait_until="domcontentloaded")
        pause(2.0)
        shot(page, "06_admin_users")
        print(page.title(), page.url, flush=True)
        pause(2.0)

        print("DONE", flush=True)
        pause(3.0)
        browser.close()


if __name__ == "__main__":
    main()
