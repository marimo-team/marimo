# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import io
import json
import os
import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from marimo._cli.pair import client
from marimo._cli.pair.client import (
    AmbiguousNotebookError,
    NoNotebookError,
    NotebookUnsupportedError,
    PairError,
    PairInputError,
    SSEEvent,
    StaleNotebookError,
)

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
        return client.EventStream(response, Mock())

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
    with pytest.raises(PairInputError, match="Could not read the token file"):
        client.load_token(tmp_path, {"MARIMO_TOKEN": "environment"})


def test_load_token_rejects_empty_file(tmp_path: Path) -> None:
    token_file = tmp_path / "token.txt"
    token_file.write_text("\n", encoding="utf-8")

    with pytest.raises(PairInputError, match="The token file is empty"):
        client.load_token(token_file, {})


def test_display_url_removes_credentials_query_and_fragment() -> None:
    assert (
        client.display_url(
            "https://user:password@example.com/base?access_token=secret#part"
        )
        == "https://example.com/base"
    )
    assert client.display_url("http://[::1") == "<invalid URL>"


def test_iter_sse_reads_cursor_multiline_and_ignores_invalid_ids() -> None:
    assert list(
        client.iter_sse(
            [
                b": comment\r\n",
                b"id: cursor-1\r\n",
                b"event: custom\r\n",
                b"data: one\r\n",
                b"data: two\r\n",
                b"\r\n",
                b"id: bad\0cursor\n",
                b"data: three\n",
                b"\n",
                b"id:\n",
                b"data: four\n",
            ]
        )
    ) == [
        SSEEvent("custom", "one\ntwo", "cursor-1"),
        SSEEvent("message", "three", "cursor-1"),
        SSEEvent("message", "four", ""),
    ]


def test_event_pump_reports_clean_eof_after_events() -> None:
    event = SSEEvent("custom", "payload", "cursor-one")
    incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue()
    client.pump_events([event], incoming, threading.Event())
    assert [incoming.get_nowait(), incoming.get_nowait()] == [event, None]
    assert incoming.empty()


@pytest.mark.parametrize(
    "failure",
    [
        OSError("disconnected"),
        http.client.IncompleteRead(b""),
        ValueError("invalid frame"),
    ],
)
def test_event_pump_reports_failure_then_eof(failure: Exception) -> None:
    event = SSEEvent("custom", "before failure")

    def events() -> Iterator[SSEEvent]:
        yield event
        raise failure

    incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue()
    client.pump_events(events(), incoming, threading.Event())
    assert [
        incoming.get_nowait(),
        incoming.get_nowait(),
        incoming.get_nowait(),
    ] == [
        event,
        failure,
        None,
    ]
    assert incoming.empty()


def test_event_pump_cancels_without_draining_a_full_queue() -> None:
    incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue(maxsize=1)
    queued = SSEEvent("custom", "already queued")
    incoming.put_nowait(queued)
    started = threading.Event()
    stopped = threading.Event()

    def events() -> Iterator[SSEEvent]:
        started.set()
        yield SSEEvent("custom", "blocked by backpressure")

    worker = threading.Thread(
        target=client.pump_events,
        args=(events(), incoming, stopped),
        daemon=True,
    )
    worker.start()
    try:
        assert started.wait(timeout=1)
    finally:
        stopped.set()
        worker.join(timeout=1)
    assert not worker.is_alive()
    assert incoming.get_nowait() == queued
    assert incoming.empty()


