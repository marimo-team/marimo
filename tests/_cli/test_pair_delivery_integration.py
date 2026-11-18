# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import msgspec
import pytest
from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands
from marimo._cli.pair.client import iter_sse, open_events, resolve_host
from marimo._cli.pair.connection import ConnectionStore, connection_identity
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle, Submission
from marimo._cli.pair.forwarder import ForwarderConfig, run_forwarder
from marimo._cli.pair.harnesses.codex import CodexHarness
from marimo._messaging.agents import MessageRequest, SendResult
from tests._cli._pair_server import PairTestServer, pair_test_server

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping


class ControlledInbox:
    inbox_bytes = 8192

    def __init__(
        self, submit: Callable[[str], Submission] | None = None
    ) -> None:
        self.messages: list[str] = []
        self.running = True
        self._submit = submit

    def alive(self) -> bool:
        return self.running

    def send(self, text: str) -> Submission:
        self.messages.append(text)
        return self._submit(text) if self._submit else Submission("submitted")


@contextmanager
def running_forwarder(
    server: PairTestServer,
    inbox: ControlledInbox,
    *,
    identity: str = "agent",
    name: str = "Test",
    address: str = "test",
) -> Iterator[threading.Thread]:
    host = resolve_host(server.url)
    ready = threading.Event()
    thread = threading.Thread(
        target=run_forwarder,
        args=(
            ForwarderConfig(
                host.url,
                server.notebook_id,
                identity,
                host.token,
                DeliveryTarget("test", address, name),
            ),
            inbox,
        ),
        kwargs={"ready": ready.set},
        daemon=True,
    )
    thread.start()
    try:
        assert ready.wait(10)
        yield thread
    finally:
        inbox.running = False
        thread.join(timeout=3)


