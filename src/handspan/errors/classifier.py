"""Classify an observation against step expectations, then app-profile defaults."""

from __future__ import annotations

from typing import Any

from handspan.errors.taxonomy import Class, Code, HandspanError
from handspan.schema.conditions import Expectation


def classify(
    observation: Any,
    expectations: list[Expectation],
    *,
    defaults: list[Expectation] | None = None,
    checkpoint_ok: bool,
) -> HandspanError | None:
    """Return a classified error, or None if the step may continue.

    Order: checkpoint satisfied → step expectations → app-profile defaults → UNEXPECTED_STATE.
    """
    if checkpoint_ok:
        return None
    for exp in list(expectations) + list(defaults or []):
        if not observation.matches(exp.when):
            continue
        if exp.classify == Class.BUSINESS:
            from handspan.errors.taxonomy import BusinessOutcome

            return BusinessOutcome(exp.outcome or Code.MEMBER_NOT_FOUND, step=None)
        if exp.classify == Class.RECOVERABLE:
            from handspan.errors.taxonomy import Recoverable

            return Recoverable(exp.code or Code.KNOWN_INTERSTITIAL)
        from handspan.errors.taxonomy import HardFailure

        return HardFailure(exp.code or Code.UNEXPECTED_STATE)
    from handspan.errors.taxonomy import HardFailure

    return HardFailure(Code.UNEXPECTED_STATE, "nothing in the expectation table matched")
