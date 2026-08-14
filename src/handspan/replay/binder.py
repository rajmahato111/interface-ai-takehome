"""Bind caller params to typed input values. Fail fast as INVALID_INPUT."""

from __future__ import annotations

import hashlib
import json
import re

from handspan.errors.taxonomy import Code, HardFailure
from handspan.schema.capability import Artifact, InputParam


def bind(artifact: Artifact, params: dict[str, str]) -> tuple[dict[str, str], str]:
    bound: dict[str, str] = {}
    for spec in artifact.inputs:
        if spec.name in params:
            value = params[spec.name]
        elif spec.default is not None:
            value = spec.default
        elif spec.required:
            raise HardFailure(Code.INVALID_INPUT, f"missing required input {spec.name}")
        else:
            continue
        _validate(spec, value)
        bound[spec.name] = value
    digest = hashlib.sha256(json.dumps(sorted(bound.items())).encode()).hexdigest()
    return bound, "sha256:" + digest[:12]


def _validate(spec: InputParam, value: str) -> None:
    if spec.pattern and re.fullmatch(spec.pattern, value) is None:
        raise HardFailure(Code.INVALID_INPUT, f"{spec.name} does not match {spec.pattern}")
    if spec.values and value not in spec.values:
        raise HardFailure(Code.INVALID_INPUT, f"{spec.name} not in {spec.values}")