def send_message(
    server: PairTestServer,
    message: object,
    *,
    to: str | None = None,
    sender: str | None = None,
    auth_token: str | None = None,
) -> SendResult:
    body = MessageRequest(
        str(uuid4()), message, to=to, broadcast=to is None, sender=sender
    )
    headers = {"Content-Type": "application/json"}
    if auth_token is not None:
        headers["Authorization"] = f"Bearer {auth_token}"
    request = urllib.request.Request(
        f"{server.url}/api/pair/notebooks/{server.stable_session_id}/messages",
        data=msgspec.json.encode(body),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        result = msgspec.json.decode(response.read(), type=SendResult)
    assert result.message_id == body.message_id
    return result


def wait_messages(path: Path, count: int) -> list[dict[str, str]]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            messages = [
                json.loads(line) for line in path.read_text().splitlines()
            ]
            if len(messages) >= count:
                return messages
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(0.05)
    raise AssertionError(
        "The detached forwarder did not deliver the expected messages."
    )


@pytest.mark.skipif(
    os.name != "posix", reason="The stub executable uses a POSIX shebang."
)
def test_detached_delivery_replacement_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox = tmp_path / "inbox.jsonl"
    binary = tmp_path / "bin" / "codex"
    binary.parent.mkdir()
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "if sys.argv[1:4] == ['app-server', 'daemon', 'version']:\n"
        "    print(json.dumps({'status': 'running'}))\n"
        "elif sys.argv[1:] == ['queue', '--help']:\n"
        "    print('Queue help')\n"
        "else:\n"
        f"    with open({str(inbox)!r}, 'a', encoding='utf-8') as output:\n"
        "        output.write(json.dumps({'thread': sys.argv[3], 'message': sys.argv[5]}) + '\\n')\n"
    )
    binary.chmod(0o700)
    monkeypatch.setenv(
        "PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}"
    )
    store = ConnectionStore(tmp_path / "state" / "connections-v1")
    monkeypatch.setattr(commands, "ConnectionStore", lambda: store)
    owner = ProcessHandle.capture(os.getpid())
    original_detect = CodexHarness.detect

    def detect(
        self: CodexHarness,
        env: Mapping[str, str],
        *,
        process: ProcessHandle | None = None,
        check_ready: bool = True,
    ) -> DeliveryTarget | None:
        return original_detect(
            self, env, process=process or owner, check_ready=check_ready
        )

    monkeypatch.setattr(CodexHarness, "detect", detect)
    for key in (
        "CLAUDE_PID",
        "CLAUDE_CODE_MESSAGING_SOCKET",
        "CLAUDE_CODE_MESSAGING_TOKEN",
        "OPENCODE_TERMINAL",
        "OPENCODE",
    ):
        monkeypatch.delenv(key, raising=False)
    runner = CliRunner()
    records = []
    with pair_test_server(tmp_path, token="editor-test-secret") as server:
        arguments = [
            "--url",
            server.url,
            "--notebook",
            server.notebook_id,
        ]
        try:
            for thread, selection in (
                ("first", ["--session", server.notebook_id]),
                (
                    "editor",
                    [
                        "--url",
                        server.url,
                        "--session",
                        server.stable_session_id,
                        "--token",
                        "editor-test-secret",
                    ],
                ),
                (
                    "second",
                    [
                        "--url",
                        server.url,
                        "--notebook",
                        server.notebook_id,
                    ],
                ),
            ):
                connection_arguments = [
                    *selection,
                    "--harness",
                    "codex",
                    "--pid",
                    str(owner.pid),
                ]
                monkeypatch.setenv("CODEX_SESSION_ID", thread)
                automatic = [
                    "pair",
                    "execute",
                    *selection,
                    "--code",
                    "print('automatic')",
                ]
                result = runner.invoke(
                    cli_main,
                    automatic
                    if thread == "first"
                    else ["pair", "connect", *connection_arguments],
                )
                assert result.exit_code == 0, result.output
                record = store.load(
                    connection_identity(server.notebook_id, "codex", thread)
                )
                assert record is not None
                assert (record.harness_pid, record.harness_start) == (
                    owner.pid,
                    owner.started,
                )
                assert record.forwarder.alive()
                records.append(record)
                if thread == "first":
                    again = runner.invoke(cli_main, automatic)
                    assert again.exit_code == 0, again.output
                    assert json.loads(again.stdout)["stdout"] == "automatic\n"
                    assert store.load(record.identity) == record

            send_message(
                server,
                {
                    "type": "cell-output",
                    "code": "1/0",
                    "output": {
                        "message": "division by zero",
                        "traceback": "full\ntraceback",
                    },
                },
                auth_token="editor-test-secret",
            )
            first = wait_messages(inbox, 3)
            assert {message["thread"] for message in first} == {
                "first",
                "second",
                "editor",
            }
            assert first[0]["message"] == first[1]["message"]

            large = {"lens": "😀" * 10000}
            send_message(server, large, auth_token="editor-test-secret")
            messages = wait_messages(inbox, 6)
            references = []
            for message in messages[3:]:
                assert len(message["message"].encode("utf-8")) <= 8192
                path = Path(
                    message["message"].rsplit(
                        "Complete JSON agent message: ", 1
                    )[1][:-1]
                )
                assert json.loads(path.read_text(encoding="utf-8")) == large
                references.append(path)
            assert references[0] != references[1]

            previous = records[-1]
            result = runner.invoke(
                cli_main, ["pair", "connect", *connection_arguments]
            )
            assert result.exit_code == 0, result.output
            replacement = store.load(previous.identity)
            assert replacement is not None
            assert replacement.forwarder.alive()
            records.append(replacement)
            assert not previous.forwarder.alive()

            result = runner.invoke(
                cli_main,
                ["pair", "execute", *arguments, "-c", "print('connected')"],
            )
            assert result.exit_code == 0, result.output
            assert json.loads(result.stdout)["stdout"] == "connected\n"

            replacement.forwarder.stop()
            result = runner.invoke(
                cli_main,
                [
                    "pair",
                    "execute",
                    *arguments,
                    "-c",
                    "print('still executes')",
                ],
            )
            assert result.exit_code == 0, result.output
            result = runner.invoke(
                cli_main,
                ["pair", "detach", "--notebook", server.notebook_id],
            )
            assert result.exit_code == 0, result.output
            assert store.load(replacement.identity) is None
            for path in references:
                assert json.loads(path.read_text(encoding="utf-8")) == large
        finally:
            for record in records:
                record.forwarder.stop()
                with store.locked(record.identity):
                    store.remove(record)


