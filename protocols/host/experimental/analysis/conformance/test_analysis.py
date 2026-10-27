# Copyright 2026 Marimo. All rights reserved.
"""Analysis's experimental contract and its compatibility with stable streams."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from contract import Frame, Watch, frames
from generate import compose
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SPEC = compose("analysis")


def validate(name: str, value: Any) -> None:
    Draft202012Validator(
        {
            "$ref": f"#/components/schemas/{name}",
            "components": SPEC["components"],
        },
        format_checker=FormatChecker(),
    ).validate(value)


async def lines(text: str) -> AsyncIterator[str]:
    for line in text.splitlines():
        yield line


@pytest.mark.parametrize(
    ("filename", "schema"),
    [("analysis.json", "Analysis"), ("diagnostic.json", "Error")],
)
def test_examples(filename: str, schema: str) -> None:
    validate(schema, json.loads((FIXTURES / filename).read_text()))


def test_schemas_are_valid() -> None:
    for schema in SPEC["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("message", [{}, {"analysis": {}}])
def test_invalid_analysis_messages_are_rejected(message: Any) -> None:
    with pytest.raises(ValidationError):
        validate("AnalysisMessage", message)


async def test_analysis_follows_document_and_matches_revision() -> None:
    document = None
    found = []
    async for frame in frames(
        lines((FIXTURES / "notebook-events.sse").read_text())
    ):
        if frame.comment is not None:
            continue
        message = json.loads(frame.data)
        validate(
            "Event",
            {
                "event": frame.event,
                "data": message,
                **({"id": frame.id} if frame.id is not None else {}),
            },
        )
        if frame.event == "document":
            document = message["document"]
        elif frame.event == "analysis":
            analysis = message["analysis"]
            assert document is not None
            assert analysis["document_etag"] == document["etag"]
            assert analysis["notebook_id"] == document["notebook_id"]
            assert set(analysis["cells"]) == set(document["order"])
            found.append(analysis)
    assert found == [json.loads((FIXTURES / "analysis.json").read_text())]


async def test_stable_probe_ignores_experimental_payloads() -> None:
    # A stable consumer must not validate a contract it has not selected.
    stream = (
        "id: 1\nevent: analysis\ndata: {}\n\nid: 1\nevent: ready\ndata: {}\n\n"
    )
    assert await Watch(frames(lines(stream)), timeout=1).ready() == [
        Frame(event="analysis", data="{}", id="1"),
        Frame(event="ready", data="{}", id="1"),
    ]
