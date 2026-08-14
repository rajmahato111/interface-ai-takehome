"""Checkpoint evaluation after state-changing steps."""

from __future__ import annotations

from typing import Any

from handspan.schema.conditions import Checkpoint, Condition
from handspan.surface.base import Observation


def passed(
    obs: Observation, checkpoint: Checkpoint | Condition | None, bound: dict[str, str]
) -> bool:
    if checkpoint is None:
        return True
    kind = checkpoint.kind
    if kind == "any_of":
        return any(passed(obs, c, bound) for c in (checkpoint.conditions or []))
    expected = _expected(checkpoint, bound)
    if kind == "ax_value_equals":
        return expected.lower() in obs.ax_text.lower() if expected else True
    if kind == "ax_present":
        cond = Condition.model_validate(checkpoint.model_dump())
        return obs.matches(cond)
    if kind == "text_present":
        needle = expected or (checkpoint.value if hasattr(checkpoint, "value") else "") or ""
        return needle.lower() in obs.ax_text.lower()
    if kind == "matches":
        import re

        pat = checkpoint.pattern or expected
        return re.search(pat or "", obs.ax_text) is not None
    cond = Condition.model_validate(checkpoint.model_dump())
    return obs.matches(cond)


def _expected(checkpoint: Any, bound: dict[str, str]) -> str:
    exp = getattr(checkpoint, "expected", None)
    if exp is None:
        return getattr(checkpoint, "value", None) or ""
    if isinstance(exp, str):
        return bound.get(exp, exp)
    if getattr(exp, "from_input", None):
        return bound.get(exp.from_input, exp.default or "")
    return exp.literal or ""
