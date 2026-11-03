# Copyright 2026 Marimo. All rights reserved.
"""Portable slider contract examples and stable-client compatibility."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from contract import Frame, Watch, frames
from generate import compose
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def validate(name: str, value: Any) -> None:
    spec = compose("ui_element")
    Draft202012Validator(
        {
            "$ref": f"#/components/schemas/{name}",
            "components": spec["components"],
        },
        format_checker=FormatChecker(),
    ).validate(value)


def test_slider_record() -> None:
    validate("UIElement", json.loads((FIXTURES / "slider.json").read_text()))


@pytest.mark.parametrize("state", [{"value": 4}, {}, {"value": None}])
def test_update_accepts_partial_wire_state(state: Any) -> None:
    validate("UIElementUpdateRequest", {"state": state})


@pytest.mark.parametrize("state", [{"other": 4}, [], 4])
def test_update_rejects_invalid_state(state: Any) -> None:
    with pytest.raises(ValidationError):
        validate("UIElementUpdateRequest", {"state": state})


async def lines(text: str) -> AsyncIterator[str]:
    for line in text.splitlines():
        yield line


async def test_slider_lifecycle_fixture() -> None:
    events = []
    async for frame in frames(lines((FIXTURES / "slider.sse").read_text())):
        event = {"event": frame.event, "data": json.loads(frame.data)}
        if frame.id is not None:
            event["id"] = frame.id
        validate("Event", event)
        events.append(frame.event)
    assert events == [
        "ui_element",
        "ready",
        "ui_element.update",
        "ui_element.removed",
    ]


async def test_stable_probe_keeps_cursor_for_unknown_events() -> None:
    stream = "id: 7\nevent: ui_element.update\ndata: {}\n\nid: 7\nevent: ready\ndata: {}\n\n"
    assert await Watch(frames(lines(stream)), timeout=1).ready() == [
        Frame(event="ui_element.update", data="{}", id="7"),
        Frame(event="ready", data="{}", id="7"),
    ]
