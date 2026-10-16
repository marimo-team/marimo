# Copyright 2026 Marimo. All rights reserved.
"""HTTP media types are case insensitive and may include parameters."""

from __future__ import annotations

import json

import httpx
import pytest
from contract import ROOT, Frame, Host, accepted, problem


@pytest.mark.parametrize(
    "content_type",
    [
        "text/event-stream",
        "Text/Event-Stream",
        " Text/Event-Stream ; charset=utf-8",
    ],
)
async def test_watch_accepts_media_type_variations(content_type):
    def respond(_request):
        return httpx.Response(
            200,
            headers={"Content-Type": content_type},
            content="event: ready\ndata: {}\n\n",
        )

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1/", transport=httpx.MockTransport(respond)
    ) as client:
        assert await Host(client, timeout=1).snapshot() == [
            Frame(event="ready", data="{}")
        ]


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "Application/JSON",
        " Application/JSON ; charset=utf-8",
    ],
)
def test_accepted_accepts_media_type_variations(content_type):
    value = json.loads((ROOT / "fixtures" / "cell.json").read_text())
    response = httpx.Response(
        200, headers={"Content-Type": content_type}, json=value
    )
    assert accepted(response, 200, "Cell") == value


@pytest.mark.parametrize(
    "content_type",
    [
        "application/problem+json",
        "Application/Problem+JSON",
        " Application/Problem+JSON ; charset=utf-8",
    ],
)
def test_problem_accepts_media_type_variations(content_type):
    value = json.loads(
        (ROOT / "fixtures" / "problems" / "not-found.json").read_text()
    )
    response = httpx.Response(
        404, headers={"Content-Type": content_type}, json=value
    )
    assert problem(response, 404, "not-found") == value
