"""Build an InterventionRequest (PRD §12.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from handspan.schema.results import InterventionRequest, ResumeContract


def make_request(
    *,
    kind: str,
    run: dict,
    stopped_at: dict,
    why: dict,
    state: dict,
    inputs_redacted: dict,
    session: dict,
    resume_at_step: str,
    required_state: dict | None = None,
) -> InterventionRequest:
    rid = "int_" + uuid4().hex[:10]
    return InterventionRequest(
        request_id=rid,
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        kind=kind,
        run=run,
        stopped_at=stopped_at,
        why=why,
        state=state,
        inputs_redacted=inputs_redacted,
        session=session,
        resume_contract=ResumeContract(
            resume_at_step=resume_at_step,
            required_state=required_state or {},
        ),
    )
