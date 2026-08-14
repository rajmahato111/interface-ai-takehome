"""Playwright + AX implementation of Surface."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

from handspan.schema.capability import Step, Target
from handspan.schema.conditions import Wait
from handspan.surface.ax_compact import compact
from handspan.surface.base import ActionResult, Handle, Observation
from handspan.surface.ladder import resolve as resolve_ladder


class WebAriaSurface:
    def __init__(self, page: Page, *, playwright: Any = None, owns: bool = False) -> None:
        self.page = page
        self._pw = playwright
        self._owns = owns
        self._paused = False

    @classmethod
    def launch(
        cls,
        *,
        headless: bool = True,
        start_url: str | None = None,
        user_data_dir: str | None = None,
    ) -> WebAriaSurface:
        pw = sync_playwright().start()
        if user_data_dir:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir, headless=headless, viewport={"width": 1280, "height": 800}
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        else:
            browser = pw.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_default_timeout(5000)
        if start_url:
            page.goto(start_url)
        return cls(page, playwright=pw, owns=True)

    def close(self) -> None:
        if self._owns:
            self.page.context.close()
            if self._pw:
                self._pw.stop()

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def login(self, username: str, password: str) -> None:
        if "/login" not in self.page.url:
            origin = f"{urlparse(self.page.url).scheme}://{urlparse(self.page.url).netloc}"
            self.page.goto(urljoin(origin, "/login"), wait_until="domcontentloaded")
        self.page.locator("input[name=username]").fill(username)
        self.page.locator("input[name=password]").fill(password)
        self.page.locator("input[type=submit]").click()
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.frame_locator("frame[name=nav]").locator("body").wait_for(timeout=8000)
        except Exception:
            pass

    def observe(self, *, screenshot: bool = False) -> Observation:
        frames = [f.name or "" for f in self.page.frames]
        texts: list[str] = []
        ax_nodes: list[dict[str, Any]] = []
        for fr in self.page.frames:
            try:
                texts.append(fr.inner_text("body", timeout=1500))
            except Exception:
                continue
            try:
                ax_nodes.extend(
                    fr.evaluate(
                        """() => Array.from(document.querySelectorAll('input,button,select,textarea,a,h1,h2,h3,[role]')).map(el => ({
                            role: el.getAttribute('role') || el.tagName.toLowerCase(),
                            name: (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().slice(0,120),
                            value: (el.value || '').slice(0,120),
                            id: el.id || ''
                        }))"""
                    )
                )
            except Exception:
                pass
        ax_text = "\n".join(texts)
        extra_vals = [str(n.get("value") or "") for n in ax_nodes if n.get("value")]
        if extra_vals:
            ax_text = ax_text + "\n" + "\n".join(extra_vals)
        digest = hashlib.sha256(ax_text.encode()).hexdigest()[:16]
        shot = self.screenshot() if screenshot else None
        return Observation(
            url=self.page.url,
            title=self.page.title(),
            frames=frames,
            ax_tree={"nodes": ax_nodes},
            ax_text=ax_text,
            screenshot=shot,
            digest=digest,
        )

    def compact_ax(self, last_name: str | None = None) -> list[dict[str, Any]]:
        return compact(self.observe().ax_tree, last_name=last_name)

    def resolve(self, target: Target) -> Handle:
        return resolve_ladder(self.page, target)

    def wait(self, wait: Wait) -> bool:
        kind = wait.kind
        timeout = wait.timeout_ms
        if kind in {"none", ""}:
            return True
        try:
            if kind in {"navigation_or_ax_change", "ax_stable"}:
                self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
                return True
            if kind == "text_present":
                return True
            if kind == "ax_present":
                self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
                return True
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            return True
        except Exception:
            return False

    def act(self, step: Step, handle: Handle | None, bound: dict[str, str]) -> ActionResult:
        action = step.action
        try:
            if action == "navigate":
                url = (step.url_template or "").format(**bound)
                if handle and handle.frame_name:
                    for fr in self.page.frames:
                        if fr.name == handle.frame_name:
                            fr.goto(url)
                            break
                    else:
                        self.goto(url)
                else:
                    self.goto(url)
            elif action == "click":
                assert handle is not None
                if handle.click_point:
                    self.page.mouse.click(*handle.click_point)
                else:
                    handle.locator.click()
            elif action == "type":
                assert handle is not None
                value = _value(step, bound)
                handle.locator.fill(value)
            elif action == "select":
                assert handle is not None
                value = _value(step, bound, attr="option")
                handle.locator.select_option(value)
            elif action == "press_key":
                self.page.keyboard.press(step.key or "Enter")
            elif action == "extract":
                assert handle is not None
                if handle.extracted:
                    text = handle.extracted
                else:
                    text = handle.locator.inner_text()
                return ActionResult(ok=True, extracted=text.strip(), observation=self.observe())
            elif action == "submit_form":
                if handle and handle.locator:
                    handle.locator.click()
                else:
                    self.page.keyboard.press("Enter")
            elif action == "confirm_dialog":
                names = step.accept_names or ["OK", "Close"]
                scopes: list[Any] = [self.page, *list(self.page.frames)]
                try:
                    scopes.append(self.page.frame_locator("frame[name=content]"))
                except Exception:
                    pass
                for n in names:
                    for scope in scopes:
                        try:
                            loc = scope.get_by_role("button", name=n)
                            if loc.count():
                                loc.first.click()
                                break
                        except Exception:
                            continue
                    else:
                        continue
                    break
            elif action in {"wait_for", "assert"}:
                self.wait(step.waits.after)
            elif action in {"finish", "escalate"}:
                pass
            else:
                return ActionResult(ok=False, error=f"unknown action {action}")
            return ActionResult(ok=True, observation=self.observe())
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, error=str(e), observation=self.observe())

    def session_info(self) -> dict[str, Any]:
        return {"url": self.page.url, "frames": [f.name for f in self.page.frames]}

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def mask_sensitive(self) -> None:
        for fr in self.page.frames:
            try:
                fr.evaluate(
                    """() => {
                    const re = /SSN|Social Security|Tax ID|card|PAN/i;
                    document.querySelectorAll('td').forEach(td => {
                      if (re.test(td.textContent || '')) {
                        td.style.background = '#000';
                        td.style.color = '#000';
                        const n = td.nextElementSibling;
                        if (n) { n.style.background = '#000'; n.style.color = '#000'; }
                      }
                    });
                    }"""
                )
            except Exception:
                pass

    def screenshot(self) -> bytes:
        self.mask_sensitive()
        return self.page.screenshot(full_page=True)


def _value(step: Step, bound: dict[str, str], attr: str = "value") -> str:
    raw = step.option if attr == "option" else step.value
    if raw is None:
        return ""
    if isinstance(raw, str):
        return bound.get(raw, raw)
    if raw.from_input:
        return bound.get(raw.from_input, raw.default or "")
    return raw.literal or raw.default or ""
