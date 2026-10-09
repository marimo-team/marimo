# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands, forwarder
from marimo._cli.pair.artifacts import HandoffFiles
from marimo._cli.pair.client import (
    PairConnectionError,
    PairError,
    SSEEvent,
    StaleSessionError,
)
from marimo._cli.pair.connection import ConnectionStore, attachment_id
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.forwarder import ForwarderConfig, run_forwarder
from tests._cli.test_pair_delivery import record

if TYPE_CHECKING:
    import queue


class Adapter:
    kind = "codex"
    inbox_bytes = 512

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.living = True

    def identity(self, _env: object) -> None:
        return None

    def check(self) -> None:
        pass

    def detect(self, _env: object) -> None:
        return None

    def alive(self, _target: DeliveryTarget) -> bool:
        return self.living

    def send(self, _target: DeliveryTarget, text: str) -> None:
        self.messages.append(text)


@pytest.fixture
def config() -> ForwarderConfig:
    return ForwarderConfig(
        "http://server",
        "s_one",
        "identity",
        "private-token",
        DeliveryTarget(
            "codex",
            "thread",
            "Codex",
            process=ProcessHandle.capture(os.getpid()),
        ),
    )


def install_stream(
    monkeypatch: pytest.MonkeyPatch,
    scripts: list[list[SSEEvent | Exception | None]],
) -> Mock:
    calls = Mock()

    def read(
        config: ForwarderConfig,
        incoming: queue.Queue[SSEEvent | Exception | None],
        stopped: threading.Event,
        _responses: object,
    ) -> None:
        calls(config)
        for event in scripts.pop(0):
            if stopped.is_set():
                return
            incoming.put(event)

    monkeypatch.setattr(forwarder, "_read_stream", read)
    return calls


def attached(identity: str = "identity") -> SSEEvent:
    return SSEEvent("attached", json.dumps({"id": identity}))


def handoff(value: object) -> SSEEvent:
    return SSEEvent("handoff", json.dumps(value))


