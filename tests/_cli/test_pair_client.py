# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
import subprocess
from dataclasses import dataclass, field
from http.client import HTTPMessage
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.request import Request

import pytest

import marimo._cli.pair.client as pair_client
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


@dataclass
class MemoryResponse:
    body: bytes
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    read_error: BaseException | None = None
    closed: bool = False

    def read(self, size: int = -1) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        return self.body if size < 0 else self.body[:size]

    def close(self) -> None:
        self.closed = True


@dataclass
class MemoryTransport:
    responses: dict[str, MemoryResponse]
    request: Request | None = None
    open_count: int = 0

    def open(
        self,
        request: Request,
        *,
        timeout: float | None,
    ) -> MemoryResponse:
        assert timeout == 5.0
        self.open_count += 1
        self.request = request
        return self.responses[request.full_url]


@dataclass
class RecordingWriter:
    name: str
    records: list[tuple[str, str]]
    error: BaseException | None = None

    def write(self, value: str) -> int:
        if self.error is not None:
            raise self.error
        self.records.append((self.name, value))
        return len(value)


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


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "execute-success.sse",
            (
                ("stdout", '{"data":"hello\\n"}'),
                (
                    "done",
                    '{"success":true,"output":{"mimetype":"text/plain","data":"2"}}',
                ),
            ),
        ),
        (
            "execute-failure.sse",
            (
                ("stderr", '{"data":"ValueError: boom\\n"}'),
                (
                    "done",
                    '{"success":false,"output":{"mimetype":"text/plain","data":""}}',
                ),
            ),
        ),
    ],
)
def test_parse_sse_matches_frozen_responses(
    filename: str,
    expected: tuple[tuple[str, str], ...],
) -> None:
    fixture = (
        Path(__file__).parent / "fixtures" / "marimo_pair_v0_0_19" / filename
    )

    events = pair_client.parse_sse(fixture.read_bytes())

    assert tuple((event.name, event.data) for event in events) == expected


def test_parse_sse_handles_crlf_comments_multiline_utf8_and_final_record() -> (
    None
):
    body = (
        ": keepalive\r\n"
        "event: stdout\r\n"
        "data: café\r\n"
        "data: second line\r\n"
        "\r\n"
        "event: done\r\n"
        'data: {"success":true,"output":{"data":""}}'
    ).encode()

    events = pair_client.parse_sse(body)

    assert tuple((event.name, event.data) for event in events) == (
        ("stdout", "café\nsecond line"),
        ("done", '{"success":true,"output":{"data":""}}'),
    )


def test_parse_sse_rejects_invalid_utf8() -> None:
    with pytest.raises(PairError) as error:
        pair_client.parse_sse(b"event: stdout\ndata: \xff\n\n")

    assert error.value.kind == "invalid_response"


def _execution_client(
    body: bytes,
    *,
    read_error: BaseException | None = None,
) -> tuple[PairClient, MemoryResponse, MemoryTransport]:
    response = MemoryResponse(body, read_error=read_error)
    transport = MemoryTransport(
        {"https://example.com/base/api/kernel/execute": response}
    )
    return (
        PairClient(_server(), token="secret-token", transport=transport),
        response,
        transport,
    )


def test_execute_routes_output_and_returns_the_terminal_result() -> None:
    body = (
        b'event: stdout\ndata: {"data":"hello\\n"}\n\n'
        b'event: stderr\ndata: {"data":"warning\\n"}\n\n'
        b"event: done\n"
        b'data: {"success":true,"output":{"mimetype":"text/plain","data":"2"}}\n\n'
    )
    client, response, transport = _execution_client(body)
    records: list[tuple[str, str]] = []

    result = client.execute(
        "session-one",
        "print('hello')",
        stdout=RecordingWriter("stdout", records),
        stderr=RecordingWriter("stderr", records),
    )

    assert result.success is True
    assert result.output == "2"
    assert records == [
        ("stdout", "hello\n"),
        ("stderr", "warning\n"),
        ("stdout", "2\n"),
    ]
    assert response.closed
    assert transport.open_count == 1
    assert transport.request is not None
    assert transport.request.get_method() == "POST"
    assert transport.request.data == b'{"code": "print(\'hello\')"}'
    assert transport.request.get_header("Content-type") == "application/json"
    assert transport.request.get_header("Marimo-session-id") == "session-one"
    assert transport.request.get_header("Authorization") == (
        "Bearer secret-token"
    )


def test_execute_returns_kernel_failure_after_routing_stderr() -> None:
    body = (
        b'event: stderr\ndata: {"data":"ValueError: boom\\n"}\n\n'
        b"event: done\n"
        b'data: {"success":false,"output":{"mimetype":"text/plain","data":""}}\n\n'
    )
    client, response, _transport = _execution_client(body)
    stdout = io.StringIO()
    stderr = io.StringIO()

    result = client.execute(
        "session-one",
        "raise ValueError",
        stdout=stdout,
        stderr=stderr,
    )

    assert result.success is False
    assert result.output == ""
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "ValueError: boom\n"
    assert response.closed


