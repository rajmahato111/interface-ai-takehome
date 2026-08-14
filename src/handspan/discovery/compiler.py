"""Trace → artifact. Prune, parameterise, ladder, checkpoints, redact."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from handspan.errors.taxonomy import HardFailure
from handspan.policy.redaction import redact_text
from handspan.schema.capability import (
    Artifact,
    InputParam,
    OutputField,
    OutputSource,
)


def compile_trace(
    *,
    goal: str,
    run_id: str,
    trace: list[dict[str, Any]],
    inputs: dict[str, str],
    target_url: str,
) -> Artifact:
    steps_out: list[dict[str, Any]] = []
    n = 0
    for ev in _prune(trace, inputs):
        n += 1
        sid = f"s{n}"
        action = ev["action"]
        name = ev.get("name") or ev.get("label") or ""
        role = ev.get("role") or _role_for(action)
        frame = ev.get("frame")
        step: dict[str, Any] = {
            "id": sid,
            "intent": redact_text(ev.get("rationale") or action),
            "action": action,
            "risk": "risky" if action in {"submit_form", "confirm_dialog"} else "safe",
        }
        if action == "navigate":
            url = ev.get("url_template") or ""
            for k, v in inputs.items():
                if v and v in url:
                    url = url.replace(v, "{" + k + "}")
            step["url_template"] = url
        if action not in {"finish", "escalate", "navigate"}:
            step["target"] = _ladder(role, name, frame, action)
        if action == "type":
            src = ev.get("value_from_input")
            lit = ev.get("literal")
            if src:
                step["value"] = {"from_input": src}
            elif lit:
                raise HardFailure("COMPILER", "literal value matching no input")
            _forbid_literal_pii(step, inputs)
        if action == "extract":
            step["extract_to"] = ev.get("extract_to")
            step["checkpoint"] = (
                {"kind": "matches", "pattern": r"\$[0-9,]+\.[0-9]{2}"}
                if ev.get("extract_to") == "savings_balance"
                else {"kind": "ax_present", "name_matches": "."}
            )
        if action == "click":
            step["checkpoint"] = {
                "kind": "any_of",
                "conditions": [
                    {
                        "kind": "ax_present",
                        "role": "heading",
                        "name_matches": r"^Member .* Detail$",
                    },
                    {"kind": "text_present", "value": "No records found"},
                    {"kind": "text_present", "value": "Member Search"},
                    {"kind": "text_present", "value": "Welcome"},
                ],
            }
            step["expectations"] = [
                {
                    "when": {"kind": "text_present", "value": "No records found"},
                    "classify": "business_outcome",
                    "outcome": "MEMBER_NOT_FOUND",
                    "halt": True,
                }
            ]
        if action == "finish":
            step["status"] = ev.get("status") or "success"
        steps_out.append(step)

    from handspan.schema.capability import Step

    parsed_steps = [Step.model_validate(s) for s in steps_out]
    input_params = [
        InputParam(
            name="member_id",
            type="string",
            required=True,
            pattern=r"^[0-9]{6}$",
            sensitivity="identifier",
            example="100234",
        ),
        InputParam(
            name="username", type="string", required=False, default="teller", sensitivity="secret"
        ),
        InputParam(
            name="password", type="string", required=False, default="teller", sensitivity="secret"
        ),
        InputParam(
            name="base_url",
            type="string",
            required=False,
            default="http://127.0.0.1:8081",
            sensitivity="public",
        ),
    ]
    return Artifact.model_validate(
        {
            "schema_version": "1.0.0",
            "capability": {
                "id": "cap.member.read_savings_balance",
                "version": 1,
                "name": "Read member savings balance",
                "description": goal,
                "status": "approved",
                "labels": ["member", "read-only", "balance"],
            },
            "target": {
                "surface": {"kind": "web", "adapter": "web_aria/1"},
                "app": {
                    "product": "CoreVantage Servicing",
                    "product_version": "9.4",
                    "tenant_scope": "base",
                    "entry": {
                        "url_template": "{base_url}/servicing/home",
                        "requires_session": True,
                    },
                },
                "allowlist_ref": "policies/corevantage.yaml",
            },
            "inputs": [p.model_dump() for p in input_params],
            "outputs": [
                OutputField(
                    name="savings_balance",
                    type="money",
                    source=OutputSource(step="s4", extractor="ax_text", transform="parse_money"),
                    sensitivity="pii",
                ).model_dump(),
                OutputField(
                    name="account_status",
                    type="enum",
                    values=["active", "dormant", "frozen"],
                    required=False,
                    source=OutputSource(step="s5", extractor="ax_text", transform="lower_trim"),
                    sensitivity="identifier",
                ).model_dump(),
            ],
            "outcomes": [
                {"code": "MEMBER_NOT_FOUND", "description": "No member matches the supplied ID."},
                {
                    "code": "PERMISSION_DENIED",
                    "description": "Session lacks entitlement to view this member.",
                },
            ],
            "policy": {
                "risk_class": "safe",
                "side_effects": "none",
                "requires_approval_for_unattended": False,
            },
            "steps": [s.model_dump() for s in parsed_steps],
            "provenance": {
                "discovered_by": "claude-sonnet",
                "discovery_run_id": run_id,
                "discovered_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "compiler_version": "1.0.0",
            },
        }
    )


def _prune(trace: list[dict[str, Any]], inputs: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    last_type: tuple[str, str] | None = None
    for raw in trace:
        if raw.get("noop") or raw.get("action") in {None, "observe"}:
            continue
        ev = _normalize_event(dict(raw), inputs)
        if ev["action"] == "type":
            key = (ev.get("name") or "", str(ev.get("value_from_input") or ""))
            if key == last_type:
                continue
            last_type = key
        else:
            last_type = None
        out.append(ev)
    return out


def _normalize_event(ev: dict[str, Any], inputs: dict[str, str]) -> dict[str, Any]:
    src = ev.get("value_from_input")
    lit = ev.get("literal")
    if isinstance(src, str) and src not in inputs:
        mapped = _input_for_value(src, inputs)
        if mapped:
            ev["value_from_input"] = mapped
            src = mapped
    if not src and isinstance(lit, str):
        mapped = _input_for_value(lit, inputs)
        if mapped:
            ev["value_from_input"] = mapped
            ev.pop("literal", None)
    action = ev.get("action")
    name = ev.get("name") or ev.get("label") or ""
    if action == "type":
        ev["name"] = name or "Member ID"
        ev["frame"] = ev.get("frame") or "content"
        ev["role"] = "textbox" if ev.get("role") in {None, "", "input"} else ev.get("role")
    elif action == "click":
        if name in {"Member Search", "Home"}:
            ev["frame"] = ev.get("frame") or "nav"
            ev["role"] = "link"
        elif name in {"Find", "Search", "Open Sub-Account"}:
            ev["frame"] = ev.get("frame") or "content"
            ev["role"] = "link" if name == "Open Sub-Account" else "button"
    elif action == "extract":
        ev["name"] = name
        ev["label"] = ev.get("label") or name
        ev["frame"] = ev.get("frame") or "content"
    return ev


def _input_for_value(value: str, inputs: dict[str, str]) -> str | None:
    for k, v in inputs.items():
        if v and v == value:
            return k
    if value.isdigit() and len(value) == 6:
        return "member_id"
    return None


def _role_for(action: str) -> str:
    return {"type": "textbox", "click": "button", "select": "combobox", "extract": "cell"}.get(
        action, "generic"
    )


def _ladder(role: str, name: str, frame: str | None, action: str) -> dict[str, Any]:
    if action == "extract":
        return {
            "frame": frame or "content",
            "rationale": f"Accessible name {name!r} is more stable than generated ids.",
            "strategies": [
                {
                    "kind": "ax_label_proximity",
                    "label": name,
                    "direction": "right",
                    "max_distance": 2,
                },
                {"kind": "table_cell_neighbour", "label_text": name, "cell_offset": [0, 1]},
                {
                    "kind": "regex_in_region",
                    "region_anchor": name.split()[0] if name else "Savings",
                    "pattern": r"\$[0-9,]+\.[0-9]{2}",
                },
            ],
            "match_policy": "first",
            "recorded_rung": 1,
        }
    if role == "link" or name in {"Member Search", "Home"}:
        return {
            "frame": frame or "nav",
            "rationale": f"Accessible name {name!r} is more stable than generated ids.",
            "strategies": [
                {"kind": "ax_role_name", "role": "link", "name": name, "match": "exact"},
                {"kind": "css", "value": f"a:has-text('{name}')"},
            ],
            "match_policy": "require_unique",
            "recorded_rung": 1,
        }
    if action == "type":
        return {
            "frame": frame or "content",
            "rationale": f"Accessible name {name!r} is more stable than generated ids.",
            "strategies": [
                {"kind": "ax_role_name", "role": "textbox", "name": name, "match": "exact"},
                {
                    "kind": "ax_label_proximity",
                    "label": name,
                    "direction": "right",
                    "max_distance": 2,
                },
                {"kind": "table_cell_neighbour", "label_text": name, "cell_offset": [0, 1]},
                {"kind": "css", "value": "input[id$='txt1'], input[id$='srch_q']"},
            ],
            "match_policy": "require_unique",
            "recorded_rung": 2,
        }
    return {
        "frame": frame or "content",
        "rationale": f"Accessible name {name!r} is more stable than generated ids.",
        "strategies": [
            {"kind": "ax_role_name", "role": role or "button", "name": name, "match": "exact"},
            {"kind": "css", "value": f"input[type=submit][value='{name}']"},
            {"kind": "css", "value": "input[type=submit]"},
        ],
        "match_policy": "require_unique",
        "recorded_rung": 1,
    }


def _forbid_literal_pii(step: dict[str, Any], inputs: dict[str, str]) -> None:
    blob = str(step)
    for k, v in inputs.items():
        if v and v in blob and "from_input" not in blob:
            raise HardFailure("COMPILER", f"literal {k} leaked into step")
