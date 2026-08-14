#!/usr/bin/env python3
"""Write a 10-run stability report into evidence/replay/rpl_success/."""

from __future__ import annotations

import json
from pathlib import Path

from handspan.replay.executor import replay


def main() -> None:
    base = Path("evidence/replay/rpl_success")
    base.mkdir(parents=True, exist_ok=True)
    runs = []
    for i in range(10):
        r = replay(
            "evidence/artifacts/cap.member.read_savings_balance.yaml",
            {"member_id": "100234"},
            evidence_dir=base / f"run_{i:02d}",
            persist_outputs=True,
        )
        runs.append(
            {
                "i": i,
                "status": r.status,
                "outputs": r.outputs,
                "steps": [s.id for s in r.steps],
            }
        )
    ok = all(x["status"] == "success" and x["outputs"] == runs[0]["outputs"] for x in runs)
    report = {"runs": 10, "identical": ok, "sample": runs[0], "all": runs}
    (base / "stability.json").write_text(json.dumps(report, indent=2) + "\n")
    print("stability identical" if ok else "stability DIVERGED")


if __name__ == "__main__":
    main()
