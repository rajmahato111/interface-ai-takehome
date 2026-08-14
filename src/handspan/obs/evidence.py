"""Evidence bundle writer. Screenshots treated as PII (0700 dir)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from handspan.policy.redaction import redact_obj


class Evidence:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(
                "Evidence bundle. Retention: 7 days, local only. Screenshots are PII.\n"
            )

    def write_json(self, rel: str, obj: Any) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(redact_obj(obj), indent=2, default=str) + "\n")
        return path

    def write_bytes(self, rel: str, data: bytes) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_text(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path
