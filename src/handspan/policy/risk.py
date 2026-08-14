"""Risky vs safe actions. Fail closed in unattended replay."""

from __future__ import annotations

from typing import Literal

from handspan.errors.taxonomy import Code, HardFailure

RISKY_ACTIONS = {"submit_form", "confirm_dialog"}


def is_risky(action: str, *, step_risk: str = "safe", side_effects: str = "none") -> bool:
    if step_risk == "risky":
        return True
    if action == "submit_form" and side_effects != "none":
        return True
    if action == "confirm_dialog":
        return True
    return action in RISKY_ACTIONS and side_effects != "none"


def gate_risky(
    action: str,
    *,
    mode: Literal["discovery", "attended", "unattended"],
    step_risk: str = "safe",
    side_effects: str = "none",
    approved: bool = False,
) -> Literal["allow", "confirm", "block"]:
    if not is_risky(action, step_risk=step_risk, side_effects=side_effects):
        return "allow"
    if mode == "unattended":
        if approved:
            return "allow"
        raise HardFailure(Code.POLICY_BLOCKED, f"risky action {action} blocked in unattended mode")
    return "confirm"
