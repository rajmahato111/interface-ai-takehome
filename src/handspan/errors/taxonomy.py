"""Error taxonomy — Class A business, Class B recoverable, Class C hard failure."""

from __future__ import annotations

from enum import StrEnum


class Class(StrEnum):
    BUSINESS = "business_outcome"
    RECOVERABLE = "recoverable"
    HARD = "hard_failure"


class Code(StrEnum):
    # A
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    # B
    TRANSIENT_LOAD = "TRANSIENT_LOAD"
    KNOWN_INTERSTITIAL = "KNOWN_INTERSTITIAL"
    STALE_HANDLE = "STALE_HANDLE"
    NAV_RACE = "NAV_RACE"
    RATE_LIMITED = "RATE_LIMITED"
    # C
    SESSION_EXPIRED = "SESSION_EXPIRED"
    LOCATOR_EXHAUSTED = "LOCATOR_EXHAUSTED"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    CHECKPOINT_MISMATCH = "CHECKPOINT_MISMATCH"
    APP_ERROR = "APP_ERROR"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    TIMEOUT_EXCEEDED = "TIMEOUT_EXCEEDED"
    INVALID_INPUT = "INVALID_INPUT"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    UNEXPECTED_STATE = "UNEXPECTED_STATE"
    RESUME_STATE_MISMATCH = "RESUME_STATE_MISMATCH"
    LEASE_NOT_HELD = "LEASE_NOT_HELD"


ESCALATE_ON = {
    Code.SESSION_EXPIRED,
    Code.LOCATOR_EXHAUSTED,
    Code.AMBIGUOUS_TARGET,
    Code.CHECKPOINT_MISMATCH,
}


class HandspanError(Exception):
    def __init__(self, code: str, message: str = "", *, step: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.step = step


class BusinessOutcome(HandspanError):
    cls = Class.BUSINESS


class Recoverable(HandspanError):
    cls = Class.RECOVERABLE


class HardFailure(HandspanError):
    cls = Class.HARD
