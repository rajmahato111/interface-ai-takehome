"""Deterministic replay. No LLM imports — enforced by tests/unit/test_architecture.py."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from handspan.errors.taxonomy import (
    BusinessOutcome,
    Code,
    HandspanError,
    HardFailure,
    Recoverable,
)
from handspan.escalation.bus import Bus
from handspan.escalation.request import make_request
from handspan.obs.evidence import Evidence
from handspan.obs.logger import RunLog
from handspan.policy.allowlist import Allowlist
from handspan.policy.redaction import redact_obj
from handspan.policy.risk import gate_risky
from handspan.replay.binder import bind
from handspan.replay.checkpoints import passed
from handspan.replay.loader import load
from handspan.replay.recovery import default_expectations, try_recover
from handspan.schema.capability import Artifact, Step
from handspan.schema.results import (
    ControlInfo,
    Degradation,
    EscalationInfo,
    Failure,
    Outcome,
    ReplayResult,
    StepResult,
)
from handspan.session.lease import Lease, LeaseState
from handspan.surface.base import Observation
from handspan.surface.web_aria import WebAriaSurface

Mode = Literal["attended", "unattended"]


def replay(
    artifact_path: str | Path,
    params: dict[str, str],
    *,
    overlay: str | Path | None = None,
    mode: Mode = "unattended",
    headless: bool = True,
    persist_outputs: bool = False,
    evidence_dir: Path | None = None,
    allowlist_path: str | Path = "policies/corevantage.yaml",
    wait_for_human: bool = False,
    lease_dir: Path | None = None,
    surface: WebAriaSurface | None = None,
) -> ReplayResult:
    artifact = load(artifact_path, overlay=overlay)
    run_id = "rpl_" + uuid4().hex[:8]
    started = datetime.now(UTC)
    evidence = Evidence(evidence_dir or Path("evidence/replay") / run_id)
    log = RunLog(evidence.root / "run.jsonl", run_id)
    log.emit("run.started", capability=artifact.capability.id)
    lease_path = (lease_dir or evidence.root) / "lease.json"
    lease = Lease(lease_path, run_id)
    lease.start()
    bus = Bus(evidence.root / "interventions")

    try:
        bound, digest = bind(artifact, params)
    except HandspanError as e:
        log.emit("run.finished", status="failed", code=e.code)
        log.close()
        return _result(
            run_id,
            artifact,
            started,
            "failed",
            digest="",
            failure=Failure(code=e.code, expected=None, observed=e.message),
            evidence=evidence,
        )

    allow = Allowlist.load(allowlist_path)
    owns = surface is None
    if surface is None:
        entry = artifact.target.app.entry.url_template
        start = entry.format(base_url=_base(params, entry))
        if params.get("fault"):
            start += ("&" if "?" in start else "?") + "fault=" + params["fault"]
        surface = WebAriaSurface.launch(headless=headless, start_url=start)
    try:
        allow.check_url(surface.page.url)
        if artifact.target.app.entry.requires_session:
            if "username" in bound and "password" in bound:
                if "login" in surface.page.url or "Sign On" in surface.observe().ax_text:
                    surface.login(bound["username"], bound["password"])
                    allow.check_url(surface.page.url)

        step_results: list[StepResult] = []
        degradations: list[Degradation] = []
        outputs: dict[str, Any] = {}
        recoveries_count: dict[str, int] = {}

        for step in artifact.steps:
            lease.assert_automation()
            t0 = datetime.now(UTC)
            log.emit("policy.evaluated", step=step.id, action=step.action)
            try:
                allow.check_action(step.action)
                if step.action == "navigate" and step.url_template:
                    allow.check_url(step.url_template.format(**{**bound, "base_url": ""}))
                verdict = gate_risky(
                    step.action,
                    mode=mode if mode != "attended" else "attended",
                    step_risk=step.risk,
                    side_effects=artifact.policy.side_effects,
                    approved=bool(artifact.policy.unattended_approver)
                    or artifact.policy.requires_approval_for_unattended is False
                    and step.risk == "safe",
                )
                if verdict == "confirm" and mode == "attended":
                    return _escalate(
                        run_id,
                        artifact,
                        started,
                        step,
                        surface,
                        lease,
                        bus,
                        evidence,
                        log,
                        bound,
                        "approval needed",
                        wait_for_human=wait_for_human,
                    )
            except HardFailure as e:
                log.emit("policy.blocked", step=step.id, code=e.code)
                return _fail(
                    run_id, artifact, started, step, e, surface, evidence, log, step_results, digest
                )

            handle = None
            rung = None
            if step.target is not None and step.action not in {"finish", "escalate", "navigate"}:
                try:
                    handle = surface.resolve(step.target)
                    rung = handle.rung
                    if step.target.recorded_rung and rung > step.target.recorded_rung:
                        degradations.append(
                            Degradation(
                                step=step.id,
                                recorded_rung=step.target.recorded_rung,
                                rung_used=rung,
                            )
                        )
                except HardFailure as e:
                    return _fail(
                        run_id,
                        artifact,
                        started,
                        step,
                        e,
                        surface,
                        evidence,
                        log,
                        step_results,
                        digest,
                    )

            if step.action == "escalate":
                return _escalate(
                    run_id,
                    artifact,
                    started,
                    step,
                    surface,
                    lease,
                    bus,
                    evidence,
                    log,
                    bound,
                    step.reason or "escalate",
                    wait_for_human=wait_for_human,
                )

            surface.wait(step.waits.before)
            result = surface.act(step, handle, bound)
            surface.wait(step.waits.after)
            obs = result.observation or surface.observe(screenshot=True)

            if result.extracted and step.extract_to:
                outputs[step.extract_to] = _transform(result.extracted, artifact, step.extract_to)

            classified = _classify_obs(obs, step, recoveries_count, surface)
            recovered = []
            while isinstance(classified, Recoverable):
                recovered.append(
                    {"code": classified.code, "attempts": recoveries_count.get(classified.code, 1)}
                )
                obs = surface.observe()
                classified = _classify_obs(obs, step, recoveries_count, surface)
            if recovered and classified is None:
                classified = None
            if isinstance(classified, BusinessOutcome):
                log.emit("expectation.matched", step=step.id, code=classified.code)
                log.close()
                return _result(
                    run_id,
                    artifact,
                    started,
                    "business_outcome",
                    digest,
                    outputs={},
                    outcome=Outcome(
                        code=classified.code, detected_at_step=step.id, message=classified.message
                    ),
                    steps=step_results
                    + [
                        StepResult(
                            id=step.id,
                            action=step.action,
                            status="ok",
                            duration_ms=_ms(t0),
                            rung_used=rung,
                        )
                    ],
                    evidence=evidence,
                )
            if isinstance(classified, HardFailure):
                if classified.code == Code.SESSION_EXPIRED and (
                    wait_for_human or mode == "attended"
                ):
                    return _escalate(
                        run_id,
                        artifact,
                        started,
                        step,
                        surface,
                        lease,
                        bus,
                        evidence,
                        log,
                        bound,
                        "session expired",
                        wait_for_human=wait_for_human,
                        code=classified.code,
                    )
                return _fail(
                    run_id,
                    artifact,
                    started,
                    step,
                    classified,
                    surface,
                    evidence,
                    log,
                    step_results,
                    digest,
                    obs=obs,
                )

            ck_ok = passed(obs, step.checkpoint, bound)
            if step.checkpoint and not ck_ok and not isinstance(classified, Recoverable):
                # maybe recoverable interstitial hid the checkpoint
                again = _classify_obs(obs, step, recoveries_count, surface)
                if isinstance(again, Recoverable):
                    obs = surface.observe()
                    ck_ok = passed(obs, step.checkpoint, bound)
                if not ck_ok:
                    err = HardFailure(Code.CHECKPOINT_MISMATCH, f"checkpoint failed on {step.id}")
                    return _fail(
                        run_id,
                        artifact,
                        started,
                        step,
                        err,
                        surface,
                        evidence,
                        log,
                        step_results,
                        digest,
                        obs=obs,
                    )

            try:
                allow.check_url(surface.page.url)
            except HardFailure as e:
                return _fail(
                    run_id, artifact, started, step, e, surface, evidence, log, step_results, digest
                )

            step_results.append(
                StepResult(
                    id=step.id,
                    action=step.action,
                    status="ok",
                    duration_ms=_ms(t0),
                    rung_used=rung,
                    checkpoint="passed" if step.checkpoint else None,
                    recoveries=recovered,
                )
            )
            log.emit("step.completed", step=step.id, action=step.action, rung_used=rung)

            if step.action == "finish":
                break

        log.emit("run.finished", status="success")
        log.close()
        out = outputs if persist_outputs else outputs
        # outputs returned in memory always; file write only if persist
        final = _result(
            run_id,
            artifact,
            started,
            "success",
            digest,
            outputs=out,
            steps=step_results,
            degradations=degradations,
            evidence=evidence,
        )
        dump = final.model_dump()
        if not persist_outputs:
            dump["outputs"] = redact_obj({k: v for k, v in out.items()})
        evidence.write_json("result.json", {**dump, "outputs": out if persist_outputs else {}})
        return final
    finally:
        if owns:
            surface.close()


def _classify_obs(
    obs: Observation,
    step: Step,
    recoveries: dict[str, int],
    surface: WebAriaSurface,
) -> HandspanError | None:
    matched = None
    for exp in list(step.expectations) + default_expectations():
        if obs.matches(exp.when):
            matched = exp
            break
    if matched is None:
        return None
    if matched.classify == "recoverable":
        code = matched.code or Code.KNOWN_INTERSTITIAL
        recoveries[code] = recoveries.get(code, 0) + 1
        bound = matched.max_attempts
        if recoveries[code] > bound:
            return HardFailure(Code.UNEXPECTED_STATE, "recovery bound exceeded")
        if try_recover(surface, obs, matched):
            return Recoverable(code)
        return Recoverable(code)
    if matched.classify == "business_outcome":
        return BusinessOutcome(matched.outcome or "BUSINESS", matched.outcome or "")
    return HardFailure(matched.code or Code.UNEXPECTED_STATE)


def _base(params: dict[str, str], entry: str) -> str:
    if "base_url" in params:
        return params["base_url"].rstrip("/")
    if "{base_url}" in entry:
        return "http://127.0.0.1:8081"
    return "http://127.0.0.1:8081"


def _ms(t0: datetime) -> int:
    return int((datetime.now(UTC) - t0).total_seconds() * 1000)


def _transform(raw: str, artifact: Artifact, name: str) -> str:
    field = next((o for o in artifact.outputs if o.name == name), None)
    text = raw.strip()
    if field and field.source and field.source.transform == "parse_money":
        m = re.search(r"\$[0-9,]+\.[0-9]{2}", text)
        return m.group(0) if m else text
    if field and field.source and field.source.transform == "lower_trim":
        return text.lower().strip()
    if name == "savings_balance":
        m = re.search(r"\$[0-9,]+\.[0-9]{2}", text)
        if m:
            return m.group(0)
    return text


def _result(
    run_id: str,
    artifact: Artifact,
    started: datetime,
    status: str,
    digest: str,
    outputs: dict[str, Any] | None = None,
    outcome: Outcome | None = None,
    failure: Failure | None = None,
    steps: list[StepResult] | None = None,
    degradations: list[Degradation] | None = None,
    evidence: Evidence | None = None,
    escalation: EscalationInfo | None = None,
) -> ReplayResult:
    return ReplayResult(
        run_id=run_id,
        capability={
            "id": artifact.capability.id,
            "version": artifact.capability.version,
            "schema_version": artifact.schema_version,
        },
        status=status,  # type: ignore[arg-type]
        started_at=started.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        duration_ms=_ms(started),
        inputs_digest=digest,
        outputs=outputs or {},
        outcome=outcome,
        failure=failure,
        steps=steps or [],
        degradations=degradations or [],
        control=ControlInfo(),
        evidence_ref=str(evidence.root) if evidence else None,
        escalation=escalation,
    )


def _fail(
    run_id: str,
    artifact: Artifact,
    started: datetime,
    step: Step,
    err: HandspanError,
    surface: WebAriaSurface,
    evidence: Evidence,
    log: RunLog,
    steps: list[StepResult],
    digest: str,
    obs: Observation | None = None,
) -> ReplayResult:
    obs = obs or surface.observe(screenshot=True)
    shot = evidence.write_bytes(
        f"screenshots/{step.id}-fail.png", obs.screenshot or surface.screenshot()
    )
    ax = evidence.write_json(f"observations/{step.id}-ax.json", obs.ax_tree)
    log.emit("run.finished", status="failed", code=err.code, step=step.id)
    log.close()
    return _result(
        run_id,
        artifact,
        started,
        "failed",
        digest,
        failure=Failure(
            code=err.code,
            step=step.id,
            observed=err.message,
            evidence={"screenshot": str(shot), "ax_snapshot": str(ax)},
        ),
        steps=steps,
        evidence=evidence,
        escalation=EscalationInfo(
            raised=err.code in {Code.SESSION_EXPIRED, Code.LOCATOR_EXHAUSTED}
        ),
    )


def _escalate(
    run_id: str,
    artifact: Artifact,
    started: datetime,
    step: Step,
    surface: WebAriaSurface,
    lease: Lease,
    bus: Bus,
    evidence: Evidence,
    log: RunLog,
    bound: dict[str, str],
    why: str,
    *,
    wait_for_human: bool,
    code: str = Code.SESSION_EXPIRED,
) -> ReplayResult:
    lease.transition(LeaseState.PAUSE_REQUESTED)
    surface.pause()
    obs = surface.observe(screenshot=True)
    shot = evidence.write_bytes(f"screenshots/{step.id}-esc.png", obs.screenshot or b"")
    ax = evidence.write_json(f"observations/{step.id}-ax.json", obs.ax_tree)
    req = make_request(
        kind="blocked",
        run={"run_id": run_id, "mode": "replay", "capability": artifact.capability.id},
        stopped_at={"step": step.id, "intent": step.intent},
        why={"code": code, "message": why},
        state={"url": obs.url, "screenshot": str(shot), "ax_snapshot": str(ax)},
        inputs_redacted=redact_obj({k: v for k, v in bound.items() if k != "password"}),
        session={
            "session_id": run_id,
            "lease_state": "PAUSE_REQUESTED",
            "takeover_url": f"http://127.0.0.1:8090/operator/{run_id}",
        },
        resume_at_step=step.id,
        required_state={"kind": "ax_present", "name_matches": "Member"},
    )
    bus.publish(req)
    evidence.write_json("intervention.json", req.model_dump())
    lease.transition(LeaseState.HUMAN_HELD, holder="human")
    log.emit("escalation.raised", request_id=req.request_id)
    log.emit("lease.transferred", holder="human")
    if wait_for_human:
        ok = lease.wait_for(LeaseState.RESUME_REQUESTED, timeout_s=900)
        if not ok:
            lease.transition(LeaseState.TERMINATED)
            log.close()
            return _result(
                run_id,
                artifact,
                started,
                "escalated",
                "",
                escalation=EscalationInfo(raised=True, request_id=req.request_id, abandoned=True),
                evidence=evidence,
            )
        obs2 = surface.observe()
        from handspan.schema.conditions import Condition

        need = Condition.model_validate(
            req.resume_contract.required_state if req.resume_contract else {"kind": "none"}
        )
        if req.resume_contract and req.resume_contract.required_state and not obs2.matches(need):
            log.close()
            return _result(
                run_id,
                artifact,
                started,
                "failed",
                "",
                failure=Failure(code=Code.RESUME_STATE_MISMATCH, step=step.id),
                evidence=evidence,
            )
        lease.transition(LeaseState.AUTOMATION_HELD)
        surface.resume()
        log.emit("lease.transferred", holder="automation")
        evidence.write_text("handoff.jsonl", '{"event":"human_intervention","redacted":true}\n')
        log.close()
        return _result(
            run_id,
            artifact,
            started,
            "success",
            "",
            evidence=evidence,
            escalation=EscalationInfo(raised=True, request_id=req.request_id),
        )
    log.close()
    return _result(
        run_id,
        artifact,
        started,
        "escalated",
        "",
        escalation=EscalationInfo(raised=True, request_id=req.request_id),
        evidence=evidence,
        failure=Failure(code=code, step=step.id, observed=why),
    )