def test_open_events_uses_host_headers_and_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_response(monkeypatch, io.BytesIO())
    client.open_events(
        url="http://localhost:2718/base/api/marimo/v1",
        notebook="nb-one",
        token="private",
        identity="p1_one",
        name="Codex",
        cursor="cursor-1",
    )
    assert calls == [
        {
            "method": "GET",
            "url": "http://localhost:2718/base/api/marimo/v1/notebooks/nb-one/events?types=custom,attachment",
            "headers": {
                "Marimo-Attachment-Identity": "p1_one",
                "Marimo-Attachment-Kind": "agent",
                "Marimo-Attachment-Name": "Codex",
                "Authorization": "Bearer private",
                "Last-Event-ID": "cursor-1",
            },
            "body": None,
            "read_timeout": 45,
        }
    ]


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "interrupted"])
@pytest.mark.parametrize("stream", [True, False])
def test_execute_host_run_filters_other_runs(
    monkeypatch: pytest.MonkeyPatch, outcome: str, stream: bool
) -> None:
    response = io.BytesIO(_fixture(f"host-run-{outcome}.sse"))
    calls: list[dict[str, Any]] = []

    def open_response(**kwargs: Any) -> client.EventStream:
        calls.append(kwargs)
        if kwargs["method"] == "GET":
            return client.EventStream(response, Mock())
        # The ready frame must be consumed before submission.
        assert response.tell() > 0
        return client.EventStream(io.BytesIO(b'{"id":"run-one"}'), Mock())

    monkeypatch.setattr(client, "open_response", open_response)
    stdout, stderr = io.StringIO(), io.StringIO()
    result = client.execute(
        url="http://localhost:2718/api/marimo/v1",
        notebook_id="nb-one",
        token="private",
        code="print(42)",
        stdout=stdout,
        stderr=stderr,
        stream=stream,
    )
    assert result == client.ExecutionResult(
        outcome == "succeeded",
        {"mimetype": "text/plain", "data": "42"},
        "" if stream else "hello\n",
        "" if stream else "warning\n",
        outcome,
    )
    assert stdout.getvalue() == ("hello\n42\n" if stream else "")
    assert stderr.getvalue() == ("warning\n" if stream else "")
    assert [call["method"] for call in calls] == ["GET", "POST"]
    assert json.loads(calls[1]["body"]) == {"code": "print(42)"}
    from uuid import UUID

    UUID(calls[1]["headers"]["Idempotency-Key"])
    assert response.closed


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"event: ready\ndata: {}\n\n",
        b"event: ready\ndata: {}\n\nevent: execution\ndata: invalid\n\n",
    ],
)
def test_execute_missing_completion_is_unconfirmed(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    def open_response(**kwargs: Any) -> client.EventStream:
        return client.EventStream(
            io.BytesIO(
                body if kwargs["method"] == "GET" else b'{"id":"run-one"}'
            ),
            Mock(),
        )

    monkeypatch.setattr(client, "open_response", open_response)
    with pytest.raises(PairError):
        client.execute(
            url="http://localhost:2718/api/marimo/v1",
            notebook_id="nb-one",
            token="private",
            code="1",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            stream=False,
        )


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("with_traceback", [False, True])
def test_execution_error_snapshots_are_emitted_once(
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
    with_traceback: bool,
) -> None:
    error: dict[str, object] = {
        "name": "ValueError",
        "message": "<invalid value>",
    }
    expected = "ValueError: <invalid value>\n"
    if with_traceback:
        expected = "Traceback: original cell\n" + expected
        error["traceback"] = {"mimetype": "text/plain", "data": expected}
    frames = [b"event: ready\ndata: {}\n\n"]
    for status in ("concluded", "completed"):
        snapshot = {
            "execution": {
                "id": "execution-one",
                "run_id": "run-one",
                "status": status,
                "outcome": {"kind": "error", "error": error},
            }
        }
        frames.append(
            b"event: execution\ndata: "
            + json.dumps(snapshot).encode()
            + b"\n\n"
        )
    frames.append(
        b'event: run\ndata: {"run":{"id":"run-one","status":"completed","outcome":"failed"}}\n\n'
    )
    response = io.BytesIO(b"".join(frames))

    def open_response(**kwargs: Any) -> client.EventStream:
        return client.EventStream(
            response
            if kwargs["method"] == "GET"
            else io.BytesIO(b'{"id":"run-one"}'),
            Mock(),
        )

    monkeypatch.setattr(client, "open_response", open_response)
    stderr = io.StringIO()
    result = client.execute(
        url="http://localhost:2718/api/marimo/v1",
        notebook_id="nb-one",
        token="private",
        code="raise ValueError('<invalid value>')",
        stdout=io.StringIO(),
        stderr=stderr,
        stream=stream,
    )
    assert result == client.ExecutionResult(
        False, None, "", "" if stream else expected, "failed"
    )
    assert stderr.getvalue() == (expected if stream else "")
    assert response.closed


def test_lost_run_submission_response_is_unknown_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(b"event: ready\ndata: {}\n\n")
    calls: list[dict[str, Any]] = []

    def open_response(**kwargs: Any) -> client.EventStream:
        calls.append(kwargs)
        if kwargs["method"] == "GET":
            return client.EventStream(response, Mock())
        raise client.PairConnectionError("private transport details")

    monkeypatch.setattr(client, "open_response", open_response)
    fallback = Mock(
        side_effect=AssertionError("Execution must not be retried")
    )
    monkeypatch.setattr(client, "execute_editor", fallback)
    with pytest.raises(
        PairError, match="before completion was confirmed"
    ) as caught:
        client.execute(
            url="http://localhost:2718/api/marimo/v1",
            notebook_id="nb-one",
            token="private",
            code="side_effect()",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            stream=False,
        )
    assert type(caught.value) is PairError
    assert "private transport details" not in str(caught.value)
    assert [call["method"] for call in calls] == ["GET", "POST"]
    assert calls[1]["url"].endswith("/notebooks/nb-one/runtime/runs")
    fallback.assert_not_called()
    assert response.closed


@pytest.mark.parametrize(
    "url",
    [
        "ftp://user:private-password@localhost?access_token=private-token#private-fragment",
        "http://user:private-password@[?access_token=private-token#private-fragment",
        "http://user:private-password@localhost:99999?access_token=private-token#private-fragment",
    ],
)
def test_open_response_rejects_invalid_url_without_exposing_it(
    url: str,
) -> None:
    with pytest.raises(PairInputError) as caught:
        client.open_response(method="GET", url=url, headers={}, body=None)
    assert all(
        secret not in str(caught.value)
        for secret in (
            "private-password",
            "private-token",
            "private-fragment",
            "user:",
        )
    )


def test_list_sessions_sends_request_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(
        json.dumps(
            {
                "session-1": {
                    "session_id": "sess-stable-1",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
                    "state": "idle",
                },
                "session-2": {
                    "session_id": "sess-stable-2",
                    "filename": None,
                    "path": None,
                    "notebook_id": None,
                },
            }
        ).encode()
    )
    calls = _patch_response(monkeypatch, response)

    sessions = client.list_sessions(
        url=(
            "https://example.com/base/"
            "?access_token=query-token#ignored-fragment"
        ),
        token="secret-token",
    )

    assert sessions == {
        "session-1": {
            "session_id": "sess-stable-1",
            "filename": "analysis.py",
            "path": "/work/analysis.py",
            "notebook_id": "nb-analysis",
        },
        "session-2": {
            "session_id": "sess-stable-2",
            "filename": None,
            "path": None,
            "notebook_id": None,
        },
    }
    assert calls == [
        {
            "method": "GET",
            "url": (
                "https://example.com/base/api/sessions"
                "?access_token=query-token"
            ),
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


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"session-1": None},
        {"session-1": {}},
        {
            "session-1": {
                "session_id": "sess-stable",
                "filename": "analysis.py",
            }
        },
        {
            "session-1": {
                "session_id": "sess-stable",
                "path": "/work/analysis.py",
                "notebook_id": "nb-analysis",
            }
        },
        {
            "session-1": {
                "session_id": "sess-stable",
                "filename": [],
                "path": None,
                "notebook_id": None,
            }
        },
        {
            "session-1": {
                "session_id": "sess-stable",
                "filename": None,
                "path": [],
            }
        },
        {
            "session-1": {
                "session_id": None,
                "filename": None,
                "path": None,
                "notebook_id": None,
            }
        },
    ],
)
def test_list_sessions_rejects_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    response = io.BytesIO(json.dumps(payload).encode())
    _patch_response(monkeypatch, response)

    with pytest.raises(PairError) as exc_info:
        client.list_sessions(
            url="http://user:password@localhost:2718/"
            "?access_token=secret#fragment",
            token=None,
        )

    assert str(exc_info.value) == (
        "Unexpected response from http://localhost:2718/api/sessions."
    )
    assert "password" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
    assert response.closed


