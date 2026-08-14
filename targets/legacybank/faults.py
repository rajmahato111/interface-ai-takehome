"""?fault= control plane. Stored on the session so later pages apply it."""

from __future__ import annotations

FAULTS = (
    "slow",
    "dialog",
    "notfound",
    "validation",
    "denied",
    "expire",
    "500",
    "dupname",
)
