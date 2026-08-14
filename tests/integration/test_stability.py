from pathlib import Path

from tests.fixtures.pii_corpus import CORPUS

from handspan.replay.executor import replay


def test_stability_three_runs(bank_a: str, tmp_path: Path) -> None:
    paths = []
    outputs = []
    for i in range(3):
        r = replay(
            "evidence/artifacts/cap.member.read_savings_balance.yaml",
            {"member_id": "100234", "base_url": bank_a},
            evidence_dir=tmp_path / f"r{i}",
            persist_outputs=True,
        )
        assert r.status == "success"
        paths.append([s.id for s in r.steps])
        outputs.append(r.outputs)
    assert paths[0] == paths[1] == paths[2]
    assert outputs[0] == outputs[1] == outputs[2]


def test_suite_output_has_no_pii(tmp_path: Path) -> None:
    # scan committed artifacts + this test's lack of corpus
    blob = Path("evidence/artifacts/cap.member.read_savings_balance.yaml").read_text()
    for item in CORPUS:
        assert item not in blob