def test_failed_start_removes_record(tmp_path: Path) -> None:
    from marimo._cli.pair.client import PairError
    from marimo._cli.pair.forwarder import ForwarderConfig, start_forwarder

    identity = connection_identity("s_one", "codex", "thread")
    config = ForwarderConfig(
        "http://127.0.0.1:1",
        "s_one",
        identity,
        "private-token",
        DeliveryTarget(
            "codex",
            "thread",
            "Codex",
            process=ProcessHandle.capture(os.getpid()),
        ),
    )
    store = ConnectionStore(tmp_path)
    with store.locked(identity):
        with pytest.raises(PairError, match="could not attach"):
            start_forwarder(config, store)
    assert store.load(identity) is None
    assert "private-token" not in "".join(
        path.read_text() for path in tmp_path.glob("*.json")
    )


def test_subprocess_reconnect_replays_messages_and_server_detach(
    tmp_path: Path,
) -> None:
    with pair_test_server(tmp_path) as server:
        host = resolve_host(server.url)
        observer = open_events(
            url=host.url,
            notebook=server.notebook_id,
            token=host.token,
            identity="observer",
            name="Replay observer",
            read_timeout=10,
        )
        events = iter_sse(observer)
        for event in events:
            if event.name == "ready":
                break
        config = ForwarderConfig(
            host.url,
            server.notebook_id,
            "replay-test",
            host.token,
            DeliveryTarget(
                "test",
                "replay-conversation",
                "Replay test",
                process=ProcessHandle.capture(os.getpid()),
            ),
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "tests._cli._pair_replay", str(tmp_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        process.stdin.write(msgspec.json.encode(config) + b"\n")
        process.stdin.flush()

        def attachment() -> str:
            for event in events:
                if event.name == "attachment":
                    value = json.loads(event.data)["attachment"]
                    if value.get("identity") == config.identity:
                        identity = value["id"]
                        assert isinstance(identity, str)
                        return identity
            raise AssertionError("No forwarder attachment")

        assert process.stdout is not None
        output = process.stdout

        def receive() -> bytes:
            lines: queue.Queue[bytes] = queue.Queue(maxsize=1)
            reader = threading.Thread(
                target=lambda: lines.put(output.readline()), daemon=True
            )
            reader.start()
            try:
                line = lines.get(timeout=10)
            except queue.Empty:
                line = b""
            if line:
                return line
            if process.poll() is None:
                process.kill()
            reader.join(timeout=5)
            _, stderr = process.communicate(timeout=5)
            raise AssertionError(
                "Replay subprocess did not respond:\n"
                + stderr.decode(errors="replace")
            )

        try:
            assert receive() in (b"attached\n", b"attached\r\n")
            first_id = attachment()
            send_message(server, "before drop")
            wait_messages(tmp_path / "inbox.jsonl", 1)
            process.stdin.write(b"drop\n")
            process.stdin.flush()
            cursor = json.loads(receive())["cursor"]
            assert isinstance(cursor, str)
            assert cursor
            process.stdin.write(b"resume\n")
            process.stdin.flush()
            second_id = attachment()
            assert second_id != first_id
            send_message(server, "after reconnect")
            messages = wait_messages(tmp_path / "inbox.jsonl", 2)
            assert [
                message["message"].rsplit("\n", 1)[1] for message in messages
            ] == ["before drop", "after reconnect"]
            request = urllib.request.Request(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/attachments/detach",
                method="POST",
                data=json.dumps({"attachment_id": second_id}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 204
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, stderr.decode()
            assert stdout == b""
        finally:
            observer.close()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


@pytest.mark.parametrize("sender", [None, "Lens", "😀" * 64, ""])
def test_pointer_delivery_is_private_and_targeted(
    tmp_path: Path, sender: str | None
) -> None:
    with pair_test_server(tmp_path) as server, ExitStack() as stack:
        host = resolve_host(server.url)
        observer = open_events(
            url=host.url,
            notebook=server.notebook_id,
            token=host.token,
            identity="observer",
            name="Observer",
            kind="tool",
            read_timeout=10,
        )
        events = iter_sse(observer)
        for event in events:
            if event.name == "ready":
                break
        inboxes = [ControlledInbox(), ControlledInbox()]
        try:
            for i, inbox in enumerate(inboxes):
                stack.enter_context(
                    running_forwarder(
                        server,
                        inbox,
                        identity=f"agent-{i}",
                        name=f"Agent {i}",
                        address=str(i),
                    )
                )

            from urllib.error import HTTPError

            for invalid_sender in (
                "x" * 65,
                "Lens\nAdmin",
                "Lens\r",
                "Lens\u2028Admin",
            ):
                with pytest.raises(HTTPError) as error:
                    send_message(
                        server, "invalid sender", sender=invalid_sender
                    )
                assert error.value.code == 400
                assert "sender" in error.value.read().decode()

            result = send_message(
                server,
                {"secret": "private error"},
                to="agent-0",
                sender=sender,
            )
            assert msgspec.to_builtins(list(result.recipients)) == [
                {
                    "agent_id": "agent-0",
                    "name": "Agent 0",
                    "status": "submitted",
                    "reason": None,
                    "detail": None,
                }
            ]
            expected_prefix = (
                "Agent message from marimo (notebook pair-integration.py). "
                "No reply is expected.\n"
            )
            if sender is not None:
                expected_prefix += f"Sender (not verified): {sender}\n"
            assert inboxes[0].messages == [
                expected_prefix + '{"secret": "private error"}'
            ]
            assert inboxes[1].messages == []
            result = send_message(
                server, {"secret": "private error"}, sender=sender
            )
            assert [r.status for r in result.recipients] == [
                "submitted",
                "submitted",
            ]
            assert [len(i.messages) for i in inboxes] == [2, 1]
            pointers = []
            for event in events:
                assert "private error" not in event.data
                assert "report_key" not in event.data
                if event.name == "custom":
                    pointer = json.loads(event.data)["custom"]
                    assert pointer["type"] == "marimo.agents.pointer.v1"
                    assert set(pointer["data"]) == {
                        "message_id",
                        "attempt_id",
                        "attachment_id",
                        "agent_id",
                        "sender",
                    }
                    assert pointer["data"]["sender"] == sender
                    pointers.append(pointer)
                    if len(pointers) == 3:
                        break
            assert len(pointers) == 3
            from urllib.error import HTTPError

            pointer = pointers[0]["data"]
            for key in (None, "wrong-key"):
                headers = {
                    "Authorization": f"Bearer {host.token}",
                    "Content-Type": "application/json",
                    "Marimo-Agent-Attachment": pointer["attachment_id"],
                }
                if key:
                    headers["Marimo-Agent-Report-Key"] = key
                base = f"{host.url}/notebooks/{server.notebook_id}/messages"
                for url, body in (
                    (f"{base}/{pointer['attempt_id']}/content", b"{}"),
                    (
                        f"{base}/report",
                        json.dumps(
                            {
                                "attempt_id": pointer["attempt_id"],
                                "attachment_id": pointer["attachment_id"],
                                "status": "submitted",
                            }
                        ).encode(),
                    ),
                ):
                    request = urllib.request.Request(
                        url, data=body, headers=headers, method="POST"
                    )
                    with pytest.raises(HTTPError) as error:
                        urllib.request.urlopen(request, timeout=5)
                    assert error.value.code == 403
        finally:
            observer.close()


@pytest.fixture
def claude_inbox() -> Iterator[tuple[DeliveryTarget, queue.Queue[str]]]:
    import socket
    import tempfile

    received: queue.Queue[str] = queue.Queue()
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="pair-") as directory:
        address = str(Path(directory) / "inbox.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen()
            listener.settimeout(15)

            def accept() -> None:
                connection, _ = listener.accept()
                with connection:
                    data = b""
                    while chunk := connection.recv(65536):
                        data += chunk
                    received.put(data.decode())

            thread = threading.Thread(target=accept, daemon=True)
            thread.start()
            try:
                yield (
                    DeliveryTarget(
                        "claude",
                        address,
                        "Claude Code",
                        ProcessHandle.capture(os.getpid()),
                        "private-token",
                    ),
                    received,
                )
            finally:
                thread.join(timeout=3)


@pytest.fixture
def opencode_inbox(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[DeliveryTarget, queue.Queue[str]]]:
    response_status = getattr(request, "param", 200)
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received: queue.Queue[str] = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            pass

        def do_POST(self) -> None:
            body = json.loads(
                self.rfile.read(int(self.headers["Content-Length"]))
            )
            received.put(body["text"])
            self.send_response(response_status)
            self.end_headers()
            self.wfile.write(
                msgspec.json.encode(
                    {
                        "data": {
                            "id": "msg_one",
                            "type": "user",
                            "sessionID": "ses_one",
                        }
                    }
                )
            )

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as http:
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            address = f"http://127.0.0.1:{http.server_port}/api/session/ses_one/prompt"
            yield (
                DeliveryTarget(
                    "opencode",
                    address,
                    "OpenCode",
                    ProcessHandle.capture(os.getpid()),
                    "private-token",
                ),
                received,
            )
        finally:
            http.shutdown()
            thread.join(timeout=3)


@pytest.fixture(params=["claude_inbox", "opencode_inbox"])
def native_inbox(
    request: pytest.FixtureRequest,
) -> tuple[DeliveryTarget, queue.Queue[str]]:
    inbox: tuple[DeliveryTarget, queue.Queue[str]] = request.getfixturevalue(
        request.param
    )
    return inbox


@pytest.mark.skipif(os.name != "posix", reason="Claude uses Unix sockets")
def test_native_submission_outcomes(
    tmp_path: Path,
    native_inbox: tuple[DeliveryTarget, queue.Queue[str]],
) -> None:
    from marimo._cli.pair.forwarder import start_forwarder

    target, received = native_inbox
    store = ConnectionStore(tmp_path / "connections")
    with pair_test_server(tmp_path) as server:
        host = resolve_host(server.url)
        identity = connection_identity(
            server.notebook_id, target.kind, target.address
        )
        config = ForwarderConfig(
            host.url, server.notebook_id, identity, host.token, target
        )
        with store.locked(config.identity):
            record = start_forwarder(config, store)
        try:
            result = send_message(
                server, "native delivery", to=identity, sender="Lens"
            ).recipients[0]
            assert result.status == (
                "unknown" if target.kind == "claude" else "submitted"
            )
            assert result.reason == (
                "unconfirmed" if target.kind == "claude" else None
            )
            text = received.get(timeout=5)
            if target.kind == "claude":
                auth, frame = [json.loads(line) for line in text.splitlines()]
                assert auth == {"type": "auth", "token": "private-token"}
                assert frame == {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": (
                            "Agent message from marimo (notebook pair-integration.py). "
                            "No reply is expected.\n"
                            "Sender (not verified): Lens\nnative delivery"
                        ),
                    },
                }
            else:
                assert "Sender (not verified): Lens" in text
            assert "native delivery" in text
            assert "No reply is expected" in text
            assert "pair-integration.py" in text
        finally:
            record.forwarder.stop()


@pytest.mark.parametrize(
    ("outcome", "status", "reason", "detail"),
    [
        (
            Submission("rejected", "refused", "refused"),
            "rejected",
            "refused",
            "refused",
        ),
        (
            Submission("rejected", "invalid", "invalid"),
            "rejected",
            "invalid",
            "invalid",
        ),
        (OSError("inbox failed"), "unknown", "failed", None),
        (RuntimeError("unexpected inbox failure"), "unknown", "failed", None),
        (
            Submission("rejected", "😀" * 501, "refused"),
            "rejected",
            "refused",
            "😀" * 500,
        ),
    ],
)
def test_forwarder_failure_results(
    tmp_path: Path,
    outcome: Submission | Exception,
    status: str,
    reason: str,
    detail: str | None,
) -> None:
    def submit(_text: str) -> Submission:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    inbox = ControlledInbox(submit)
    with (
        pair_test_server(tmp_path) as server,
        running_forwarder(server, inbox),
    ):
        result = send_message(server, "message", to="agent").recipients[0]
        assert (result.status, result.reason) == (status, reason)
        if detail is not None:
            assert result.detail == detail


def test_absent_recipients_are_results(tmp_path: Path) -> None:
    with pair_test_server(tmp_path) as server:
        result = send_message(server, "message", to="absent")
        assert [(r.status, r.reason) for r in result.recipients] == [
            ("rejected", "not-connected")
        ]
        assert send_message(server, "message").recipients == ()


def test_attempts_stay_on_the_original_attachment(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    entered = threading.Event()
    release = threading.Event()

    def blocked_submission(_text: str) -> Submission:
        entered.set()
        assert release.wait(10)
        return Submission("submitted")

    with pair_test_server(tmp_path) as server, ExitStack() as stack:
        host = resolve_host(server.url)
        observer = open_events(
            url=host.url,
            notebook=server.notebook_id,
            token=host.token,
            identity="observer",
            kind="tool",
            name="Observer",
            read_timeout=10,
        )
        events = iter_sse(observer)
        for event in events:
            if event.name == "ready":
                break
        inboxes = [ControlledInbox(blocked_submission), ControlledInbox()]
        try:
            stack.enter_context(running_forwarder(server, inboxes[0]))
            with ThreadPoolExecutor(2) as executor:
                fetched = executor.submit(
                    send_message, server, "fetched", to="agent"
                )
                assert entered.wait(10)
                unfetched = executor.submit(
                    send_message, server, "unfetched", to="agent"
                )
                pointers = []
                for event in events:
                    if event.name == "custom":
                        pointers.append(
                            json.loads(event.data)["custom"]["data"]
                        )
                        if len(pointers) == 2:
                            break
                attachment_id = pointers[0]["attachment_id"]
                request = urllib.request.Request(
                    f"{server.url}/api/pair/notebooks/{server.stable_session_id}/attachments/detach",
                    method="POST",
                    data=json.dumps({"attachment_id": attachment_id}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.status == 204
                stack.enter_context(running_forwarder(server, inboxes[1]))
                assert (
                    fetched.result(5).recipients[0].status,
                    fetched.result().recipients[0].reason,
                ) == ("unknown", "disconnected")
                assert (
                    unfetched.result(5).recipients[0].status,
                    unfetched.result().recipients[0].reason,
                ) == ("rejected", "disconnected")
                release.set()
            assert inboxes[1].messages == []
            assert (
                send_message(server, "new attempt", to="agent")
                .recipients[0]
                .status
                == "submitted"
            )
            assert len(inboxes[1].messages) == 1
            assert inboxes[1].messages[0].endswith("new attempt")
        finally:
            release.set()
            observer.close()


@pytest.mark.parametrize(
    ("opencode_inbox", "status", "reason"),
    [
        (400, "rejected", "invalid"),
        (403, "rejected", "refused"),
        (500, "unknown", "failed"),
    ],
    indirect=["opencode_inbox"],
)
def test_native_harness_failure_results(
    tmp_path: Path,
    opencode_inbox: tuple[DeliveryTarget, queue.Queue[str]],
    status: str,
    reason: str,
) -> None:
    from marimo._cli.pair.forwarder import start_forwarder

    target, _ = opencode_inbox
    store = ConnectionStore(tmp_path / "connections")
    with pair_test_server(tmp_path) as server:
        host = resolve_host(server.url)
        identity = connection_identity(
            server.notebook_id, target.kind, target.address
        )
        config = ForwarderConfig(
            host.url, server.notebook_id, identity, host.token, target
        )
        with store.locked(config.identity):
            record = start_forwarder(config, store)
        try:
            result = send_message(server, "message", to=identity).recipients[0]
            assert (result.status, result.reason) == (status, reason)
        finally:
            record.forwarder.stop()


def test_blocking_agents_from_cell_and_widget(tmp_path: Path) -> None:
    inbox = ControlledInbox()
    with (
        pair_test_server(tmp_path, token="editor-secret") as server,
        ExitStack() as stack,
    ):

        def post(path: str, body: object) -> dict:
            request = urllib.request.Request(
                f"{server.url}{path}",
                data=json.dumps(body).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer editor-secret",
                    "Marimo-Session-Id": server.session_id,
                    "Idempotency-Key": str(uuid4()),
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.load(response)

        def execute(code: str) -> str:
            cell_id = uuid4().hex[:4]
            base = f"/api/marimo/v1/notebooks/{server.notebook_id}"
            post(
                base + "/edits",
                {
                    "changes": [
                        {
                            "kind": "put_cell",
                            "base_etag": None,
                            "cell": {"id": cell_id, "code": code},
                        }
                    ]
                },
            )
            run = post(base + "/runtime/runs", {"cells": [{"id": cell_id}]})
            output = ""
            while True:
                event = json.loads(server._websocket.recv(timeout=15))
                if event["event"] == "console":
                    output += event["data"]["console"]["text"]
                if (
                    event["event"] == "marimo"
                    and event["data"]["marimo"]["op"] == "completed-run"
                    and event["data"]["marimo"]["run_id"] == run["id"]
                ):
                    return output

        initial = execute(
            "import marimo as mo, msgspec\n"
            "print(mo.agents.available())\n"
            "print(mo.agents.list())\n"
            "print(mo.agents.broadcast(None).recipients)\n"
            "print(mo.agents.send(None, to='absent').recipients[0].reason)"
        )
        assert initial == "True\n()\n()\nnot-connected\n"
        stack.enter_context(running_forwarder(server, inbox))
        output = execute(
            "print(mo.agents.available())\n"
            "print([(a.id, a.name) for a in mo.agents.list()])\n"
            "print(msgspec.json.encode(mo.agents.send({'from': 'cell'}, to='agent', sender='Lens')).decode())\n"
            "results = []\n"
            "button = mo.ui.button(on_change=lambda _: results.append(mo.agents.broadcast({'from': 'widget'}, sender='Lens')))\n"
            "print(button._id)"
        ).splitlines()
        assert output[:2] == ["True", "[('agent', 'Test')]"]
        cell_result = json.loads(output[2])
        assert cell_result["recipients"] == [
            {
                "agent_id": "agent",
                "name": "Test",
                "status": "submitted",
                "reason": None,
                "detail": None,
            }
        ]
        assert inbox.messages[-1].endswith('{"from": "cell"}')
        request = urllib.request.Request(
            f"{server.url}/api/kernel/set_ui_element_value",
            data=json.dumps(
                {"objectIds": [output[3]], "values": [1]}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Marimo-Session-Id": server.session_id,
                "Authorization": "Bearer editor-secret",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        callback_result = json.loads(
            execute("print(msgspec.json.encode(results[0]).decode())")
        )
        assert inbox.messages[-1].endswith('{"from": "widget"}')
        assert callback_result["recipients"] == cell_result["recipients"]
        assert callback_result["message_id"] != cell_result["message_id"]


def test_agent_listing_retains_first_connection_order(tmp_path: Path) -> None:
    with pair_test_server(tmp_path) as server, ExitStack() as stack:
        host = resolve_host(server.url)
        threads: list[threading.Thread] = []
        streams = []

        def start(identity: str, name: str) -> ControlledInbox:
            inbox = ControlledInbox()
            threads.append(
                stack.enter_context(
                    running_forwarder(
                        server,
                        inbox,
                        identity=identity,
                        name=name,
                    )
                )
            )
            return inbox

        def listing() -> list[dict[str, str]]:
            with urllib.request.urlopen(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/agents",
                timeout=5,
            ) as response:
                return json.load(response)

        try:
            for kind, messaging in [("agent", False), ("client", True)]:
                stream = open_events(
                    url=host.url,
                    notebook=server.notebook_id,
                    token=host.token,
                    identity=kind,
                    name="Not a recipient",
                    kind=kind,
                    messaging=messaging,
                )
                streams.append(stream)
                for event in iter_sse(stream):
                    if event.name == "ready":
                        break
            assert listing() == []
            first = start("z", "First")
            start("a", "Second")
            assert listing() == [
                {"id": "z", "name": "First"},
                {"id": "a", "name": "Second"},
            ]
            first.running = False
            for event in iter_sse(streams[0]):
                if event.name == "attachment":
                    attachment = json.loads(event.data)["attachment"]
                    if attachment["identity"] == "z":
                        break
            request = urllib.request.Request(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/attachments/detach",
                data=json.dumps({"attachment_id": attachment["id"]}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 204
            threads[0].join(timeout=10)
            assert not threads[0].is_alive()
            assert listing() == [{"id": "a", "name": "Second"}]
            start("z", "Reconnected")
            assert listing() == [
                {"id": "z", "name": "Reconnected"},
                {"id": "a", "name": "Second"},
            ]
        finally:
            for stream in streams:
                stream.close()
