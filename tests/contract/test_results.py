from handspan.schema.results import InterventionRequest, ReplayResult


def test_replay_result_roundtrip(snapshot) -> None:  # type: ignore[no-untyped-def]
    r = ReplayResult(
        run_id="rpl_test",
        capability={
            "id": "cap.member.read_savings_balance",
            "version": 1,
            "schema_version": "1.0.0",
        },
        status="success",
        started_at="2026-08-12T09:14:19.220Z",
        outputs={"savings_balance": "$4,215.60"},
    )
    assert r.model_dump() == snapshot


def test_intervention_shape() -> None:
    req = InterventionRequest(
        request_id="int_test",
        created_at="2026-08-12T09:20:41Z",
        kind="blocked",
    )
    assert req.allowed_human_actions
