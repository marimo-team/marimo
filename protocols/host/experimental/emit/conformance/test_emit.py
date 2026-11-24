# Copyright 2026 Marimo. All rights reserved.
"""Custom event publication through the public HTTP and SSE interface."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from contract import problem, validate
from test_host import notebook_path, require

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


async def test_emit_broadcasts_once_per_request(host, scratch) -> None:
    require(scratch, "notebook.emit")
    path = notebook_path(scratch)
    body = json.loads((FIXTURES / "emit-request.json").read_text())
    key, barrier_key = uuid4().hex, uuid4().hex
    barrier = {"type": "example.barrier", "data": None}

    async with (
        host.watch(path + "/events", params={"kinds": "custom"}) as first,
        host.watch(path + "/events", params={"kinds": "custom"}) as second,
    ):
        await first.ready()
        await second.ready()
        for _ in range(2):
            response = await host.request(
                "POST", path + "/emit", key=key, json=body
            )
            assert (response.status_code, response.content) == (204, b"")
        response = await host.request(
            "POST", path + "/emit", key=barrier_key, json=barrier
        )
        assert (response.status_code, response.content) == (204, b"")

        received = []
        for watch in (first, second):
            frames = await watch.until(
                lambda frame: (
                    frame.event == "custom"
                    and frame.message().get("request_id") == barrier_key
                )
            )
            messages = []
            for frame in frames:
                if frame.event != "custom":
                    continue
                message = frame.message()
                validate("CustomMessage", message)
                assert frame.id
                messages.append(message)
            assert [message["custom"] for message in messages] == [
                body,
                barrier,
            ]
            assert [message["request_id"] for message in messages] == [
                key,
                barrier_key,
            ]
            received.append(messages)
        assert received[0] == received[1]


@pytest.mark.parametrize(
    ("key", "body"),
    [
        ("", {"type": "example.message", "data": None}),
        (None, {"type": "", "data": None}),
    ],
)
async def test_emit_rejects_invalid_requests(host, scratch, key, body) -> None:
    require(scratch, "notebook.emit")
    problem(
        await host.request(
            "POST", notebook_path(scratch) + "/emit", key=key, json=body
        ),
        400,
        "invalid-request",
    )
