"""Record/replay LLM cassettes. Sequence match is enough for CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Cassette:
    def __init__(self, path: Path) -> None:
        self.path = path
        raw = json.loads(path.read_text()) if path.exists() else []
        self.events: list[dict[str, Any]] = (
            raw if isinstance(raw, list) else raw.get("events") or []
        )
        self.i = 0
        self.record: list[dict[str, Any]] = []

    def next_response(self) -> dict[str, Any]:
        if self.i >= len(self.events):
            return {"action": "finish", "status": "success"}
        ev = self.events[self.i]
        self.i += 1
        return ev.get("response") or ev

    def append(self, request: Any, response: Any) -> None:
        self.record.append({"request": request, "response": response})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.record or self.events, indent=2) + "\n")
