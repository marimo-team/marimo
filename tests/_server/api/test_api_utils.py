# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import msgspec
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from marimo._server.api.utils import (
    get_code_mode_credentials,
    parse_multipart_request,
)

if TYPE_CHECKING:
    from starlette.types import Scope

    from marimo._server.api.deps import AppStateBase


class _SampleForm(msgspec.Struct):
    name: str
    count: int


def _build_app(captured: dict[str, object]) -> TestClient:
    async def endpoint(request: Request) -> JSONResponse:
        async with parse_multipart_request(request, _SampleForm) as parsed:
            captured["body"] = parsed.body
            captured["files"] = dict(parsed.files)
            upload = parsed.files.get("upload")
            if upload is not None:
                captured["upload_bytes"] = await upload.read()
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/test", endpoint, methods=["POST"])])
    return TestClient(app)


def test_parse_multipart_request_strings_and_file_upload() -> None:
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
    files = captured["files"]
    assert isinstance(files, dict)
    assert set(files.keys()) == {"upload"}
    assert captured["upload_bytes"] == b"\x00\x01\x02\xff"


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


def _fake_app_state(
    *,
    host: str = "localhost",
    port: int = 2718,
    base_url: str = "",
    auth_token: str = "tok",
) -> AppStateBase:
    """Minimal duck-typed stand-in for AppStateBase exposing only the
    attributes that get_code_mode_credentials reads."""
    state = SimpleNamespace(
        host=host,
        port=port,
        base_url=base_url,
        session_manager=SimpleNamespace(auth_token=auth_token),
    )
    return cast("AppStateBase", cast(object, state))


def _fake_request(
    *,
    scheme: str = "http",
    host_header: str = "evil.example.com:80",
) -> Request:
    """Build a Starlette Request with a chosen scheme and Host header
    without spinning up an app."""
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "scheme": scheme,
        "server": ("localhost", 2718),
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", host_header.encode())],
    }
    return Request(scope)


def test_get_code_mode_credentials_uses_configured_host_not_request_host_header() -> (
    None
):
    """Regression guard for the security property documented on
    get_code_mode_credentials: the server URL must come from the server's
    configured host/port, not from the (spoofable) Host header."""
    url, token = get_code_mode_credentials(
        _fake_app_state(host="127.0.0.1", port=2718, auth_token="secret"),
        _fake_request(host_header="evil.example.com:80"),
    )
    assert url == "http://127.0.0.1:2718"
    assert token == "secret"


def test_get_code_mode_credentials_strips_trailing_slash_from_base_url() -> (
    None
):
    url, _ = get_code_mode_credentials(
        _fake_app_state(base_url="/notebook/"),
        _fake_request(),
    )
    assert url == "http://localhost:2718/notebook"


def test_get_code_mode_credentials_includes_non_empty_base_url() -> None:
    url, _ = get_code_mode_credentials(
        _fake_app_state(base_url="/notebook"),
        _fake_request(),
    )
    assert url == "http://localhost:2718/notebook"


def test_get_code_mode_credentials_empty_base_url() -> None:
    url, _ = get_code_mode_credentials(
        _fake_app_state(base_url=""),
        _fake_request(),
    )
    assert url == "http://localhost:2718"


def test_get_code_mode_credentials_propagates_https_scheme() -> None:
    url, _ = get_code_mode_credentials(
        _fake_app_state(),
        _fake_request(scheme="https"),
    )
    assert url == "https://localhost:2718"
