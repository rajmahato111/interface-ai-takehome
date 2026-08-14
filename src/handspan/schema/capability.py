"""Capability artifact — the product. Replay's only input besides params."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from handspan.schema.conditions import Checkpoint, Expectation, Retry, ValueRef, Waits

SCHEMA_VERSION = "1.0.0"
SUPPORTED_MAJOR = 1

ACTIONS = (
    "navigate",
    "click",
    "type",
    "select",
    "press_key",
    "wait_for",
    "extract",
    "assert",
    "submit_form",
    "confirm_dialog",
    "escalate",
    "finish",
)

STRATEGY_KINDS = (
    "ax_role_name",
    "ax_label_proximity",
    "table_cell_neighbour",
    "css",
    "xpath",
    "visual_anchor",
    "regex_in_region",
)


class ActionName(StrEnum):
    navigate = "navigate"
    click = "click"
    type = "type"
    select = "select"
    press_key = "press_key"
    wait_for = "wait_for"
    extract = "extract"
    assert_ = "assert"
    submit_form = "submit_form"
    confirm_dialog = "confirm_dialog"
    escalate = "escalate"
    finish = "finish"


class Strategy(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    role: str | None = None
    name: str | None = None
    match: str | None = "exact"
    aliases: list[str] | None = None
    label: str | None = None
    label_text: str | None = None
    direction: str | None = None
    max_distance: int | None = None
    cell_offset: list[int] | None = None
    value: str | None = None
    anchor_text: str | None = None
    offset: list[int] | None = None
    requires: str | None = None
    region_anchor: str | None = None
    pattern: str | None = None

    @field_validator("kind")
    @classmethod
    def known_kind(cls, v: str) -> str:
        if v not in STRATEGY_KINDS:
            raise ValueError(f"unknown strategy kind: {v}")
        return v


class Target(BaseModel):
    frame: str | None = None
    rationale: str | None = None
    strategies: list[Strategy] = Field(min_length=1)
    match_policy: Literal["require_unique", "first", "nth"] = "require_unique"
    recorded_rung: int = 1
    nth: int = 1


class InputParam(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    pattern: str | None = None
    sensitivity: Literal["public", "identifier", "pii", "secret"] = "public"
    description: str | None = None
    example: str | None = None
    default: str | None = None
    values: list[str] | None = None


class OutputSource(BaseModel):
    step: str
    extractor: str = "ax_text"
    transform: str | None = None


class OutputField(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    source: OutputSource | None = None
    sensitivity: Literal["public", "identifier", "pii", "secret"] = "public"
    values: list[str] | None = None


class OutcomeDecl(BaseModel):
    code: str
    description: str = ""
    detected_at: str | None = None


class SurfaceSpec(BaseModel):
    kind: Literal["web", "legacy_web", "desktop"] = "web"
    adapter: str = "web_aria/1"


class AppEntry(BaseModel):
    url_template: str
    requires_session: bool = False


class AppSpec(BaseModel):
    product: str
    product_version: str
    tenant_scope: str = "base"
    entry: AppEntry


class TargetApp(BaseModel):
    surface: SurfaceSpec = Field(default_factory=SurfaceSpec)
    app: AppSpec
    allowlist_ref: str | None = None


class CapabilityMeta(BaseModel):
    id: str
    version: int
    name: str
    description: str = ""
    status: Literal["draft", "approved", "deprecated"] = "draft"
    labels: list[str] = Field(default_factory=list)


class PolicySpec(BaseModel):
    risk_class: Literal["safe", "risky"] = "safe"
    side_effects: Literal["none", "reversible", "irreversible"] = "none"
    requires_approval_for_unattended: bool = False
    max_runtime_ms: int = 45000
    unattended_approver: str | None = None


class Step(BaseModel):
    id: str
    intent: str = ""
    action: str
    target: Target | None = None
    value: ValueRef | str | None = None
    url_template: str | None = None
    option: ValueRef | str | None = None
    key: str | None = None
    extract_to: str | None = None
    condition: Checkpoint | None = None
    reason: str | None = None
    context: str | None = None
    status: str | None = None
    outputs: dict[str, Any] | None = None
    accept_names: list[str] | None = None
    waits: Waits = Field(default_factory=Waits)
    checkpoint: Checkpoint | None = None
    expectations: list[Expectation] = Field(default_factory=list)
    risk: Literal["safe", "risky"] = "safe"
    timeout_ms: int = 8000
    retry: Retry = Field(default_factory=Retry)

    @field_validator("action")
    @classmethod
    def known_action(cls, v: str) -> str:
        if v not in ACTIONS:
            raise ValueError(f"unknown action: {v}")
        return v


class LocatorDegradation(BaseModel):
    step: str
    rung_used: int
    count: int = 1


class Reliability(BaseModel):
    replays: int = 0
    successes: int = 0
    last_verified_at: str | None = None
    stability_score: float = 0.0
    locator_degradations: list[LocatorDegradation] = Field(default_factory=list)


class HumanEdit(BaseModel):
    at: str
    by: str
    note: str = ""


class Provenance(BaseModel):
    discovered_by: str = "unknown"
    discovery_run_id: str | None = None
    discovered_at: str | None = None
    compiler_version: str = "1.0.0"
    evidence_ref: str | None = None
    human_edits: list[HumanEdit] = Field(default_factory=list)


class Capability(BaseModel):
    id: str
    version: int
    name: str
    description: str = ""
    status: Literal["draft", "approved", "deprecated"] = "draft"
    labels: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    """Top-level capability artifact (PRD §8.2)."""

    schema_version: str = SCHEMA_VERSION
    capability: CapabilityMeta
    target: TargetApp
    inputs: list[InputParam] = Field(default_factory=list)
    outputs: list[OutputField] = Field(default_factory=list)
    outcomes: list[OutcomeDecl] = Field(default_factory=list)
    policy: PolicySpec = Field(default_factory=PolicySpec)
    steps: list[Step]
    reliability: Reliability = Field(default_factory=Reliability)
    provenance: Provenance = Field(default_factory=Provenance)

    @field_validator("schema_version")
    @classmethod
    def major_supported(cls, v: str) -> str:
        major = int(v.split(".", 1)[0])
        if major != SUPPORTED_MAJOR:
            raise ValueError(f"SCHEMA_INCOMPATIBLE: unsupported schema_version {v}")
        return v
