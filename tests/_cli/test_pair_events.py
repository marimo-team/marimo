# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from click import unstyle
from click.testing import CliRunner

from marimo._cli.cli import main
from marimo._cli.pair import client, commands

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.mark.parametrize(
    ("pretty", "terminal", "no_color", "colored"),
    [
        (True, True, None, True),
        (True, False, None, False),
        (True, True, "1", False),
        (True, True, "true", False),
        (False, True, None, False),
    ],
)
def test_events_colors_only_pretty_terminal_output(
    monkeypatch: pytest.MonkeyPatch,
    pretty: bool,
    terminal: bool,
    no_color: str | None,
    colored: bool,
) -> None:
    monkeypatch.setattr(commands, "_supports_color", lambda: True)
    monkeypatch.setattr(
        commands,
        "sys",
        Mock(stdout=Mock(isatty=lambda: terminal)),
    )
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda _: client.HostEndpoint("http://localhost:2718", "private"),
    )
    stream = io.BytesIO(
        b'event: runtime\ndata: {"status": "running"}\n\n'
        b"event: ready\ndata: {}\n\n"
    )
    monkeypatch.setattr(commands, "open_events", Mock(return_value=stream))
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "events",
            "--notebook",
            "nb-one",
            "--url",
            "http://localhost:2718",
            *(["--pretty"] if pretty else []),
        ],
        color=True,
    )
    assert result.exit_code == 0, result.output
    assert ("\x1b[" in result.stdout) is colored
    plain = unstyle(result.stdout)
    events = plain.strip().split("\n\n" if pretty else "\n")
    assert [json.loads(event) for event in events] == [
        {"event": "runtime", "data": {"status": "running"}},
        {"event": "ready", "data": {}},
    ]
    assert not plain.startswith("\n")
    assert not plain.endswith("\n\n")


@pytest.mark.parametrize(
    "types",
    [None, "ui_element,runtime,execution", " ui_element, runtime ,execution "],
)
@pytest.mark.parametrize("notebook", [None, "nb-one"])
def test_events_prints_json_lines_and_passes_filters(
    monkeypatch: pytest.MonkeyPatch, types: str | None, notebook: str | None
) -> None:
    payloads = [
        {
            "event": "ui_element",
            "data": {"ui_element": {"id": "slider", "state": {"value": 3}}},
        },
        {"event": "ready", "id": "cursor-1", "data": {}},
        {
            "event": "future.event",
            "id": "cursor-2",
            "data": {"unknown": [1, 2]},
        },
        {"event": "reset", "data": {}},
    ]
    frames = ": heartbeat\n\n" + "".join(
        (f"id: {event['id']}\n" if "id" in event else "")
        + f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
        for event in payloads
    )
    response = io.BytesIO(frames.encode())
    transport = Mock(return_value=client.EventStream(response, Mock()))
    monkeypatch.setattr(client, "open_response", transport)
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda _: client.HostEndpoint(
            "http://localhost:2718/base/api/marimo/v1", "private"
        ),
    )
    options = [] if types is None else ["--types", types]
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "events",
            *(["--notebook", notebook] if notebook is not None else []),
            "--url",
            "http://localhost:2718/base",
            *options,
        ],
    )
    assert result.exit_code == 0, result.output
    assert [
        json.loads(line) for line in result.stdout.splitlines()
    ] == payloads
    request = transport.call_args.kwargs
    path = "/events" if notebook is None else "/notebooks/nb-one/events"
    assert urlsplit(request["url"]).path == "/base/api/marimo/v1" + path
    assert parse_qs(urlsplit(request["url"]).query) == (
        {} if types is None else {"types": ["ui_element,runtime,execution"]}
    )
    assert request["headers"]["Authorization"] == "Bearer private"
    assert ("Marimo-Attachment-Identity" in request["headers"]) is (
        notebook is not None
    )
    assert request["read_timeout"] is None
    assert response.closed


@pytest.mark.parametrize(
    "types", ["", " ", ",", "runtime,", ",runtime", "runtime,,execution"]
)
def test_events_rejects_empty_types_before_connecting(
    monkeypatch: pytest.MonkeyPatch, types: str
) -> None:
    resolve = Mock()
    monkeypatch.setattr(commands, "resolve_host", resolve)
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "events",
            "--notebook",
            "nb-one",
            "--url",
            "http://localhost:2718",
            "--types",
            types,
        ],
    )
    assert result.exit_code == 2
    assert "--types" in result.stderr
    assert "empty" in result.stderr
    resolve.assert_not_called()


@pytest.mark.parametrize(
    "error", [KeyboardInterrupt(), OSError("disconnected")]
)
def test_events_closes_the_stream_on_interrupt_or_failure(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    def interrupted() -> Iterator[bytes]:
        yield from [b"event: ready\n", b"data: {}\n", b"\n"]
        raise error

    stream = Mock()
    stream.__iter__ = Mock(side_effect=interrupted)
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda _: client.HostEndpoint(
            "http://localhost:2718/api/marimo/v1", "private"
        ),
    )
    monkeypatch.setattr(client, "open_response", Mock(return_value=stream))
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "events",
            "--notebook",
            "nb-one",
            "--url",
            "http://localhost:2718",
        ],
    )
    assert result.exit_code == 1
    assert "Traceback" not in result.stderr
    stream.close.assert_called_once()


def test_events_reports_host_errors_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        commands,
        "resolve_host",
        Mock(side_effect=client.PairError("Authentication failed.")),
    )
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "events",
            "--notebook",
            "nb-one",
            "--url",
            "http://localhost:2718",
        ],
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: Authentication failed.\n"