def test_list_sessions_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(b"{")
    _patch_response(monkeypatch, response)

    with pytest.raises(PairError) as exc_info:
        client.list_sessions(
            url="http://localhost:2718/?access_token=secret", token=None
        )

    assert str(exc_info.value) == (
        "Unexpected response from http://localhost:2718/api/sessions."
    )
    assert "secret" not in str(exc_info.value)
    assert response.closed


def test_list_sessions_rejects_server_without_stable_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = io.BytesIO(
        json.dumps(
            {
                "session-1": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
                }
            }
        ).encode()
    )
    _patch_response(monkeypatch, response)

    with pytest.raises(NotebookUnsupportedError):
        client.list_sessions(url="http://localhost:2718", token=None)

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
    (tmp_path / "bad-port.json").write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": 70000,
                "base_url": "",
            }
        ),
        encoding="utf-8",
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


class FakeStatusResponse:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self.body = body
        self.closed = False

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        self.closed = True


def test_raise_for_status_maps_invalid_session_id() -> None:
    response = FakeStatusResponse(
        500, json.dumps({"detail": "Invalid session id: s_old"}).encode()
    )

    with pytest.raises(StaleNotebookError, match="Invalid session id"):
        client._raise_for_status(response)

    assert response.closed


def test_raise_for_status_maps_invalid_stable_session_id() -> None:
    response = FakeStatusResponse(
        404,
        json.dumps({"detail": "Invalid stable session id: sess-old"}).encode(),
    )

    with pytest.raises(StaleNotebookError, match="Invalid stable session id"):
        client._raise_for_status(response)

    assert response.closed


