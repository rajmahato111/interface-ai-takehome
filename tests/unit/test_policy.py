from pathlib import Path

from pytest import raises
from tests.fixtures.pii_corpus import CORPUS, PAN_SAMPLE, SSN_SAMPLE

from handspan.errors.taxonomy import HardFailure
from handspan.policy.allowlist import Allowlist
from handspan.policy.redaction import redact_text
from handspan.policy.risk import gate_risky


def test_allowlist_blocks_admin() -> None:
    al = Allowlist.load("policies/corevantage.yaml")
    al.check_url("http://127.0.0.1:8081/member/search")
    with raises(HardFailure, match="denied"):
        al.check_url("http://127.0.0.1:8081/admin/users")


def test_allowlist_blocks_denied_action() -> None:
    al = Allowlist.load("policies/corevantage.yaml")
    with raises(HardFailure):
        al.check_action("file_download")


def test_unattended_risky_blocked() -> None:
    with raises(HardFailure):
        gate_risky("submit_form", mode="unattended", step_risk="risky", side_effects="reversible")


def test_redaction_ssn_and_pan() -> None:
    text = f"ssn {SSN_SAMPLE} card {PAN_SAMPLE}"
    out = redact_text(text)
    assert SSN_SAMPLE not in out
    assert PAN_SAMPLE not in out
    assert "redacted:ssn" in out
    assert "redacted:pan" in out


def test_artifacts_have_no_pii_corpus() -> None:
    blob = ""
    for p in Path("evidence").rglob("*"):
        if p.is_file() and p.suffix in {".yaml", ".json", ".jsonl", ".md"}:
            blob += p.read_text(errors="ignore")
    for item in CORPUS:
        assert item not in blob
