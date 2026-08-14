"""Surface port. Nothing above this module knows what a CSS selector is."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from handspan.schema.capability import Step, Target
from handspan.schema.conditions import Condition, Wait


@dataclass
class Observation:
    url: str
    title: str = ""
    frames: list[str] = field(default_factory=list)
    ax_tree: dict[str, Any] = field(default_factory=dict)
    ax_text: str = ""
    screenshot: bytes | None = None
    digest: str = ""
    status: int | None = None

    def matches(self, condition: Condition) -> bool:
        kind = condition.kind
        blob = (self.ax_text + "\n" + self.url + "\n" + self.title).lower()
        if kind == "any_of":
            return any(self.matches(c) for c in (condition.conditions or []))
        if kind == "text_present":
            return (condition.value or "").lower() in blob
        if kind == "text_matches":
            import re

            return re.search(condition.value or "", self.ax_text + self.title, re.I) is not None
        if kind in {"ax_present", "ax_value_equals", "matches"}:
            name = (condition.name or condition.name_matches or "").lower()
            if condition.name_matches:
                import re

                return re.search(condition.name_matches, self.ax_text, re.I) is not None
            if name and name in blob:
                return True
            if condition.pattern:
                import re

                return re.search(condition.pattern, self.ax_text) is not None
            if condition.value and condition.value.lower() in blob:
                return True
            return False
        if kind == "none":
            return True
        return False


@dataclass
class Handle:
    rung: int
    locator: Any = None
    frame_name: str | None = None
    click_point: tuple[float, float] | None = None
    extracted: str | None = None


@dataclass
class ActionResult:
    ok: bool
    extracted: str | None = None
    error: str | None = None
    observation: Observation | None = None


class Surface(Protocol):
    def observe(self, *, screenshot: bool = False) -> Observation: ...
    def resolve(self, target: Target) -> Handle: ...
    def act(self, step: Step, handle: Handle | None, bound: dict[str, str]) -> ActionResult: ...
    def wait(self, wait: Wait) -> bool: ...
    def session_info(self) -> dict[str, Any]: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def login(self, username: str, password: str) -> None: ...
    def goto(self, url: str) -> None: ...
    def mask_sensitive(self) -> None: ...
    def screenshot(self) -> bytes: ...
    def close(self) -> None: ...