def test_raise_for_status_maps_missing_legacy_header_to_upgrade() -> None:
    response = FakeStatusResponse(
        500,
        json.dumps({"detail": "Missing Marimo-Session-Id header"}).encode(),
    )

    with pytest.raises(NotebookUnsupportedError):
        client._raise_for_status(response)

    assert response.closed


def test_raise_for_status_uses_json_detail() -> None:
    response = FakeStatusResponse(
        500, json.dumps({"detail": "Some other server error"}).encode()
    )

    with pytest.raises(PairError, match="Some other server error") as error:
        client._raise_for_status(response)

    assert type(error.value) is PairError
    assert response.closed


def test_raise_for_status_falls_back_to_status_code() -> None:
    response = FakeStatusResponse(502, b"<html>Bad Gateway</html>")

    with pytest.raises(PairError, match=r"Server returned 502\."):
        client._raise_for_status(response)

    assert response.closed


def test_resolve_session_returns_only_stable_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "list_sessions",
        lambda **_kwargs: {
            "routing-id": {
                "session_id": "sess-stable",
                "filename": "analysis.py",
                "path": "/work/analysis.py",
                "notebook_id": "nb-analysis",
            }
        },
    )

    assert (
        client.resolve_notebook(url="http://one", token=None) == "nb-analysis"
    )


