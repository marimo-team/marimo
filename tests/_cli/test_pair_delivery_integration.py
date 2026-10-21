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
from pathlib import Path

import msgspec
import pytest
from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands
from marimo._cli.pair.client import iter_sse, open_events, resolve_host
from marimo._cli.pair.connection import ConnectionStore, connection_identity
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.forwarder import ForwarderConfig
from tests._cli._pair_server import pair_test_server


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
@pytest.mark.parametrize("ipc", [False, True])
@pytest.mark.parametrize(
    "widget",
    [False, pytest.param(True, marks=pytest.mark.requires("anywidget"))],
)
def test_detached_delivery_replacement_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ipc: bool, widget: bool
) -> None:
    if ipc:
        (tmp_path / "pyproject.toml").write_text(
            f"[tool.marimo.venv]\npath = {json.dumps(sys.prefix)}\nwritable = false\n"
        )
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
    runner = CliRunner()
    records = []
    with pair_test_server(tmp_path) as server:
        arguments = [
            "--url",
            server.url,
            "--notebook",
            server.notebook_id,
        ]
        connection_arguments = [
            *arguments,
            "--harness",
            "codex",
            "--pid",
            str(owner.pid),
        ]
        try:
            for thread in ("first", "second"):
                monkeypatch.setenv("CODEX_SESSION_ID", thread)
                result = runner.invoke(
                    cli_main, ["pair", "connect", *connection_arguments]
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

            def send(payload: object) -> None:
                request = urllib.request.Request(
                    f"{server.url}/api/pair/notebooks/{server.stable_session_id}/messages",
                    data=json.dumps(
                        {"message": payload, "broadcast": True}
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.status == 200
                    assert {
                        r["status"] for r in json.load(response)["recipients"]
                    } == {"submitted"}

            send(
                {
                    "type": "cell-output",
                    "code": "1/0",
                    "output": {
                        "message": "division by zero",
                        "traceback": "full\ntraceback",
                    },
                }
            )
            first = wait_messages(inbox, 2)
            assert {message["thread"] for message in first} == {
                "first",
                "second",
            }
            assert first[0]["message"] == first[1]["message"]

            code = (
                "import marimo as mo\n"
                "print(len(mo.agents.list()))\n"
                f"print(mo.agents.send({{'from': 'python'}}, to={records[0].identity!r}).recipients[0].status)\n"
            )
            result = runner.invoke(
                cli_main, ["pair", "execute", *arguments, "-c", code]
            )
            assert result.exit_code == 0, result.output
            assert json.loads(result.stdout)["stdout"] == "2\nsubmitted\n"
            python_messages = wait_messages(inbox, 3)
            assert python_messages[2]["thread"] == "first"
            assert json.loads(
                python_messages[2]["message"].split("\n", 1)[1]
            ) == {"from": "python"}

            if widget:
                widget_code = (
                    "import anywidget, builtins\n"
                    "builtins._messaging_widget = anywidget.AnyWidget()\n"
                    "builtins._widget_results = []\n"
                    "def on_agent_message(widget, content, buffers):\n"
                    "    import builtins, marimo as mo\n"
                    "    from marimo._runtime.context import get_context\n"
                    f"    result = mo.agents.send(content, to={records[0].identity!r})\n"
                    "    builtins._widget_results.append((get_context().cell_id, result.recipients[0].status))\n"
                    "builtins._messaging_widget.on_msg(on_agent_message)\n"
                    "print(builtins._messaging_widget._model_id)\n"
                )
                result = runner.invoke(
                    cli_main,
                    ["pair", "execute", *arguments, "-c", widget_code],
                )
                assert result.exit_code == 0, result.output
                model_id = json.loads(result.stdout)["stdout"].strip()
                request = urllib.request.Request(
                    f"{server.url}/api/kernel/set_model_value",
                    data=json.dumps(
                        {
                            "modelId": model_id,
                            "message": {
                                "method": "custom",
                                "content": {"from": "widget"},
                            },
                            "buffers": [],
                        }
                    ).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Marimo-Session-Id": server.session_id,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.status == 200
                result = runner.invoke(
                    cli_main,
                    [
                        "pair",
                        "execute",
                        *arguments,
                        "-c",
                        "import builtins\nprint(builtins._widget_results)\nbuiltins._messaging_widget.close()\ndel builtins._widget_results, builtins._messaging_widget",
                    ],
                )
                assert result.exit_code == 0, result.output
                assert (
                    json.loads(result.stdout)["stdout"]
                    == "[(None, 'submitted')]\n"
                )
                assert wait_messages(inbox, 4)[3]["thread"] == "first"

            large = {"lens": "😀" * 10000}
            send(large)
            messages = wait_messages(inbox, 5 + int(widget))
            references = []
            for message in messages[3 + int(widget) :]:
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


def test_subprocess_reconnect_does_not_redirect_messages_and_server_detach(
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

        def send(message: str) -> str:
            request = urllib.request.Request(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/messages",
                method="POST",
                data=json.dumps(
                    {"message": message, "to": config.identity}
                ).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 200
                return json.load(response)["recipients"][0]["status"]

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
            assert send("before drop") == "submitted"
            wait_messages(tmp_path / "inbox.jsonl", 1)
            process.stdin.write(b"drop\n")
            process.stdin.flush()
            cursor = json.loads(receive())["cursor"]
            assert isinstance(cursor, str)
            assert cursor
            assert send("during gap") == "rejected"
            process.stdin.write(b"resume\n")
            process.stdin.flush()
            second_id = attachment()
            assert second_id != first_id
            assert send("after reconnect") == "submitted"
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


@pytest.mark.parametrize("ipc", [False, True])
def test_python_http_uses_editor_auth_and_base_path(
    tmp_path: Path, ipc: bool
) -> None:
    if ipc:
        (tmp_path / "pyproject.toml").write_text(
            f"[tool.marimo.venv]\npath = {json.dumps(sys.prefix)}\nwritable = false\n"
        )
    with pair_test_server(
        tmp_path,
        token="private-editor-token",
        base_url="/embedded",
        skew_protection=True,
    ) as server:
        code = (
            "import marimo as mo\n"
            "print(mo.agents.list())\n"
            "print(mo.agents.send(None, to='absent').recipients[0].status)\n"
        )
        result = CliRunner().invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                server.url,
                "--notebook",
                server.notebook_id,
                "-c",
                code,
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["stdout"] == "()\nrejected\n"
