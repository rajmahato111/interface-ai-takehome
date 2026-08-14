from pathlib import Path

from pydantic import ValidationError
from pytest import raises

from handspan.errors.taxonomy import Code
from handspan.replay.binder import bind
from handspan.replay.loader import apply_overlay, load
from handspan.schema.capability import Artifact, Step


def test_unknown_action_rejected() -> None:
    with raises(ValidationError, match="unknown action"):
        Step.model_validate({"id": "s1", "action": "teleport", "intent": "nope"})


def test_schema_version_gate() -> None:
    from handspan.errors.taxonomy import HardFailure

    p = Path("evidence/artifacts/cap.member.read_savings_balance.yaml")
    data = p.read_text().replace('schema_version: "1.0.0"', 'schema_version: "2.0.0"', 1)
    bad = Path("/tmp/bad-artifact.yaml")
    bad.write_text(data)
    with raises(HardFailure) as ei:
        load(bad)
    assert ei.value.code == Code.SCHEMA_INCOMPATIBLE


def test_load_seed_artifact() -> None:
    art = load("evidence/artifacts/cap.member.read_savings_balance.yaml")
    assert isinstance(art, Artifact)
    assert art.capability.id == "cap.member.read_savings_balance"
    assert all(s.action != "teleport" for s in art.steps)


def test_binder_bad_member_id() -> None:
    art = load("evidence/artifacts/cap.member.read_savings_balance.yaml")
    from handspan.errors.taxonomy import HardFailure

    with raises(HardFailure) as ei:
        bind(art, {"member_id": "abc"})
    assert ei.value.code == Code.INVALID_INPUT


def test_overlay_cannot_change_outputs() -> None:
    from handspan.errors.taxonomy import HardFailure

    with raises(HardFailure):
        apply_overlay({"outputs": []}, {"patch": {"outputs": [{"name": "x"}]}})


def test_overlay_renames_find_button() -> None:
    art = load(
        "evidence/artifacts/cap.member.read_savings_balance.yaml",
        overlay="evidence/artifacts/overlays/tenant_b.patch.yaml",
    )
    s3 = next(s for s in art.steps if s.id == "s3")
    assert s3.target and s3.target.strategies[0].name == "Search"