def test_resolve_session_zero_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client, "list_sessions", lambda **_kwargs: {})

    with pytest.raises(NoNotebookError, match="No host notebook") as exc_info:
        client.resolve_notebook(
            url="http://user:password@one?access_token=secret",
            token=None,
        )

    assert exc_info.value.url == "http://one"
    assert "password" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_resolve_session_many_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "list_sessions",
        lambda **_kwargs: {
            "routing-b": {
                "notebook_id": "sess-b",
                "filename": "nb.py",
                "path": "/b/nb.py",
            },
            "routing-a": {
                "notebook_id": "sess-a",
                "filename": "nb.py",
                "path": "/a/nb.py",
            },
        },
    )

    with pytest.raises(AmbiguousNotebookError) as exc_info:
        client.resolve_notebook(url="http://one", token=None)

    assert exc_info.value.candidates == ("sess-a", "sess-b")


def _host_record(
    path: Path, *, url: str, started: float | None = None
) -> None:
    from datetime import datetime, timezone

    import msgspec
    import psutil

    from marimo._core import protocol

    path.write_bytes(
        msgspec.json.encode(
            protocol.HostRecord(
                version=1,
                process=protocol.Process(
                    pid=os.getpid(),
                    started_at=datetime.fromtimestamp(
                        psutil.Process().create_time()
                        if started is None
                        else started,
                        tz=timezone.utc,
                    ),
                ),
                name="marimo",
                url=url,
                token="private-host-token",
            )
        )
    )
    path.chmod(0o600)


def test_resolve_host_skips_stale_and_malformed_records(
    tmp_path: Path,
) -> None:
    _host_record(
        tmp_path / "a-stale.json",
        url="http://127.0.0.1:2718/base/api/marimo/v1",
        started=1,
    )
    (tmp_path / "b-malformed.json").write_text("{}")
    _host_record(
        tmp_path / "c-live.json",
        url="http://127.0.0.1:2718/base/api/marimo/v1",
    )
    result = client.resolve_host("http://localhost:2718/base/", root=tmp_path)
    assert result == client.HostEndpoint(
        "http://127.0.0.1:2718/base/api/marimo/v1", "private-host-token"
    )
    assert "private-host-token" not in repr(result)


@pytest.mark.skipif(os.name != "posix", reason="POSIX private file validation")
@pytest.mark.parametrize(
    "kind", ["public", "symlink", "wrong-port", "wrong-base"]
)
def test_resolve_host_rejects_unsafe_or_unmatched_records(
    tmp_path: Path, kind: str
) -> None:
    record = tmp_path / "record.json"
    _host_record(record, url="http://127.0.0.1:2718/api/marimo/v1")
    selected = "http://localhost:2718"
    if kind == "public":
        record.chmod(0o644)
    elif kind == "symlink":
        record.rename(tmp_path / "record.private")
        record.symlink_to(tmp_path / "record.private")
    elif kind == "wrong-port":
        selected = "http://localhost:2719"
    else:
        selected += "/base"
    with pytest.raises(PairError, match="local edit server"):
        client.resolve_host(selected, root=tmp_path)


def test_resolve_notebook_filters_unsaved_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "list_sessions",
        lambda **_: {
            "one": {"notebook_id": "nb-one"},
            "two": {"notebook_id": None},
            "three": {"notebook_id": "nb-one"},
        },
    )
    assert (
        client.resolve_notebook(url="http://localhost:2718", token=None)
        == "nb-one"
    )


@pytest.mark.parametrize(
    ("problem", "error"),
    [
        ("no-runtime", client.NoRuntimeError),
        ("conflict", client.RunConflictError),
    ],
)
def test_host_problem_types_map_to_cli_errors(
    problem: str, error: type[PairError]
) -> None:
    response = FakeStatusResponse(
        409,
        json.dumps(
            {
                "type": f"tag:marimo.io,2026:host/{problem}",
                "detail": "host detail",
            }
        ).encode(),
    )
    with pytest.raises(error, match="host detail"):
        client._raise_for_status(response)
    assert response.closed
