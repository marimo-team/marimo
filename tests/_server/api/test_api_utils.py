# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from marimo._server.api.utils import parse_multipart_request

if TYPE_CHECKING:
    from starlette.requests import Request


class _SampleForm(msgspec.Struct):
    name: str
    count: int


def _build_app(captured: dict[str, object]) -> TestClient:
    async def endpoint(request: Request) -> JSONResponse:
        parsed = await parse_multipart_request(request, _SampleForm)
        captured["body"] = parsed.body
        captured["files"] = parsed.files
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/test", endpoint, methods=["POST"])])
    return TestClient(app)


def test_parse_multipart_request_strings_and_file_bytes() -> None:
    captured: dict[str, object] = {}
    client = _build_app(captured)
    response = client.post(
        "/test",
        data={"name": "marimo", "count": "42"},
        files={"upload": ("hello.bin", b"\x00\x01\x02\xff")},
    )
    assert response.status_code == 200
    body = captured["body"]
    assert isinstance(body, _SampleForm)
    assert body.name == "marimo"
    assert body.count == 42
    assert captured["files"] == {"upload": b"\x00\x01\x02\xff"}


def test_parse_multipart_request_omitted_file_yields_empty_dict() -> None:
    captured: dict[str, object] = {}
    client = _build_app(captured)
    response = client.post(
        "/test",
        data={"name": "marimo", "count": "1"},
    )
    assert response.status_code == 200
    assert captured["files"] == {}


def test_parse_multipart_request_raises_on_missing_field() -> None:
    captured: dict[str, object] = {}
    client = _build_app(captured)
    with pytest.raises(msgspec.ValidationError):
        client.post("/test", data={"name": "marimo"})
