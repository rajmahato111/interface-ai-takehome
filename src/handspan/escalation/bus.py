"""Filesystem intervention bus. Swap for a queue later."""

from __future__ import annotations

import json
from pathlib import Path

from handspan.schema.results import InterventionRequest


class Bus:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, req: InterventionRequest) -> Path:
        path = self.root / f"{req.request_id}.json"
        path.write_text(req.model_dump_json(indent=2) + "\n")
        return path

    def load(self, request_id: str) -> InterventionRequest:
        path = self.root / f"{request_id}.json"
        return InterventionRequest.model_validate(json.loads(path.read_text()))
