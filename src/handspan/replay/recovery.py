"""Bounded recovery for Class B conditions."""

from __future__ import annotations

from typing import Any

from handspan.errors.taxonomy import Code
from handspan.schema.conditions import Expectation
from handspan.surface.base import Observation
from handspan.surface.web_aria import WebAriaSurface

BOUNDS = {
    Code.TRANSIENT_LOAD.value: 2,
    Code.KNOWN_INTERSTITIAL.value: 2,
    Code.STALE_HANDLE.value: 2,
    Code.NAV_RACE.value: 1,
    Code.RATE_LIMITED.value: 2,
}


def try_recover(surface: WebAriaSurface, obs: Observation, exp: Expectation) -> bool:
    if exp.classify != "recoverable" or not exp.recovery:
        return False
    action = exp.recovery.action
    names = exp.recovery.accept_names or ["OK", "Close"]
    if action in {"dismiss_dialog", "confirm_dialog"}:
        scopes: list[Any] = [surface.page, *list(surface.page.frames)]
        try:
            scopes.append(surface.page.frame_locator("frame[name=content]"))
        except Exception:
            pass
        for n in names:
            for scope in scopes:
                try:
                    loc = scope.get_by_role("button", name=n)
                    if loc.count():
                        loc.first.click()
                        return True
                except Exception:
                    continue
                try:
                    loc = scope.get_by_text(n, exact=True)
                    if loc.count():
                        loc.first.click()
                        return True
                except Exception:
                    continue
    return False


def default_expectations() -> list[Expectation]:
    return [
        Expectation.model_validate(
            {
                "when": {"kind": "text_present", "value": "Your session has expired"},
                "classify": "hard_failure",
                "code": "SESSION_EXPIRED",
                "halt": True,
            }
        ),
        Expectation.model_validate(
            {
                "when": {"kind": "text_present", "value": "Internal Server Error"},
                "classify": "hard_failure",
                "code": "APP_ERROR",
                "halt": True,
            }
        ),
        Expectation.model_validate(
            {
                "when": {
                    "kind": "ax_present",
                    "role": "alertdialog",
                    "name_matches": "System Notice",
                },
                "classify": "recoverable",
                "code": "KNOWN_INTERSTITIAL",
                "recovery": {"action": "dismiss_dialog", "accept_names": ["OK", "Close"]},
                "max_attempts": 2,
            }
        ),
        Expectation.model_validate(
            {
                "when": {"kind": "text_present", "value": "No records found"},
                "classify": "business_outcome",
                "outcome": "MEMBER_NOT_FOUND",
                "halt": True,
            }
        ),
        Expectation.model_validate(
            {
                "when": {"kind": "text_matches", "value": "not authori[sz]ed|entitlement"},
                "classify": "business_outcome",
                "outcome": "PERMISSION_DENIED",
                "halt": True,
            }
        ),
        Expectation.model_validate(
            {
                "when": {"kind": "text_present", "value": "Product code required"},
                "classify": "business_outcome",
                "outcome": "VALIDATION_REJECTED",
                "halt": True,
            }
        ),
        Expectation.model_validate(
            {
                "when": {"kind": "text_present", "value": "All fields are required"},
                "classify": "business_outcome",
                "outcome": "VALIDATION_REJECTED",
                "halt": True,
            }
        ),
    ]
