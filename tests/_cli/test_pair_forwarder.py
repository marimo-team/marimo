# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands, forwarder
from marimo._cli.pair.artifacts import AgentMessageFiles
from marimo._cli.pair.client import (
    HostEndpoint,
    PairConnectionError,
    PairError,
    SSEEvent,
    StaleNotebookError,
)
from marimo._cli.pair.connection import ConnectionStore, connection_identity
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.forwarder import ForwarderConfig, run_forwarder
from tests._cli.test_pair_delivery import record

if TYPE_CHECKING:
    import queue


class RecordingInbox:
    inbox_bytes = 512

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.living = True

    def alive(self) -> bool:
        return self.living

    def send(self, text: str) -> None:
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
        _cursor: str | None = None,
    ) -> None:
        calls(config)
        for event in scripts.pop(0):
            if event is None:
                event = SSEEvent(
                    "attachment.removed",
                    json.dumps({"id": "att-one"}),
                )
            if stopped.is_set():
                return
            incoming.put(event)
            if isinstance(event, SSEEvent) and event.name == "attachment":
                incoming.put(SSEEvent("ready", "{}"))

    monkeypatch.setattr(forwarder, "_read_stream", read)
    return calls


def attached(identity: str = "identity") -> SSEEvent:
    return SSEEvent(
        "attachment",
        json.dumps({"attachment": {"identity": identity, "id": "att-one"}}),
    )


def agent_message(value: object) -> SSEEvent:
    return SSEEvent(
        "custom",
        json.dumps(
            {"custom": {"type": "marimo.pair.agent-message", "data": value}}
        ),
    )


def test_coalescing_bounds_final_messages(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AgentMessageFiles, "cleanup", lambda _: None)
    install_stream(
        monkeypatch,
        [
            [
                attached(),
                agent_message("one"),
                agent_message("two"),
                agent_message("😀" * 1000),
                agent_message({"lens": "custom"}),
                None,
            ]
        ],
    )
    inbox = RecordingInbox()
    ready = Mock()
    run_forwarder(config, inbox, ready=ready)
    ready.assert_called_once()
    assert len(inbox.messages) == 3
    assert "one" in inbox.messages[0]
    assert "two" in inbox.messages[0]
    for message in inbox.messages:
        assert len(message.encode("utf-8")) <= inbox.inbox_bytes
    path = Path(
        inbox.messages[1].rsplit("Complete JSON agent message: ", 1)[1][:-1]
    )
    assert json.loads(path.read_text(encoding="utf-8")) == "😀" * 1000


