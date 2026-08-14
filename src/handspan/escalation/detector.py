"""Stuck / dead-end / policy-loop detection."""

from __future__ import annotations


def dead_end(no_change_streak: int, limit: int = 3) -> bool:
    return no_change_streak >= limit


def policy_loop(same_block_streak: int, limit: int = 2) -> bool:
    return same_block_streak >= limit
