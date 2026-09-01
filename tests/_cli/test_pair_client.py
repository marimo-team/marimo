# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.client import HTTPMessage
from typing import TYPE_CHECKING
from urllib.request import Request

import pytest

from marimo._cli.pair.client import (
    PairClient,
    PairError,
    PairServer,
    SameOriginRedirectHandler,
    SessionInfo,
    load_token,
    resolve_server,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


@dataclass
class MemoryResponse:
    body: bytes
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    closed: bool = False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def close(self) -> None:
        self.closed = True


@dataclass
class MemoryTransport:
    responses: dict[str, MemoryResponse]
    request: Request | None = None

    def open(
        self,
        request: Request,
        *,
        timeout: float | None,
    ) -> MemoryResponse:
        assert timeout == 5.0
        self.request = request
        return self.responses[request.full_url]


def _server(url: str | None = "https://example.com/base") -> PairServer:
    return PairServer(
        server_id="server",
        origin="local",
        url=url,
        started_at="2026-08-31T00:00:00+00:00",
        version="0.24.0",
    )


def _client_with_sessions(payload: object) -> PairClient:
    response = MemoryResponse(json.dumps(payload).encode())
    transport = MemoryTransport(
        {"https://example.com/base/api/sessions": response}
    )
    return PairClient(_server(), token=None, transport=transport)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/base",
        "http://localhost:2718/base",
        "http://127.0.0.2:2718",
        "http://[::1]:2718/base",
    ],
)
def test_resolve_server_accepts_secure_or_loopback_urls(url: str) -> None:
    result = resolve_server(
        url=url,
        discovered=(),
        allow_insecure_http=False,
    )

    assert result.origin == "direct"
    assert result.url == url


def test_resolve_server_url_requires_override_for_remote_http() -> None:
    with pytest.raises(PairError, match="plain HTTP") as error:
        resolve_server(
            url="http://example.com/base",
            discovered=(),
            allow_insecure_http=False,
        )
    assert error.value.kind == "insecure_http"

    result = resolve_server(
        url="http://example.com/base",
        discovered=(),
        allow_insecure_http=True,
    )
    assert result.url == "http://example.com/base"


@pytest.mark.parametrize(
    "url",
    [
        "example.com/base",
        "ftp://example.com/base",
        "https://user:password@example.com/base",
        "https://example.com/base?auth=secret",
        "https://example.com/base?TOKEN=secret",
        "https://example.com/base?access_token=secret",
    ],
)
def test_resolve_server_rejects_invalid_or_credential_urls(url: str) -> None:
    with pytest.raises(PairError) as error:
        resolve_server(
            url=url,
            discovered=(),
            allow_insecure_http=False,
        )

    assert error.value.kind == "invalid_target"
    assert "secret" not in str(error.value)
    assert "password" not in str(error.value)


def test_resolve_server_url_or_discovery_selects_one_server() -> None:
    reachable = _server("http://127.0.0.1:2718")
    unreachable = _server(None)

    assert (
        resolve_server(
            url=None,
            discovered=(unreachable, reachable),
            allow_insecure_http=False,
        )
        == reachable
    )

    with pytest.raises(PairError) as none_error:
        resolve_server(
            url=None,
            discovered=(unreachable,),
            allow_insecure_http=False,
        )
    assert none_error.value.kind == "no_server"

    with pytest.raises(PairError) as many_error:
        resolve_server(
            url=None,
            discovered=(reachable, _server("http://127.0.0.1:2719")),
            allow_insecure_http=False,
        )
    assert many_error.value.kind == "ambiguous_server"


def test_load_token_uses_environment_when_no_file_is_given() -> None:
    assert (
        load_token(
            token_file=None,
            environ={"MARIMO_TOKEN": "environment-token"},
        )
        == "environment-token"
    )
    assert load_token(token_file=None, environ={}) is None


def test_load_token_file_overrides_environment_and_only_trims_newlines(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text(" file-token \r\n", encoding="utf-8")

    assert (
        load_token(
            token_file=token_file,
            environ={"MARIMO_TOKEN": "environment-token"},
        )
        == " file-token "
    )


def test_load_token_rejects_an_empty_file(tmp_path: Path) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text("\r\n", encoding="utf-8")

    with pytest.raises(PairError) as error:
        load_token(token_file=token_file, environ={})

    assert error.value.kind == "invalid_target"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("https://example.com/a", "https://example.com:443/b"),
        ("http://example.com:80/a", "http://example.com/b"),
    ],
)
def test_authenticated_redirect_accepts_the_same_origin(
    source: str,
    target: str,
) -> None:
    request = Request(source, headers={"Authorization": "Bearer token"})
    redirected = SameOriginRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        HTTPMessage(),
        target,
    )

    assert redirected is not None
    assert redirected.full_url == target
    assert redirected.get_header("Authorization") == "Bearer token"


