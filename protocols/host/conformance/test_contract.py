# Copyright 2026 Marimo. All rights reserved.
"""Shared wire examples and regression checks for the conformance probes."""

from __future__ import annotations

import asyncio
import copy
import json

import httpx
import pytest
from contract import (
    ROOT,
    SPEC,
    Frame,
    Host,
    Watch,
    document_state,
    frames,
    validate,
)
from jsonschema import Draft202012Validator, ValidationError

FIXTURES = ROOT / "fixtures"
MODELS = {
    "record.json": "HostRecord",
    "cell.json": "Cell",
    "diagnostic.json": "Error",
    "edit.json": "EditRequest",
    "edit-response.json": "EditResponse",
    "execution-restored.json": "Execution",
}


async def lines(text):
    for line in text.splitlines():
        yield line


def test_schemas_are_valid():
    for schema in SPEC["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    "path", sorted(FIXTURES.rglob("*.json")), ids=lambda p: p.name
)
def test_json_examples(path):
    validate(
        "Problem" if path.parent.name == "problems" else MODELS[path.name],
        json.loads(path.read_text()),
    )


@pytest.mark.parametrize(
    "path", sorted(FIXTURES.glob("*.sse")), ids=lambda p: p.name
)
async def test_stream_examples(path):
    found = [frame async for frame in frames(lines(path.read_text()))]
    assert found
    for frame in found:
        if frame.comment is None:
            frame.message()


async def test_sse_preserves_multiline_data_comments_and_explicit_ids():
    stream = ": ping\r\nid: 7\r\nevent: future\r\ndata: one\r\ndata:  two\r\n\r\nevent: ready\ndata: {}\n\n"
    assert [frame async for frame in frames(lines(stream))] == [
        Frame(comment="ping"),
        Frame(event="future", data="one\n two", id="7"),
        Frame(event="ready", data="{}"),
    ]


def test_required_nullable_fields_and_future_fields():
    value = json.loads((FIXTURES / "execution-restored.json").read_text())
    validate("Execution", {**value, "future_field": True})
    for field in ("run_id", "runtime_id", "caused_by"):
        missing = {key: item for key, item in value.items() if key != field}
        with pytest.raises(ValidationError):
            validate("Execution", missing)
        with pytest.raises(ValidationError):
            validate("Execution", {**value, field: ""})


async def test_document_checker_rejects_wrong_hashes_and_ordering():
    snapshot = []
    async for frame in frames(
        lines((FIXTURES / "notebook-events.sse").read_text())
    ):
        if frame.event == "ready":
            break
        snapshot.append(frame)
    document_state(snapshot)
    broken = copy.deepcopy(snapshot)
    cell = next(frame for frame in broken if frame.event == "cell")
    message = cell.message()
    message["cell"]["code"] += "\n# changed"
    cell.data = json.dumps(message)
    with pytest.raises(AssertionError):
        document_state(broken)
    with pytest.raises(AssertionError, match="cell arrived after"):
        document_state(
            sorted(snapshot, key=lambda frame: frame.event != "document")
        )


async def test_stalled_response_headers_have_a_deadline():
    async def stalled(_request):
        await asyncio.Event().wait()

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1/", transport=httpx.MockTransport(stalled)
    ) as client:
        host = Host(client, timeout=0.01)
        with pytest.raises(TimeoutError):
            async with host.watch():
                pytest.fail("stalled headers should time out")


async def test_pings_do_not_extend_a_wait_for_ready():
    async def pings():
        while True:
            await asyncio.sleep(0)
            yield Frame(comment="ping")

    watch = Watch(pings(), timeout=0.01)
    with pytest.raises(TimeoutError):
        await watch.ready()
