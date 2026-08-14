"""Caller-facing replay and intervention contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StepResult(BaseModel):
    id: str
    action: str
    status: str = "ok"
    duration_ms: int = 0
    rung_used: int | None = None
    checkpoint: str | None = None
    recoveries: list[dict[str, Any]] = Field(default_factory=list)


class Degradation(BaseModel):
    step: str
    recorded_rung: int
    rung_used: int
    signal: str = "possible_ui_drift"


class Outcome(BaseModel):
    code: str
    detected_at_step: str | None = None
    message: str = ""
    caller_action: str = "surface_to_user"


class Failure(BaseModel):
    code: str
    step: str | None = None
    expected: str | None = None
    observed: str | None = None
    rung_used: int | None = None
    recoveries_attempted: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)
    remediation_hint: str | None = None


class EscalationInfo(BaseModel):
    raised: bool = False
    request_id: str | None = None
    abandoned: bool = False


class ControlInfo(BaseModel):
    holder: str = "automation"
    handoffs: list[dict[str, Any]] = Field(default_factory=list)


class ReplayResult(BaseModel):
    run_id: str
    capability: dict[str, Any]
    status: Literal["success", "business_outcome", "failed", "escalated"]
    started_at: str
    duration_ms: int = 0
    inputs_digest: str = ""
    outputs: dict[str, Any] = Field(default_factory=dict)
    outcome: Outcome | None = None
    failure: Failure | None = None
    steps: list[StepResult] = Field(default_factory=list)
    degradations: list[Degradation] = Field(default_factory=list)
    control: ControlInfo = Field(default_factory=ControlInfo)
    evidence_ref: str | None = None
    escalation: EscalationInfo | None = None


class ResumeContract(BaseModel):
    resume_at_step: str
    required_state: dict[str, Any] = Field(default_factory=dict)
    on_state_mismatch: str = "abort_with_failure"


class InterventionRequest(BaseModel):
    request_id: str
    created_at: str
    kind: str
    priority: str = "normal"
    run: dict[str, Any] = Field(default_factory=dict)
    stopped_at: dict[str, Any] = Field(default_factory=dict)
    why: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    inputs_redacted: dict[str, str] = Field(default_factory=dict)
    session: dict[str, Any] = Field(default_factory=dict)
    allowed_human_actions: list[str] = Field(
        default_factory=lambda: ["click", "type", "select", "navigate_within_allowlist"]
    )
    resume_contract: ResumeContract | None = None
