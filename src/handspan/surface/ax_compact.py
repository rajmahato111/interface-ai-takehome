"""AX tree → LLM-sized view. Relevance, not depth: interactive + near last action."""

from __future__ import annotations

from typing import Any

INTERACTIVE = {
    "button",
    "link",
    "textbox",
    "searchbox",
    "combobox",
    "checkbox",
    "radio",
    "menuitem",
    "tab",
    "option",
    "input",
    "select",
    "textarea",
    "submit",
}


def compact(
    tree: dict[str, Any], *, cap: int = 80, last_name: str | None = None
) -> list[dict[str, Any]]:
    nodes = _flatten(tree)
    scored: list[tuple[int, dict[str, Any]]] = []
    for n in nodes:
        role = str(n.get("role") or "").lower()
        name = str(n.get("name") or n.get("value") or "")
        score = 0
        if role in INTERACTIVE:
            score += 5
        if name:
            score += 1
        if last_name and last_name.lower() in name.lower():
            score += 4
        if score:
            scored.append(
                (score, {"role": role, "name": name[:80], "value": str(n.get("value") or "")[:80]})
            )
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:cap]]


def _flatten(tree: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not tree:
        return out
    if "nodes" in tree and isinstance(tree["nodes"], list):
        for n in tree["nodes"]:
            if isinstance(n, dict):
                out.append(n)
                out.extend(_flatten(n))
        return out
    out.append(tree)
    for child in tree.get("children") or []:
        if isinstance(child, dict):
            out.extend(_flatten(child))
    return out
