from pathlib import Path

from handspan.replay.executor import replay

ART = "evidence/artifacts/cap.member.read_savings_balance.yaml"


def test_happy_path(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a},
        evidence_dir=tmp_path / "ev",
        persist_outputs=True,
    )
    assert result.status == "success"
    assert result.outputs["savings_balance"] == "$4,215.60"
    assert result.outputs["account_status"] == "active"


def test_member_not_found(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "999999", "base_url": bank_a},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "business_outcome"
    assert result.outcome and result.outcome.code == "MEMBER_NOT_FOUND"


def test_invalid_input(bank_a: str, tmp_path: Path) -> None:
    result = replay(ART, {"member_id": "nope", "base_url": bank_a}, evidence_dir=tmp_path / "ev")
    assert result.status == "failed"
    assert result.failure and result.failure.code == "INVALID_INPUT"


def test_fault_notfound(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "notfound"},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "business_outcome"
    assert result.outcome and result.outcome.code == "MEMBER_NOT_FOUND"


def test_fault_denied(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "denied"},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "business_outcome"
    assert result.outcome and result.outcome.code == "PERMISSION_DENIED"


def test_fault_500(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "500"},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "failed"
    assert result.failure and result.failure.code == "APP_ERROR"


def test_fault_expire(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "expire"},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status in {"failed", "escalated"}
    code = (result.failure.code if result.failure else "") or ""
    assert "SESSION" in code or result.status == "escalated"


def test_fault_dialog(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "dialog"},
        evidence_dir=tmp_path / "ev",
        persist_outputs=True,
    )
    assert result.status == "success"
    assert result.outputs["savings_balance"] == "$4,215.60"


def test_fault_dupname(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "dupname"},
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "failed"
    assert result.failure and result.failure.code == "AMBIGUOUS_TARGET"


def test_fault_slow(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_a, "fault": "slow"},
        evidence_dir=tmp_path / "ev",
        persist_outputs=True,
    )
    assert result.status == "success"


def test_fault_validation(bank_a: str, tmp_path: Path) -> None:
    result = replay(
        "evidence/artifacts/cap.member.open_subaccount.yaml",
        {
            "member_id": "100234",
            "base_url": bank_a,
            "fault": "validation",
            "nickname": "x",
            "amount": "1",
        },
        evidence_dir=tmp_path / "ev",
    )
    assert result.status == "business_outcome"
    assert result.outcome and result.outcome.code == "VALIDATION_REJECTED"


def test_policy_blocks_admin_navigation(bank_a: str, tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    art = YAML(typ="safe").load(Path(ART).read_text())
    art["steps"] = [
        {
            "id": "s1",
            "intent": "sneak",
            "action": "navigate",
            "url_template": bank_a + "/admin/users",
        }
    ]
    p = tmp_path / "bad.yaml"
    YAML().dump(art, p.open("w"))
    result = replay(p, {"member_id": "100234", "base_url": bank_a}, evidence_dir=tmp_path / "ev")
    assert result.status == "failed"
    assert result.failure and result.failure.code == "POLICY_BLOCKED"


def test_tenant_b_overlay(bank_b: str, tmp_path: Path) -> None:
    result = replay(
        ART,
        {"member_id": "100234", "base_url": bank_b},
        overlay="evidence/artifacts/overlays/tenant_b.patch.yaml",
        evidence_dir=tmp_path / "ev",
        persist_outputs=True,
    )
    assert result.status == "success"
    assert result.outputs["savings_balance"] == "$4,215.60"
