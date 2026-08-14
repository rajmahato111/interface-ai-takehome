"""Write docs/capability-schema.json from the Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from handspan.schema.capability import Artifact


def export(path: Path | None = None) -> Path:
    dest = path or Path("docs/capability-schema.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(Artifact.model_json_schema(), indent=2) + "\n")
    return dest


if __name__ == "__main__":
    p = export()
    print(p)