@pytest.mark.parametrize(
    "target",
    [
        "http://example.com/b",
        "https://other.example.com/b",
        "https://example.com:444/b",
    ],
)
def test_authenticated_redirect_rejects_a_different_origin(
    target: str,
) -> None:
    request = Request(
        "https://example.com/a",
        headers={"Authorization": "Bearer token"},
    )

    with pytest.raises(PairError) as error:
        SameOriginRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            HTTPMessage(),
            target,
        )

    assert error.value.kind == "invalid_target"
    assert "token" not in str(error.value)


def test_pair_client_reads_version_with_authentication() -> None:
    response = MemoryResponse(b"0.24.0")
    transport = MemoryTransport(
        {"https://example.com/base/api/version": response}
    )
    client = PairClient(_server(), token="secret-token", transport=transport)

    assert client.version() == "0.24.0"
    assert response.closed
    assert transport.request is not None
    assert transport.request.get_header("Authorization") == (
        "Bearer secret-token"
    )
    assert "secret-token" not in transport.request.full_url
    assert "secret-token" not in repr(client)


def test_pair_client_maps_version_authentication_failure() -> None:
    transport = MemoryTransport(
        {
            "https://example.com/base/api/version": MemoryResponse(
                b'{"detail":"unauthorized"}', status=401
            )
        }
    )

    with pytest.raises(PairError) as error:
        PairClient(_server(), token="secret", transport=transport).version()

    assert error.value.kind == "authentication_failed"
    assert "secret" not in str(error.value)


def test_pair_client_reads_typed_sessions() -> None:
    client = _client_with_sessions(
        {
            "s_one": {"filename": "one.py", "path": "/work/one.py"},
            "s_two": {"filename": None, "path": None},
        }
    )

    assert client.sessions() == (
        SessionInfo("s_one", "one.py", "/work/one.py"),
        SessionInfo("s_two", None, None),
    )


def test_resolve_session_handles_zero_one_and_many_sessions() -> None:
    with pytest.raises(PairError) as none_error:
        _client_with_sessions({}).resolve_session(
            session_id=None,
            notebook=None,
        )
    assert none_error.value.kind == "no_session"

    only = SessionInfo("s_one", "one.py", "/work/one.py")
    assert (
        _client_with_sessions(
            {"s_one": {"filename": "one.py", "path": "/work/one.py"}}
        ).resolve_session(session_id=None, notebook=None)
        == only
    )

    with pytest.raises(PairError) as many_error:
        _client_with_sessions(
            {
                "s_one": {"filename": "one.py", "path": "/work/one.py"},
                "s_two": {"filename": "two.py", "path": "/work/two.py"},
            }
        ).resolve_session(session_id=None, notebook=None)
    assert many_error.value.kind == "ambiguous_session"


def test_resolve_session_matches_id_filename_or_opaque_path() -> None:
    payload = {
        "s_one": {
            "filename": "notebooks/one.py",
            "path": "/work/notebooks/one.py",
        },
        "s_two": {
            "filename": r"C:\Users\Ada\notebook.py",
            "path": r"C:\Users\Ada\notebook.py",
        },
    }

    assert (
        _client_with_sessions(payload)
        .resolve_session(
            session_id="s_one",
            notebook=None,
        )
        .session_id
        == "s_one"
    )
    assert (
        _client_with_sessions(payload)
        .resolve_session(
            session_id=None,
            notebook="notebooks/one.py",
        )
        .session_id
        == "s_one"
    )
    assert (
        _client_with_sessions(payload)
        .resolve_session(
            session_id=None,
            notebook=r"C:\Users\Ada\notebook.py",
        )
        .session_id
        == "s_two"
    )


def test_resolve_session_rejects_missing_ambiguous_or_conflicting_selectors() -> (
    None
):
    payload = {
        "s_one": {"filename": "same.py", "path": "/one/same.py"},
        "s_two": {"filename": "same.py", "path": "/two/same.py"},
    }

    with pytest.raises(PairError) as missing_error:
        _client_with_sessions(payload).resolve_session(
            session_id="missing",
            notebook=None,
        )
    assert missing_error.value.kind == "session_not_found"

    with pytest.raises(PairError) as ambiguous_error:
        _client_with_sessions(payload).resolve_session(
            session_id=None,
            notebook="same.py",
        )
    assert ambiguous_error.value.kind == "ambiguous_session"

    with pytest.raises(PairError) as conflict_error:
        _client_with_sessions(payload).resolve_session(
            session_id="s_one",
            notebook="same.py",
        )
    assert conflict_error.value.kind == "invalid_target"
