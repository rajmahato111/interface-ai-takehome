"""Thin Anthropic port. Temperature 0. Cassettes for CI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from handspan.llm.cassette import Cassette


def load_dotenv() -> None:
    """Pull KEY=value lines from .env into os.environ if missing."""
    candidates = [Path(".env"), Path(__file__).resolve().parents[3] / ".env"]
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
        break


def decide(
    *,
    system: str,
    user: str,
    tools: list[dict[str, Any]],
    cassette: Cassette | None = None,
    live: bool = False,
) -> dict[str, Any]:
    if cassette is not None and not live:
        return cassette.next_response()
    if not live and cassette is None:
        raise RuntimeError("no cassette and not --live")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1024,
        temperature=0,
        system=system,
        tools=tools,
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            out = {"action": block.name, **dict(block.input)}
            if cassette is not None:
                cassette.append({"user": user[:2000]}, out)
            return out
    text = "".join(getattr(b, "text", "") or "" for b in resp.content)
    return {"action": "finish", "status": "success", "rationale": text}
