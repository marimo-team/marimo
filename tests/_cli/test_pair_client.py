# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import io
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from marimo._cli.pair import client
from marimo._cli.pair.client import PairError, SSEEvent

if TYPE_CHECKING:
    from collections.abc import Iterator


FIXTURES = Path(__file__).parent / "fixtures" / "pair"


class RecordingStream(io.StringIO):
    def __init__(self, name: str, records: list[tuple[str, str]]) -> None:
        super().__init__()
        self.name = name
        self.records = records

    def write(self, value: str) -> int:
        self.records.append((self.name, value))
        return super().write(value)

    def flush(self) -> None:
        self.records.append((self.name, "flush"))
        super().flush()


class RaisingResponse:
    def __init__(self, lines: list[bytes], error: BaseException) -> None:
        self.lines = lines
        self.error = error
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield from self.lines
        raise self.error

    def close(self) -> None:
        self.closed = True


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _patch_response(
    monkeypatch: pytest.MonkeyPatch, response: Any
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_open_response(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return response

    monkeypatch.setattr(client, "open_response", fake_open_response)
    return calls


def test_load_token_without_file_or_environment() -> None:
    assert client.load_token(None, {}) is None


def test_load_token_from_environment() -> None:
    assert client.load_token(None, {"MARIMO_TOKEN": "environment"}) == (
        "environment"
    )


def test_load_token_file_wins_and_trims_newline(tmp_path: Path) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text(" file token \r\n", encoding="utf-8")

    assert (
        client.load_token(token_file, {"MARIMO_TOKEN": "environment"})
        == " file token "
    )


def test_load_token_rejects_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(PairError, match="Could not read the token file"):
        client.load_token(tmp_path, {"MARIMO_TOKEN": "environment"})


def test_load_token_rejects_empty_file(tmp_path: Path) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text("\n", encoding="utf-8")

    with pytest.raises(PairError, match="The token file is empty"):
        client.load_token(token_file, {})


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        (
            "execute-success.sse",
            [
                SSEEvent("stdout", '{"data":"hello\\n"}'),
                SSEEvent(
                    "done",
                    '{"success":true,"output":{"mimetype":"text/plain","data":"2"}}',
                ),
            ],
        ),
        (
            "execute-failure.sse",
            [
                SSEEvent("stderr", '{"data":"ValueError: boom\\n"}'),
                SSEEvent(
                    "done",
                    '{"success":false,"output":{"mimetype":"text/plain","data":""}}',
                ),
            ],
        ),
    ],
)
def test_iter_sse_fixtures(fixture: str, expected: list[SSEEvent]) -> None:
    assert list(client.iter_sse(io.BytesIO(_fixture(fixture)))) == expected


def test_iter_sse_handles_crlf_comments_and_multiline_data() -> None:
    lines = [
        b": keep-alive\r\n",
        b"event: custom\r\n",
        b"data: first\r\n",
        b"data: second\r\n",
        b"\r\n",
    ]

    assert list(client.iter_sse(lines)) == [
        SSEEvent("custom", "first\nsecond")
    ]


def test_iter_sse_dispatches_unterminated_final_record() -> None:
    assert list(client.iter_sse([b"data: final"])) == [
        SSEEvent("message", "final")
    ]


def test_execute_sends_request_and_streams_in_event_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(
        b"event: stdout\n"
        b'data: {"data":"out"}\n\n'
        b"event: stderr\n"
        b'data: {"data":"err"}\n\n'
        b"event: done\n"
        b'data: {"success":true,"output":{"data":"result"}}\n\n'
    )
    calls = _patch_response(monkeypatch, response)
    records: list[tuple[str, str]] = []
    stdout = RecordingStream("stdout", records)
    stderr = RecordingStream("stderr", records)

    result = client.execute(
        url="https://example.com/base/?access_token=query-token",
        session_id="session-1",
        token="secret-token",
        code="print(1)",
        stdout=stdout,
        stderr=stderr,
        stream=True,
    )

    assert result == client.ExecutionResult(success=True, output="result")
    assert records == [
        ("stdout", "out"),
        ("stdout", "flush"),
        ("stderr", "err"),
        ("stderr", "flush"),
        ("stdout", "result\n"),
    ]
    assert calls == [
        {
            "method": "POST",
            "url": "https://example.com/base/api/kernel/execute?access_token=query-token",
            "headers": {
                "Content-Type": "application/json",
                "Marimo-Session-Id": "session-1",
                "Authorization": "Bearer secret-token",
            },
            "body": json.dumps({"code": "print(1)"}).encode(),
        }
    ]
    assert "secret-token" not in calls[0]["url"]
    assert b"secret-token" not in calls[0]["body"]
    assert response.closed


def test_execute_omits_authorization_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(_fixture("execute-success.sse"))
    calls = _patch_response(monkeypatch, response)

    client.execute(
        url="http://localhost:2718",
        session_id="session-1",
        token=None,
        code="1 + 1",
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        stream=True,
    )

    assert len(calls) == 1
    assert "Authorization" not in calls[0]["headers"]


def test_open_response_rejects_invalid_port_without_exposing_url() -> None:
    with pytest.raises(PairError) as exc_info:
        client.open_response(
            method="GET",
            url="http://localhost:not-a-port?access_token=secret",
            headers={},
            body=None,
        )

    assert str(exc_info.value) == "Could not connect to the server."
    assert "secret" not in str(exc_info.value)


