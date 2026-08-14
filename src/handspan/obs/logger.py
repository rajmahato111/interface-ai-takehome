"""JSONL run log. Every record is redacted before it hits a buffer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from handspan.policy.redaction import redact_obj


class RunLog:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.seq = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def emit(self, event: str, level: str = "info", **fields: Any) -> None:
        self.seq += 1
        rec = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "run_id": self.run_id,
            "seq": self.seq,
            "level": level,
            "event": event,
            **fields,
        }
        self._fh.write(json.dumps(redact_obj(rec), default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
