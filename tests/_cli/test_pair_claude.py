# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import queue
import socket
import sys
import threading
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import msgspec
import pytest

from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.connection import ConnectionStore, connection_identity
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.forwarder import ForwarderConfig, start_forwarder
from marimo._cli.pair.harnesses import detect_target, harness_for
from marimo._cli.pair.harnesses.claude import ClaudeHarness
from tests._cli._pair_server import pair_test_server

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Claude adapter uses Unix sockets"
)


@pytest.fixture
def inbox() -> Iterator[tuple[str, socket.socket]]:
    # macOS limits Unix socket paths to 104 bytes.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="pair-", dir="/tmp") as directory:
        address = str(Path(directory) / "inbox.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen()
            yield address, listener


def test_detect_native_inbox(
    inbox: tuple[str, socket.socket],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import psutil

    address, _ = inbox
    owner = ProcessHandle.capture(os.getpid())
    process = Mock(pid=owner.pid)
    process.name.side_effect = AssertionError("Use CLAUDE_PID, not names")
    process.cmdline.side_effect = AssertionError("Use CLAUDE_PID, not argv")
    monkeypatch.setattr(psutil.Process, "parents", lambda _: [process])
    harness, target = detect_target(
        {
            "CLAUDE_CODE_MESSAGING_SOCKET": address,
            "CLAUDE_CODE_MESSAGING_TOKEN": "private-token",
            "CLAUDE_PID": str(owner.pid),
        },
        "claude",
    )
    assert isinstance(harness, ClaudeHarness)
    assert target == DeliveryTarget(
        "claude", address, "Claude Code", owner, "private-token"
    )
    assert harness.open_inbox(target).alive()
    assert "private-token" not in repr(target)
    config = ForwarderConfig(
        "http://localhost", "nb-one", "identity", None, target
    )
    assert (
        msgspec.json.decode(msgspec.json.encode(config), type=ForwarderConfig)
        == config
    )


def test_missing_inbox_is_not_detected() -> None:
    assert ClaudeHarness().detect({}) is None
    assert isinstance(harness_for("claude"), ClaudeHarness)


def test_explicit_pid_does_not_require_claude_pid(
    inbox: tuple[str, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    import psutil

    address, _ = inbox
    owner = ProcessHandle.capture(os.getpid())
    monkeypatch.setattr(
        psutil.Process,
        "parents",
        Mock(side_effect=AssertionError("Explicit PID must bypass discovery")),
    )
    _, target = detect_target(
        {
            "CLAUDE_CODE_MESSAGING_SOCKET": address,
            "CLAUDE_CODE_MESSAGING_TOKEN": "private-token",
        },
        "claude",
        pid=owner.pid,
    )
    assert target == DeliveryTarget(
        "claude", address, "Claude Code", owner, "private-token"
    )


def test_reject_stale_or_symlink_inbox(
    inbox: tuple[str, socket.socket], tmp_path: Path
) -> None:
    address, _ = inbox
    link = tmp_path / "link"
    link.symlink_to(address)
    for path in (str(tmp_path / "missing"), str(link)):
        with pytest.raises(PairInputError, match="socket is unavailable"):
            ClaudeHarness().detect({"CLAUDE_CODE_MESSAGING_SOCKET": path})


def test_require_own_child_token(inbox: tuple[str, socket.socket]) -> None:
    address, _ = inbox
    with pytest.raises(PairInputError, match="inbox token"):
        ClaudeHarness().detect({"CLAUDE_CODE_MESSAGING_SOCKET": address})


def test_require_claude_parent(
    inbox: tuple[str, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    import psutil

    address, _ = inbox
    monkeypatch.setattr(psutil.Process, "parents", lambda _: [])
    with pytest.raises(PairInputError, match="native Claude Code session"):
        ClaudeHarness().detect(
            {
                "CLAUDE_CODE_MESSAGING_SOCKET": address,
                "CLAUDE_CODE_MESSAGING_TOKEN": "private-token",
                "CLAUDE_PID": str(os.getpid()),
            }
        )


@pytest.mark.parametrize("pid", ["", "invalid", "0", "-1"])
def test_require_documented_pid(
    inbox: tuple[str, socket.socket], pid: str
) -> None:
    address, _ = inbox
    with pytest.raises(PairInputError, match="valid CLAUDE_PID"):
        ClaudeHarness().detect(
            {
                "CLAUDE_CODE_MESSAGING_SOCKET": address,
                "CLAUDE_CODE_MESSAGING_TOKEN": "private-token",
                "CLAUDE_PID": pid,
            }
        )


def test_send_preserves_text_and_authenticates(
    inbox: tuple[str, socket.socket],
) -> None:
    address, listener = inbox
    target = DeliveryTarget(
        "claude", address, "Claude Code", auth_token="private-token"
    )
    text = 'Unicode 🐍\n"quotes"; $(must not execute)'
    ClaudeHarness().open_inbox(target).send(text)
    listener.settimeout(2)
    with listener.accept()[0] as connection:
        with connection.makefile("rb") as reader:
            assert [json.loads(line) for line in reader] == [
                {"type": "auth", "token": "private-token"},
                {"type": "user", "message": {"role": "user", "content": text}},
            ]


def test_send_failure_does_not_leak(tmp_path: Path) -> None:
    target = DeliveryTarget(
        "claude",
        str(tmp_path / "missing"),
        "Claude Code",
        auth_token="private-token",
    )
    with pytest.raises(PairError, match="Could not deliver") as error:
        ClaudeHarness().open_inbox(target).send("private-message")
    assert "private-token" not in str(error.value)
    assert "private-message" not in str(error.value)


def test_liveness_tracks_socket_and_process(
    inbox: tuple[str, socket.socket],
) -> None:
    address, _ = inbox
    harness = ClaudeHarness()
    owner = ProcessHandle.capture(os.getpid())
    assert not harness.open_inbox(
        DeliveryTarget("claude", address, "Claude Code")
    ).alive()
    assert not harness.open_inbox(
        DeliveryTarget(
            "claude", address, "Claude Code", ProcessHandle(owner.pid, 0)
        )
    ).alive()
    Path(address).unlink()
    assert not harness.open_inbox(
        DeliveryTarget("claude", address, "Claude Code", owner)
    ).alive()


def test_detached_forwarder_delivers_to_claude_socket(
    inbox: tuple[str, socket.socket],
    tmp_path: Path,
) -> None:
    from marimo._cli.pair.client import resolve_host

    address, listener = inbox
    received: queue.Queue[list[dict[str, object]]] = queue.Queue()

    def read() -> None:
        listener.settimeout(10)
        with listener.accept()[0] as connection:
            connection.settimeout(10)
            with connection.makefile("rb") as reader:
                received.put([json.loads(line) for line in reader])

    with pair_test_server(tmp_path) as server:
        host = resolve_host(server.url)
        target = DeliveryTarget(
            "claude",
            address,
            "Claude Code",
            ProcessHandle.capture(os.getpid()),
            "private-inbox-token",
        )
        config = ForwarderConfig(
            host.url,
            server.notebook_id,
            connection_identity(server.notebook_id, "claude", address),
            host.token,
            target,
        )
        store = ConnectionStore(tmp_path / "connections")
        record = start_forwarder(config, store)
        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        try:
            message = {"error": "Claude socket delivery 🐍"}
            request = urllib.request.Request(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/messages",
                method="POST",
                data=json.dumps(message).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 202
            frames = received.get(timeout=10)
            assert frames[0] == {
                "type": "auth",
                "token": "private-inbox-token",
            }
            assert frames[1]["type"] == "user"
            body = frames[1]["message"]
            assert isinstance(body, dict)
            assert body["role"] == "user"
            assert "Claude socket delivery" in body["content"]
            assert all(
                "private-inbox-token" not in path.read_text()
                for path in tmp_path.rglob("*.json")
            )
        finally:
            record.forwarder.stop()
            store.remove(record)
            thread.join(timeout=1)