def test_execute_buffers_output_until_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    class InspectingResponse(io.BytesIO):
        def readline(self, size: int = -1) -> bytes:
            line = super().readline(size)
            if line == b"event: done\n":
                assert stdout.getvalue() == ""
                assert stderr.getvalue() == ""
            return line

    response = InspectingResponse(_fixture("execute-success.sse"))
    calls = _patch_response(monkeypatch, response)

    result = client.execute(
        url="http://localhost:2718",
        session_id="session-1",
        token=None,
        code="1 + 1",
        stdout=stdout,
        stderr=stderr,
        stream=False,
    )

    assert result.success
    assert stdout.getvalue() == "hello\n2\n"
    assert stderr.getvalue() == ""
    assert len(calls) == 1


def test_execute_returns_unsuccessful_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(_fixture("execute-failure.sse"))
    calls = _patch_response(monkeypatch, response)
    stderr = io.StringIO()

    result = client.execute(
        url="http://localhost:2718",
        session_id="session-1",
        token=None,
        code="raise ValueError",
        stdout=io.StringIO(),
        stderr=stderr,
        stream=False,
    )

    assert result == client.ExecutionResult(success=False, output="")
    assert stderr.getvalue() == "ValueError: boom\n"
    assert len(calls) == 1


def test_execute_rejects_missing_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(b'event: stdout\ndata: {"data":"partial"}\n\n')
    calls = _patch_response(monkeypatch, response)

    with pytest.raises(PairError, match="ended before completion"):
        client.execute(
            url="http://localhost:2718",
            session_id="session-1",
            token=None,
            code="print(1)",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            stream=True,
        )

    assert len(calls) == 1


def test_execute_keeps_buffered_output_after_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = RaisingResponse(
        [b"event: stdout\n", b'data: {"data":"partial"}\n', b"\n"],
        OSError("connection lost"),
    )
    calls = _patch_response(monkeypatch, response)
    stdout = io.StringIO()

    with pytest.raises(PairError, match="ended before completion"):
        client.execute(
            url="http://localhost:2718",
            session_id="session-1",
            token=None,
            code="print(1)",
            stdout=stdout,
            stderr=io.StringIO(),
            stream=False,
        )

    assert stdout.getvalue() == "partial"
    assert response.closed
    assert len(calls) == 1


def test_execute_rejects_truncated_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = RaisingResponse([], http.client.IncompleteRead(b"partial"))
    _patch_response(monkeypatch, response)

    with pytest.raises(PairError, match="ended before completion"):
        client.execute(
            url="http://localhost:2718",
            session_id="session-1",
            token=None,
            code="print(1)",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            stream=True,
        )

    assert response.closed


def test_execute_closes_response_after_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = RaisingResponse([], KeyboardInterrupt())
    calls = _patch_response(monkeypatch, response)

    with pytest.raises(KeyboardInterrupt):
        client.execute(
            url="http://localhost:2718",
            session_id="session-1",
            token=None,
            code="while True: pass",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            stream=True,
        )

    assert response.closed
    assert len(calls) == 1


def test_list_sessions_sends_request_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(
        json.dumps(
            {
                "session-1": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                },
                "session-2": {"filename": None, "path": None},
            }
        ).encode()
    )
    calls = _patch_response(monkeypatch, response)

    sessions = client.list_sessions(
        url="https://example.com/base/", token="secret-token"
    )

    assert sessions == {
        "session-1": {
            "filename": "analysis.py",
            "path": "/work/analysis.py",
        },
        "session-2": {"filename": None, "path": None},
    }
    assert calls == [
        {
            "method": "GET",
            "url": "https://example.com/base/api/sessions",
            "headers": {"Authorization": "Bearer secret-token"},
            "body": None,
        }
    ]
    assert response.closed


def test_list_sessions_omits_authorization_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(b"{}")
    calls = _patch_response(monkeypatch, response)

    assert client.list_sessions(url="http://localhost:2718", token=None) == {}

    assert calls[0]["headers"] == {}
    assert response.closed


def test_list_sessions_rejects_non_object_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(b"[]")
    _patch_response(monkeypatch, response)

    with pytest.raises(
        PairError,
        match=(
            r"Unexpected response from "
            r"http://localhost:2718/api/sessions\."
        ),
    ):
        client.list_sessions(url="http://localhost:2718/", token=None)

    assert response.closed


def test_registry_urls_skips_invalid_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "valid.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": 2718,
                "base_url": "",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "stale.json").write_text(
        json.dumps(
            {
                "pid": 2**31 - 1,
                "host": "127.0.0.1",
                "port": 2720,
                "base_url": "",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "invalid.json").write_text("{", encoding="utf-8")
    (tmp_path / "missing.json").write_text(
        json.dumps({"port": 2719}), encoding="utf-8"
    )
    monkeypatch.setattr(client, "_servers_dir", lambda: tmp_path)

    assert client.registry_urls() == ["http://localhost:2718"]


def test_registry_urls_formats_prefix_and_standard_ports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entries = [
        ("http.json", "0.0.0.0", 80, "/prefix"),
        ("https.json", "::", 443, ""),
    ]
    for filename, host, port, base_url in entries:
        (tmp_path / filename).write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "host": host,
                    "port": port,
                    "base_url": base_url,
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(client, "_servers_dir", lambda: tmp_path)

    assert client.registry_urls() == [
        "http://localhost/prefix",
        "https://localhost",
    ]
