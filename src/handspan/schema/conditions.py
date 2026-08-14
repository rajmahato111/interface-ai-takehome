"""Checkpoints, waits, and expectation tables."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ValueRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_input: str | None = None
    literal: str | None = None
    default: str | None = None


class Condition(BaseModel):
    """A state predicate evaluated against an Observation."""

    model_config = ConfigDict(extra="allow")

    kind: str
    role: str | None = None
    name: str | None = None
    name_matches: str | None = None
    value: str | None = None
    expected: ValueRef | str | None = None
    pattern: str | None = None
    conditions: list[Condition] | None = None
    frame: str | None = None


class Wait(BaseModel):
    kind: str = "none"
    timeout_ms: int = 8000


class Waits(BaseModel):
    before: Wait = Field(default_factory=Wait)
    after: Wait = Field(default_factory=Wait)


class Recovery(BaseModel):
    action: str
    accept_names: list[str] = Field(default_factory=list)


class Expectation(BaseModel):
    when: Condition
    classify: Literal["business_outcome", "recoverable", "hard_failure"]
    outcome: str | None = None
    code: str | None = None
    halt: bool = False
    recovery: Recovery | None = None
    max_attempts: int = 2


class Checkpoint(BaseModel):
    kind: str
    role: str | None = None
    name: str | None = None
    name_matches: str | None = None
    expected: ValueRef | str | None = None
    pattern: str | None = None
    conditions: list[Condition] | None = None
    frame: str | None = None


class Retry(BaseModel):
    attempts: int = 0
    backoff_ms: int = 400
    on: list[str] = Field(default_factory=list)


Condition.model_rebuild()
