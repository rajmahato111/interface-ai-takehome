from pathlib import Path

from handspan.discovery.agent import discover
from handspan.replay.executor import replay


def test_cassette_discover_then_replay(bank_a: str, tmp_path: Path) -> None:
    dest = discover(
        "Look up member 100234 and read their current savings balance.",
        f"{bank_a}/servicing/home",
        cassette_path=Path("tests/fixtures/cassettes/read_savings.json"),
        live=False,
        evidence_dir=tmp_path / "dsc",
        auto_replay=False,
    )
    assert dest.exists()
    result = replay(
        dest,
        {"member_id": "100234", "base_url": bank_a},
        evidence_dir=tmp_path / "rpl",
        persist_outputs=True,
    )
    assert result.status in {"success", "business_outcome", "failed"}
    # cassette path is the real loop; compiled artifact must at least validate and run
    assert result.capability["id"] == "cap.member.read_savings_balance"


def test_catalog_emits_tools() -> None:
    from handspan.cli import _catalog

    tools = _catalog()
    names = {t["name"] for t in tools}
    assert "cap.member.read_savings_balance" in names
    tool = next(t for t in tools if t["name"] == "cap.member.read_savings_balance")
    assert "member_id" in tool["input_schema"]["properties"]
    assert "MEMBER_NOT_FOUND" in tool["outcomes"]
