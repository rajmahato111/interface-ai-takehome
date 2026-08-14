"""Redact at capture time. Replacement «redacted:kind:suffix» with salted hash."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SALT = "handspan-local-redaction-salt"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("pan", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")),
    ("cookie", re.compile(r"(?i)(?:set-)?cookie:\s*[^\s;]+")),
    ("account", re.compile(r"\b\d{10,17}\b")),
]


def _suffix(value: str) -> str:
    digest = hashlib.sha256((SALT + value).encode()).hexdigest()
    return digest[:4]


def redact_text(text: str) -> str:
    out = text
    for kind, pat in _PATTERNS:

        def repl(m: re.Match[str], kind: str = kind) -> str:
            return f"«redacted:{kind}:{_suffix(m.group(0))}»"

        out = pat.sub(repl, out)
    return out


def redact_obj(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


def redact_json(obj: Any) -> str:
    return json.dumps(redact_obj(obj), default=str)


def looks_like_pan(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    if not (13 <= len(digits) <= 19):
        return False
    # Luhn
    s = 0
    alt = False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        s += n
        alt = not alt
    return s % 10 == 0
