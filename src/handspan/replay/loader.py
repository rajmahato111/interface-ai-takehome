"""Load YAML artifacts and merge tenant overlays. Overlays cannot change the caller contract."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML

from handspan.errors.taxonomy import Code, HardFailure
from handspan.schema.capability import Artifact

_yaml = YAML(typ="safe")
CONTRACT_KEYS = {"outputs", "outcomes"}


def load(path: str | Path, *, overlay: str | Path | None = None) -> Artifact:
    data = _yaml.load(Path(path).read_text())
    if not isinstance(data, dict):
        raise HardFailure(Code.SCHEMA_INCOMPATIBLE, "artifact is not a mapping")
    if overlay:
        data = apply_overlay(data, _yaml.load(Path(overlay).read_text()))
    try:
        return Artifact.model_validate(data)
    except ValidationError as e:
        msg = str(e)
        if "SCHEMA_INCOMPATIBLE" in msg or "schema_version" in msg:
            raise HardFailure(Code.SCHEMA_INCOMPATIBLE, msg) from e
        raise HardFailure(Code.SCHEMA_INCOMPATIBLE, msg) from e


def apply_overlay(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    patch = overlay.get("patch") or overlay
    for key in CONTRACT_KEYS:
        if key in patch:
            raise HardFailure(Code.SCHEMA_INCOMPATIBLE, f"overlay cannot change {key}")
    if "policy" in patch and "risk_class" in (patch.get("policy") or {}):
        raise HardFailure(Code.SCHEMA_INCOMPATIBLE, "overlay cannot change policy.risk_class")
    out = copy.deepcopy(base)
    step_patch = patch.get("steps") or {}
    steps = list(out.get("steps") or [])
    by_id = {s["id"]: i for i, s in enumerate(steps) if isinstance(s, dict) and "id" in s}
    for sid, spec in step_patch.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("after"):
            insert_at = by_id.get(spec["after"], len(steps) - 1) + 1
            new_step = {k: v for k, v in spec.items() if k != "after"}
            new_step.setdefault("id", sid)
            steps.insert(insert_at, new_step)
            by_id = {s["id"]: i for i, s in enumerate(steps) if isinstance(s, dict) and "id" in s}
            continue
        if sid in by_id:
            _deep_merge(steps[by_id[sid]], spec)
    out["steps"] = steps
    if "inputs" in patch:
        extra = patch["inputs"]
        if isinstance(extra, list):
            out.setdefault("inputs", []).extend(extra)
    return out


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
