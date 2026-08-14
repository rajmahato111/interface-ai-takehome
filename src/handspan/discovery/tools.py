"""Closed action vocabulary as Anthropic tool definitions."""

from __future__ import annotations

from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "click",
        "description": "Click a control identified by role and accessible name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "role": {"type": "string"},
                "name": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["role", "name"],
        },
    },
    {
        "name": "type",
        "description": "Type a value into a field. Prefer value_from_input over literals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "role": {"type": "string"},
                "name": {"type": "string"},
                "value_from_input": {"type": "string"},
                "literal": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["role", "name"],
        },
    },
    {
        "name": "navigate",
        "description": "Navigate the current page or named frame to a URL template.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url_template": {"type": "string"},
                "frame": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["url_template"],
        },
    },
    {
        "name": "extract",
        "description": "Read text from a labelled region into an output field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "label": {"type": "string"},
                "extract_to": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["label", "extract_to"],
        },
    },
    {
        "name": "select",
        "description": "Choose an option in a combobox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "role": {"type": "string"},
                "name": {"type": "string"},
                "option": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["name", "option"],
        },
    },
    {
        "name": "submit_form",
        "description": "Submit the current form (risky if side effects).",
        "input_schema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "name": {"type": "string"},
                "rationale": {"type": "string"},
            },
        },
    },
    {
        "name": "confirm_dialog",
        "description": "Accept a dialog by button name.",
        "input_schema": {
            "type": "object",
            "properties": {"accept_names": {"type": "array", "items": {"type": "string"}}},
        },
    },
    {
        "name": "escalate",
        "description": "Stop and ask a human to take the live session.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "finish",
        "description": "Goal reached. Optionally include outputs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "outputs": {"type": "object"},
            },
        },
    },
]
