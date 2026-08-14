"""Discovery budgets."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Limits:
    max_steps: int = 25
    wallclock_s: float = 180
    token_budget: int = 100_000

    def __post_init__(self) -> None:
        self.t0 = time.monotonic()
        self.steps = 0
        self.tokens = 0

    def tick(self, tokens: int = 0) -> str | None:
        self.steps += 1
        self.tokens += tokens
        if self.steps > self.max_steps:
            return "MAX_STEPS"
        if time.monotonic() - self.t0 > self.wallclock_s:
            return "WALLCLOCK"
        if self.tokens > self.token_budget:
            return "TOKEN_BUDGET"
        return None