def test_reconnect_preserves_identity(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_stream(
        monkeypatch,
        [
            [
                attached(),
                agent_message("first"),
                http.client.IncompleteRead(b""),
            ],
            [attached(), SSEEvent("heartbeat", ""), agent_message(None), None],
        ],
    )
    inbox = RecordingInbox()
    ready = Mock()
    run_forwarder(config, inbox, ready=ready)
    assert calls.call_args_list == [((config,),), ((config,),)]
    ready.assert_called_once()
    assert len(inbox.messages) == 2
    assert inbox.messages[0].endswith("first")
    assert inbox.messages[1].endswith("null")


def test_reconnect_backoff_caps_and_resets_after_attachment(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    dropped = PairConnectionError("wording can change")
    scripts: list[list[SSEEvent | Exception | None]] = [[attached(), dropped]]
    scripts.extend([[dropped] for _ in range(8)])
    scripts.extend([[attached(), dropped], [attached(), None]])
    install_stream(monkeypatch, scripts)
    wait = Mock(return_value=True)
    monkeypatch.setattr(forwarder, "_wait_reconnect", wait)
    ready = Mock()
    run_forwarder(config, RecordingInbox(), ready=ready)
    assert [call.args[1] for call in wait.call_args_list] == [
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
        run_forwarder(config, RecordingInbox(), ready=Mock())
    calls.assert_called_once()


def test_reconnect_wait_stops_when_harness_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = RecordingInbox()
    monkeypatch.setattr(
        time, "sleep", lambda _: setattr(inbox, "living", False)
    )
    assert not forwarder._wait_reconnect(inbox, 5)


@pytest.mark.parametrize(
    "first",
    [
        agent_message("too early"),
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
        run_forwarder(config, RecordingInbox(), ready=ready)
    ready.assert_not_called()


def test_stale_notebook_exit(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stream(
        monkeypatch,
        [
            [attached(), OSError("drop")],
            [StaleNotebookError("Invalid stable session id")],
        ],
    )
    run_forwarder(config, RecordingInbox(), ready=Mock())


def test_send_failure_does_not_retry_delivery(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stream(monkeypatch, [[attached(), agent_message("once"), None]])
    inbox = RecordingInbox()
    send = Mock(side_effect=PairError("rejected"))
    monkeypatch.setattr(inbox, "send", send)
    with pytest.raises(PairError, match="rejected"):
        run_forwarder(config, inbox, ready=Mock())
    send.assert_called_once()


def test_dead_harness_closes_reader(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox = RecordingInbox()
    closed = threading.Event()

    def read(
        _config: object,
        incoming: queue.Queue[SSEEvent | Exception | None],
        stopped: threading.Event,
        _responses: object,
        _cursor: str | None = None,
    ) -> None:
        incoming.put(attached())
        stopped.wait(timeout=2)
        closed.set()

    monkeypatch.setattr(forwarder, "_read_stream", read)
    monkeypatch.setattr(forwarder, "_LIVENESS_SECONDS", 0.01)
    run_forwarder(config, inbox, ready=lambda: setattr(inbox, "living", False))
    assert closed.is_set()


def test_dead_harness_never_connects(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_stream(monkeypatch, [])
    inbox = RecordingInbox()
    inbox.living = False
    run_forwarder(config, inbox, ready=Mock())
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
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda _: HostEndpoint("http://server/api/marimo/v1", "host-token"),
    )
    store = ConnectionStore(tmp_path)
    monkeypatch.setattr(commands, "ConnectionStore", lambda: store)
    return store


def test_connect_and_detach_lifecycle(
    isolated_cli: ConnectionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = ProcessHandle.capture(os.getpid())
    target = DeliveryTarget("codex", "thread", "Codex", process=owner)
    harness = Mock()
    check = Mock()
    monkeypatch.setattr(harness, "check", check)
    monkeypatch.setattr(
        commands, "detect_target", lambda *_: (harness, target)
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
        [
            "pair",
            *["connect", "--url", "http://server", "--notebook", "s_one"],
        ],
    )
    assert result.exit_code == 0, result.output
    check.assert_called_once()
    stop.assert_called_once()
    assert start.call_args.args[0].identity == previous.identity
    assert isolated_cli.load(previous.identity) is None
    isolated_cli.save(previous)
    result = runner.invoke(
        cli_main,
        ["pair", *["detach", "--notebook", "s_one"]],
    )
    assert result.exit_code == 0, result.output
    assert isolated_cli.load(previous.identity) is None
    assert stop.call_count == 2


def test_connect_flag_off(
    isolated_cli: ConnectionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        isolated_cli.load(connection_identity("s_one", "codex", "thread"))
        is None
    )
    monkeypatch.delenv("MARIMO_PAIR_NEXT")
    result = CliRunner().invoke(
        cli_main,
        [
            "pair",
            *["connect", "--url", "http://server", "--notebook", "s_one"],
        ],
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
        b"event: custom\n",
        b"data: null\n",
        b"\n",
    ]
    assert list(iter_sse(lines)) == [SSEEvent("custom", "null")]
    assert list(iter_sse(lines, heartbeats=True)) == [
        SSEEvent("heartbeat", ""),
        SSEEvent("custom", "null"),
    ]


def test_reconnect_uses_processed_cursor_and_ignores_old_removal(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    cursors: list[str | None] = []
    scripts: list[list[SSEEvent | Exception | None]] = [
        [
            attached(),
            SSEEvent("ready", "{}", "10"),
            SSEEvent(
                "custom",
                json.dumps(
                    {
                        "custom": {
                            "type": "marimo.pair.agent-message",
                            "data": "first",
                        }
                    }
                ),
                "11",
            ),
            OSError("drop"),
        ],
        [
            SSEEvent(
                "attachment.removed",
                json.dumps({"id": "att-one"}),
                "12",
            ),
            SSEEvent(
                "custom",
                json.dumps({"custom": {"type": "other", "data": "ignore"}}),
                "13",
            ),
            SSEEvent(
                "custom",
                json.dumps(
                    {
                        "custom": {
                            "type": "marimo.pair.agent-message",
                            "data": "replayed",
                        }
                    }
                ),
                "14",
            ),
            SSEEvent(
                "attachment",
                json.dumps(
                    {
                        "attachment": {
                            "identity": config.identity,
                            "id": "att-two",
                        }
                    }
                ),
                "15",
            ),
            SSEEvent("ready", "{}", "15"),
            SSEEvent(
                "attachment.removed",
                json.dumps({"id": "att-two"}),
                "16",
            ),
        ],
    ]

    def read(
        _config: ForwarderConfig,
        incoming: queue.Queue[SSEEvent | Exception | None],
        _stopped: threading.Event,
        _responses: object,
        cursor: str | None = None,
    ) -> None:
        cursors.append(cursor)
        for event in scripts.pop(0):
            incoming.put(event)

    monkeypatch.setattr(forwarder, "_read_stream", read)
    inbox = RecordingInbox()
    ready = Mock()
    run_forwarder(config, inbox, ready=ready)
    assert cursors == [None, "11"]
    assert [message.rsplit("\n", 1)[1] for message in inbox.messages] == [
        "first",
        "replayed",
    ]
    ready.assert_called_once()


def test_reset_replaces_attachment_without_second_ready(
    config: ForwarderConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_stream(
        monkeypatch,
        [
            [
                attached(),
                SSEEvent("reset", "{}"),
                attached(),
                agent_message({"opaque": [1, None]}),
                None,
            ]
        ],
    )
    inbox = RecordingInbox()
    ready = Mock()
    run_forwarder(config, inbox, ready=ready)
    ready.assert_called_once()
    assert inbox.messages[0].endswith('{"opaque": [1, null]}')