def test_coalescing_bounds_final_messages(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(HandoffFiles, "cleanup", lambda _: None)
    install_stream(
        monkeypatch,
        [
            [
                attached(),
                handoff("one"),
                handoff("two"),
                handoff("😀" * 1000),
                handoff({"lens": "custom"}),
                None,
            ]
        ],
    )
    adapter = Adapter()
    ready = Mock()
    run_forwarder(config, adapter, ready=ready)
    ready.assert_called_once()
    assert len(adapter.messages) == 3
    assert "one" in adapter.messages[0]
    assert "two" in adapter.messages[0]
    for message in adapter.messages:
        assert len(message.encode("utf-8")) <= adapter.inbox_bytes
    path = Path(
        adapter.messages[1].rsplit("Complete JSON handoff: ", 1)[1][:-1]
    )
    assert json.loads(path.read_text(encoding="utf-8")) == "😀" * 1000


def test_reconnect_preserves_identity_and_no_replay(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_stream(
        monkeypatch,
        [
            [attached(), handoff("first"), http.client.IncompleteRead(b"")],
            [attached(), SSEEvent("heartbeat", ""), handoff(None), None],
        ],
    )
    adapter = Adapter()
    ready = Mock()
    run_forwarder(config, adapter, ready=ready)
    assert calls.call_args_list == [((config,),), ((config,),)]
    ready.assert_called_once()
    assert len(adapter.messages) == 2
    assert adapter.messages[0].endswith("first")
    assert adapter.messages[1].endswith("null")


def test_reconnect_backoff_caps_and_resets_after_attachment(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    dropped = PairConnectionError("wording can change")
    install_stream(
        monkeypatch,
        [[attached(), dropped]]
        + [[dropped] for _ in range(8)]
        + [[attached(), dropped], [attached(), None]],
    )
    wait = Mock(return_value=True)
    monkeypatch.setattr(forwarder, "_wait_reconnect", wait)
    ready = Mock()
    run_forwarder(config, Adapter(), ready=ready)
    assert [call.args[2] for call in wait.call_args_list] == [
        0.1,
        0.2,
        0.4,
        0.8,
        1.6,
        3.2,
        5.0,
        5.0,
        5.0,
        0.1,
    ]
    ready.assert_called_once()


def test_authentication_failure_after_attachment_does_not_reconnect(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_stream(
        monkeypatch, [[attached(), PairError("Authentication failed.")]]
    )
    with pytest.raises(PairError, match="could not continue"):
        run_forwarder(config, Adapter(), ready=Mock())
    calls.assert_called_once()


def test_reconnect_wait_stops_when_harness_exits(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = Adapter()
    monkeypatch.setattr(
        forwarder.time, "sleep", lambda _: setattr(adapter, "living", False)
    )
    assert not forwarder._wait_reconnect(adapter, config.target, 5)


@pytest.mark.parametrize(
    "first",
    [
        handoff("too early"),
        attached("wrong"),
        PairError("Authentication failed."),
    ],
)
def test_startup_failure(
    config: ForwarderConfig,
    monkeypatch: pytest.MonkeyPatch,
    first: SSEEvent | Exception,
) -> None:
    install_stream(monkeypatch, [[first]])
    ready = Mock()
    with pytest.raises(PairError):
        run_forwarder(config, Adapter(), ready=ready)
    ready.assert_not_called()


def test_stale_session_exit(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stream(
        monkeypatch,
        [
            [attached(), OSError("drop")],
            [StaleSessionError("Invalid stable session id")],
        ],
    )
    run_forwarder(config, Adapter(), ready=Mock())


def test_send_failure_does_not_retry_delivery(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stream(monkeypatch, [[attached(), handoff("once"), None]])
    adapter = Adapter()
    send = Mock(side_effect=PairError("rejected"))
    monkeypatch.setattr(adapter, "send", send)
    with pytest.raises(PairError, match="rejected"):
        run_forwarder(config, adapter, ready=Mock())
    send.assert_called_once()


def test_dead_harness_closes_reader(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = Adapter()
    closed = threading.Event()

    def read(
        _config: object,
        incoming: queue.Queue[SSEEvent | Exception | None],
        stopped: threading.Event,
        _responses: object,
    ) -> None:
        incoming.put(attached())
        stopped.wait(timeout=2)
        closed.set()

    monkeypatch.setattr(forwarder, "_read_stream", read)
    monkeypatch.setattr(forwarder, "_LIVENESS_SECONDS", 0.01)
    run_forwarder(
        config, adapter, ready=lambda: setattr(adapter, "living", False)
    )
    assert closed.is_set()


def test_dead_harness_never_connects(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_stream(monkeypatch, [])
    adapter = Adapter()
    adapter.living = False
    run_forwarder(config, adapter, ready=Mock())
    calls.assert_not_called()


def test_detached_platform_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "DETACHED_PROCESS", 8, raising=False)
    monkeypatch.setattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )
    assert forwarder.detached_options() == {"creationflags": 520}
    monkeypatch.setattr(sys, "platform", "darwin")
    assert forwarder.detached_options() == {"start_new_session": True}


@pytest.fixture
def isolated_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> ConnectionStore:
    monkeypatch.setenv("MARIMO_PAIR_NEXT", "1")
    monkeypatch.setenv("CODEX_SESSION_ID", "thread")
    store = ConnectionStore(tmp_path)
    monkeypatch.setattr(commands, "ConnectionStore", lambda: store)
    return store


def test_connect_and_detach_lifecycle(
    isolated_cli: ConnectionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = ProcessHandle.capture(os.getpid())
    target = DeliveryTarget("codex", "thread", "Codex", process=owner)
    adapter = Adapter()
    check = Mock()
    monkeypatch.setattr(adapter, "check", check)
    monkeypatch.setattr(
        commands, "detect_target", lambda *_: (adapter, target)
    )
    start = Mock(return_value=record(owner))
    stop = Mock()
    monkeypatch.setattr(commands, "start_forwarder", start)
    monkeypatch.setattr(ProcessHandle, "stop", stop)
    previous = record(owner)
    isolated_cli.save(previous)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["pair", *["connect", "--url", "http://server", "--session", "s_one"]],
    )
    assert result.exit_code == 0, result.output
    check.assert_called_once()
    stop.assert_called_once()
    assert start.call_args.args[0].attachment == previous.attachment_id
    assert isolated_cli.load(previous.attachment_id) is None
    isolated_cli.save(previous)
    result = runner.invoke(
        cli_main,
        ["pair", *["detach", "--session", "s_one"]],
    )
    assert result.exit_code == 0, result.output
    assert isolated_cli.load(previous.attachment_id) is None
    assert stop.call_count == 2


def test_events_and_flag_off(
    isolated_cli: ConnectionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert isolated_cli.load(attachment_id("s_one", "codex", "thread")) is None
    response = io.BytesIO(
        b'event: attached\ndata: {"id":"one"}\n\nevent: handoff\ndata: null\n\n'
    )
    open_events = Mock(return_value=response)
    monkeypatch.setattr(commands, "open_events", open_events)
    result = CliRunner().invoke(
        cli_main,
        ["pair", *["events", "--url", "http://server", "--session", "s_one"]],
    )
    assert result.exit_code == 0, result.output
    assert result.output == 'attached: {"id":"one"}\nhandoff: null\n'
    assert response.closed
    assert open_events.call_args.kwargs["name"] == "pair events"
    monkeypatch.delenv("MARIMO_PAIR_NEXT")
    result = CliRunner().invoke(
        cli_main,
        ["pair", *["connect", "--url", "http://server", "--session", "s_one"]],
    )
    assert result.exit_code == 1
    assert "MARIMO_PAIR_NEXT=1" in result.output


def test_stream_close_interrupts_blocked_read() -> None:
    import socket

    from marimo._cli.pair.client import EventStream

    left, right = socket.socketpair()
    finished = threading.Event()

    def read() -> None:
        try:
            assert left.recv(1) == b""
        finally:
            finished.set()

    thread = threading.Thread(target=read)
    try:
        thread.start()
        response = Mock()
        EventStream(response, left).close()
        assert finished.wait(timeout=1)
        response.close.assert_called_once()
        assert left.fileno() == -1
    finally:
        left.close()
        right.close()
        thread.join(timeout=1)


def test_heartbeat_parser_is_opt_in() -> None:
    from marimo._cli.pair.client import iter_sse

    lines = [
        b": keep-alive\n",
        b"\n",
        b"event: handoff\n",
        b"data: null\n",
        b"\n",
    ]
    assert list(iter_sse(lines)) == [SSEEvent("handoff", "null")]
    assert list(iter_sse(lines, heartbeats=True)) == [
        SSEEvent("heartbeat", ""),
        SSEEvent("handoff", "null"),
    ]
