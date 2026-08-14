"""Observe → decide → act. Compiles a capability artifact. Auto-replays once."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ruamel.yaml import YAML

from handspan.discovery.compiler import compile_trace
from handspan.discovery.limits import Limits
from handspan.discovery.prompts import SYSTEM, user_prompt
from handspan.discovery.tools import TOOLS
from handspan.escalation.detector import dead_end, policy_loop
from handspan.llm.cassette import Cassette
from handspan.llm.client import decide
from handspan.obs.evidence import Evidence
from handspan.obs.logger import RunLog
from handspan.policy.allowlist import Allowlist
from handspan.schema.capability import Step, Strategy, Target
from handspan.surface.web_aria import WebAriaSurface


def discover(
    goal: str,
    target: str,
    *,
    cassette_path: Path | None = None,
    live: bool = False,
    headless: bool = True,
    evidence_dir: Path | None = None,
    inputs: dict[str, str] | None = None,
    auto_replay: bool = True,
) -> Path:
    run_id = "dsc_" + uuid4().hex[:8]
    evidence = Evidence(evidence_dir or Path("evidence/discovery") / run_id)
    log = RunLog(evidence.root / "run.jsonl", run_id)
    cassette = Cassette(cassette_path) if cassette_path else None
    allow = Allowlist.load("policies/corevantage.yaml")
    inputs = inputs or {"member_id": "100234", "username": "teller", "password": "teller"}
    surface = WebAriaSurface.launch(headless=headless, start_url=target)
    limits = Limits()
    trace: list[dict[str, Any]] = []
    last_digest = ""
    no_change = 0
    blocks = 0
    stop = "GOAL_REACHED"
    try:
        if "login" in surface.page.url or "Sign On" in surface.observe().ax_text:
            surface.login(inputs.get("username", "teller"), inputs.get("password", "teller"))
        try:
            surface.page.frame_locator("frame[name=nav]").get_by_role(
                "link", name="Member Search"
            ).wait_for(timeout=8000)
        except Exception:
            pass
        while True:
            reason = limits.tick()
            if reason:
                stop = reason
                break
            obs = surface.observe(screenshot=True)
            evidence.write_json(f"observations/s{limits.steps:02d}.ax.json", obs.ax_tree)
            if obs.screenshot:
                evidence.write_bytes(f"screenshots/s{limits.steps:02d}.png", obs.screenshot)
            if obs.digest == last_digest:
                no_change += 1
            else:
                no_change = 0
            last_digest = obs.digest
            if dead_end(no_change):
                stop = "DEAD_END"
                break
            ax = surface.compact_ax()
            decision = decide(
                system=SYSTEM,
                user=user_prompt(goal, obs.ax_text, ax, obs.url, 25 - limits.steps),
                tools=TOOLS,
                cassette=cassette,
                live=live,
            )
            log.emit("llm.responded", action=decision.get("action"))
            action = decision.get("action") or "finish"
            if action == "finish":
                trace.append({"action": "finish", "status": "success"})
                stop = "GOAL_REACHED"
                break
            if action == "escalate":
                stop = "ESCALATED"
                break
            try:
                allow.check_action(action)
                if action == "navigate":
                    allow.check_url(decision.get("url_template") or obs.url)
            except Exception as e:  # noqa: BLE001
                blocks += 1
                log.emit("policy.blocked", error=str(e))
                if policy_loop(blocks):
                    stop = "POLICY_BLOCKED"
                    break
                continue
            blocks = 0
            step = _decision_to_step(decision)
            handle = None
            try:
                if step.target:
                    handle = surface.resolve(step.target)
                result = surface.act(step, handle, inputs)
            except Exception as e:  # noqa: BLE001
                log.emit("action.failed", action=action, error=str(e))
                trace.append({**decision, "noop": True})
                continue
            trace.append({**decision, "noop": not result.ok})
            log.emit("action.dispatched", action=action, ok=result.ok)
        artifact = compile_trace(
            goal=goal, run_id=run_id, trace=trace, inputs=inputs, target_url=target
        )
        yaml = YAML()
        yaml.default_flow_style = False
        dest = evidence.root / "artifact.yaml"
        with dest.open("w") as fh:
            yaml.dump(artifact.model_dump(mode="json"), fh)
        evidence.write_text(
            "README.md", f"Discovery run {run_id}\nstop_reason: {stop}\ngoal: {goal}\n"
        )
        evidence.write_json("result.json", {"stop_reason": stop, "run_id": run_id})
        if cassette and live:
            cassette.save()
        if auto_replay and stop == "GOAL_REACHED":
            from handspan.replay.executor import replay as do_replay

            do_replay(
                dest,
                {
                    "member_id": inputs.get("member_id", "100234"),
                    "base_url": target.rsplit("/servicing", 1)[0],
                },
                headless=headless,
                evidence_dir=evidence.root / "auto_replay",
            )
        return dest
    finally:
        log.close()
        surface.close()


def _decision_to_step(d: dict[str, Any]) -> Step:
    action = d["action"]
    name = d.get("name") or d.get("label") or ""
    role = d.get("role") or ("textbox" if action == "type" else "button")
    frame = d.get("frame")
    target = None
    if action == "type":
        target = Target(
            frame=frame or "content",
            strategies=[
                Strategy(kind="css", value="input[id$='txt1'], input[id$='srch_q']"),
                Strategy(kind="ax_label_proximity", label=name, direction="right"),
                Strategy(kind="table_cell_neighbour", label_text=name, cell_offset=[0, 1]),
            ],
            match_policy="require_unique",
        )
    elif action == "extract":
        target = Target(
            frame=frame or "content",
            strategies=[
                Strategy(kind="ax_label_proximity", label=name, direction="right"),
                Strategy(kind="table_cell_neighbour", label_text=name, cell_offset=[0, 1]),
                Strategy(
                    kind="regex_in_region",
                    region_anchor=(name.split()[0] if name else "Savings"),
                    pattern=r"\$[0-9,]+\.[0-9]{2}",
                ),
            ],
            match_policy="first",
        )
    elif action == "click" and (
        role == "link" or name in {"Member Search", "Home", "Open Sub-Account"}
    ):
        target = Target(
            frame=frame or ("content" if name == "Open Sub-Account" else "nav"),
            strategies=[
                Strategy(kind="ax_role_name", role="link", name=name, match="fuzzy"),
                Strategy(kind="css", value=f"a:has-text('{name}')"),
            ],
            match_policy="first",
        )
    elif action not in {"finish", "escalate", "navigate", "confirm_dialog"}:
        target = Target(
            frame=frame or "content",
            strategies=[
                Strategy(kind="ax_role_name", role=role, name=name, match="fuzzy"),
                Strategy(kind="css", value=f"input[type=submit][value='{name}']"),
                Strategy(kind="css", value="input[type=submit]"),
            ],
            match_policy="first",
        )
    kwargs: dict[str, Any] = {
        "id": "d",
        "action": action,
        "target": target,
        "intent": d.get("rationale") or "",
    }
    if action == "type":
        kwargs["value"] = (
            {"from_input": d["value_from_input"]}
            if d.get("value_from_input")
            else {"literal": d.get("literal")}
        )
    if action == "extract":
        kwargs["extract_to"] = d.get("extract_to")
    if action == "navigate":
        kwargs["url_template"] = d.get("url_template")
    if action == "confirm_dialog":
        kwargs["accept_names"] = d.get("accept_names") or ["OK"]
    return Step.model_validate(kwargs)