@pytest.mark.parametrize(
    ("body", "expected_kind"),
    [
        (
            b'event: stdout\ndata: {"data":"partial"}\n\n',
            "incomplete_response",
        ),
        (b"event: done\ndata: not-json\n\n", "invalid_response"),
    ],
)
def test_execute_rejects_incomplete_or_malformed_sse(
    body: bytes,
    expected_kind: str,
) -> None:
    client, response, _transport = _execution_client(body)

    with pytest.raises(PairError) as error:
        client.execute(
            "session-one",
            "1 + 1",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert error.value.kind == expected_kind
    assert response.closed


def test_execute_cancel_closes_the_response() -> None:
    client, response, transport = _execution_client(
        b"",
        read_error=KeyboardInterrupt(),
    )

    with pytest.raises(KeyboardInterrupt):
        client.execute(
            "session-one",
            "while True: pass",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert response.closed
    assert transport.open_count == 1


def test_execute_broken_output_pipe_closes_the_response() -> None:
    body = (
        b'event: stdout\ndata: {"data":"hello"}\n\n'
        b'event: done\ndata: {"success":true,"output":{"data":""}}\n\n'
    )
    client, response, _transport = _execution_client(body)

    with pytest.raises(BrokenPipeError):
        client.execute(
            "session-one",
            "print('hello')",
            stdout=RecordingWriter(
                "stdout",
                [],
                error=BrokenPipeError(),
            ),
            stderr=io.StringIO(),
        )

    assert response.closed


def test_execute_does_not_retry_after_connection_loss() -> None:
    client, response, transport = _execution_client(
        b"",
        read_error=ConnectionResetError(),
    )

    with pytest.raises(PairError) as error:
        client.execute(
            "session-one",
            "mutate_state()",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert error.value.kind == "indeterminate_result"
    assert response.closed
    assert transport.open_count == 1


@pytest.mark.parametrize("server_version", ["0.23.9", "0.24.0"])
def test_version_selection_keeps_compatible_client(
    server_version: str,
) -> None:
    with (
        patch.object(pair_client, "__version__", "0.24.0", create=True),
        patch.object(pair_client, "subprocess", subprocess, create=True),
        patch.object(subprocess, "run") as run,
        patch("marimo._cli.pair.client.os.execvpe") as execvpe,
    ):
        pair_client.ensure_client_version(
            server_version,
            arguments=("--url", "https://example.com"),
            environ={},
        )

    run.assert_not_called()
    execvpe.assert_not_called()


def test_version_handoff_uses_an_exact_wheel_and_sanitized_environment() -> (
    None
):
    environment = {
        "HOME": "/home/ada",
        "MARIMO_TOKEN": "secret-token",
        "UV_INDEX": "https://untrusted.example/simple",
        "UV_INDEX_URL": "https://untrusted.example/simple",
        "UV_DEFAULT_INDEX": "https://untrusted.example/simple",
        "UV_EXTRA_INDEX_URL": "https://untrusted.example/extra",
        "UV_FIND_LINKS": "/tmp/wheels",
        "UV_CONFIG_FILE": "/tmp/uv.toml",
        "UV_INSECURE_HOST": "untrusted.example",
        "PIP_INDEX_URL": "https://untrusted.example/simple",
        "PIP_TRUSTED_HOST": "untrusted.example",
    }
    arguments = (
        "--url",
        "https://example.com/base",
        "--session",
        "session-one",
        "-c",
        "1 + 1",
    )
    prefix = [
        "uvx",
        "--no-config",
        "--no-env-file",
        "--no-sources",
        "--default-index",
        "https://pypi.org/simple",
        "--from",
        "marimo==0.25.0",
    ]

    with (
        patch.object(pair_client, "__version__", "0.24.0", create=True),
        patch.object(pair_client, "subprocess", subprocess, create=True),
        patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(prefix, 0),
        ) as run,
        patch("marimo._cli.pair.client.os.execvpe") as execvpe,
    ):
        pair_client.ensure_client_version(
            "0.25.0",
            arguments=arguments,
            environ=environment,
        )

    expected_environment = {
        "HOME": "/home/ada",
        "MARIMO_TOKEN": "secret-token",
        pair_client.PAIR_HANDOFF_ENV: "0.25.0",
    }
    run.assert_called_once_with(
        [*prefix, "marimo", "--version"],
        check=False,
        env=expected_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    execvpe.assert_called_once_with(
        "uvx",
        [*prefix, "marimo", "pair", "execute", *arguments],
        expected_environment,
    )
    assert "secret-token" not in execvpe.call_args.args[1]


def test_version_handoff_reports_an_unavailable_wheel() -> None:
    with (
        patch.object(pair_client, "__version__", "0.24.0", create=True),
        patch.object(pair_client, "subprocess", subprocess, create=True),
        patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 1),
        ),
        patch("marimo._cli.pair.client.os.execvpe") as execvpe,
        pytest.raises(PairError) as error,
    ):
        pair_client.ensure_client_version(
            "0.25.0",
            arguments=(),
            environ={},
        )

    assert error.value.kind == "version_unavailable"
    assert str(error.value) == (
        "marimo 0.25.0 is unavailable from PyPI. Run the marimo executable "
        "from that server's source checkout."
    )
    execvpe.assert_not_called()


def test_version_handoff_rejects_a_second_mismatch() -> None:
    with (
        patch.object(pair_client, "__version__", "0.24.0", create=True),
        patch.object(pair_client, "subprocess", subprocess, create=True),
        patch.object(subprocess, "run") as run,
        patch("marimo._cli.pair.client.os.execvpe") as execvpe,
        pytest.raises(PairError) as error,
    ):
        pair_client.ensure_client_version(
            "0.25.0",
            arguments=(),
            environ={pair_client.PAIR_HANDOFF_ENV: "0.25.0"},
        )

    assert error.value.kind == "version_unavailable"
    run.assert_not_called()
    execvpe.assert_not_called()
