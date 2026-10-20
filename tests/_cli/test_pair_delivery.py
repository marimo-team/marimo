# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from marimo._cli.pair.artifacts import AgentMessageFiles, inbox_message
from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.connection import (
    Connection,
    ConnectionStore,
    connection_identity,
)
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.harnesses import detect_target
from marimo._cli.pair.harnesses.claude import ClaudeHarness
from marimo._cli.pair.harnesses.codex import CodexHarness


@pytest.fixture
def codex_ready(monkeypatch: pytest.MonkeyPatch) -> Mock:
    check = Mock()
    monkeypatch.setattr(CodexHarness, "check", check)
    return check


@pytest.fixture
def owner() -> ProcessHandle:
    return ProcessHandle.capture(os.getpid())


@pytest.mark.parametrize(
    ("env", "address"),
    [
        ({}, None),
        ({"CODEX_SESSION_ID": "root", "CODEX_THREAD_ID": "child"}, "root"),
        ({"CODEX_THREAD_ID": "child"}, "child"),
        ({"CODEX_SESSION_ID": "", "CODEX_THREAD_ID": "child"}, "child"),
    ],
)
def test_codex_detect(
    env: dict[str, str],
    address: str | None,
    monkeypatch: pytest.MonkeyPatch,
    owner: ProcessHandle,
    codex_ready: Mock,
) -> None:
    import psutil

    parent = Mock(pid=owner.pid)
    parent.name.return_value = "codex"
    parent.cmdline.return_value = ["codex"]
    monkeypatch.setattr(psutil.Process, "parents", lambda _: [parent])
    assert CodexHarness().detect(env) == (
        None
        if address is None
        else DeliveryTarget("codex", address, "Codex", process=owner)
    )
    assert codex_ready.call_count == (1 if address is not None else 0)


@pytest.mark.parametrize(
    "args",
    [
        ["codex", "app-server", "--listen", "stdio://"],
        ["codex", "--no-daemon"],
    ],
)
def test_codex_refuses_embedded_process(
    args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import psutil

    parent = Mock()
    parent.name.return_value = "codex"
    parent.cmdline.return_value = args
    monkeypatch.setattr(psutil.Process, "parents", lambda _: [parent])
    with pytest.raises(PairInputError, match="shared daemon"):
        CodexHarness().detect({"CODEX_SESSION_ID": "root"})


def test_no_inbox_and_no_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    import psutil

    with pytest.raises(PairInputError, match="No supported inbox"):
        detect_target({}, None)
    monkeypatch.setattr(psutil.Process, "parents", lambda _: [])
    with pytest.raises(PairInputError, match="native Codex session"):
        detect_target({"CODEX_THREAD_ID": "thread"}, None)


def test_explicit_pid_keeps_recipient_and_skips_ancestor_detection(
    monkeypatch: pytest.MonkeyPatch, owner: ProcessHandle, codex_ready: Mock
) -> None:
    import psutil

    monkeypatch.setattr(
        psutil.Process,
        "parents",
        Mock(side_effect=AssertionError("Explicit PID must bypass discovery")),
    )
    _, target = detect_target(
        {"CODEX_THREAD_ID": "thread"}, "codex", pid=owner.pid
    )
    assert target == DeliveryTarget("codex", "thread", "Codex", owner)
    codex_ready.assert_called_once()


@pytest.mark.parametrize("pid", [0, -1])
def test_explicit_pid_must_be_positive(pid: int) -> None:
    with pytest.raises(PairInputError, match="positive process ID"):
        detect_target({"CODEX_THREAD_ID": "thread"}, "codex", pid=pid)


def test_explicit_pid_must_be_running(
    monkeypatch: pytest.MonkeyPatch, owner: ProcessHandle
) -> None:
    monkeypatch.setattr(ProcessHandle, "alive", lambda _: False)
    with pytest.raises(PairInputError, match="not running"):
        detect_target({"CODEX_THREAD_ID": "thread"}, "codex", pid=owner.pid)


def test_explicit_pid_inspection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import psutil

    monkeypatch.setattr(
        ProcessHandle, "capture", Mock(side_effect=psutil.NoSuchProcess(123))
    )
    with pytest.raises(PairInputError, match="Could not inspect"):
        detect_target({"CODEX_THREAD_ID": "thread"}, "codex", pid=123)


@pytest.mark.parametrize(
    ("status", "code", "ok"),
    [("running", 0, True), ("stopped", 0, False), ("running", 1, False)],
)
@pytest.mark.parametrize(
    ("platform", "executable"), [("linux", "codex"), ("win32", "codex.exe")]
)
def test_daemon_probe(
    status: str,
    code: int,
    ok: bool,
    platform: str,
    executable: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    run = Mock(
        return_value=subprocess.CompletedProcess(
            [], code, json.dumps({"status": status}).encode()
        )
    )
    monkeypatch.setattr(subprocess, "run", run)
    if ok:
        CodexHarness().check()
    else:
        with pytest.raises(PairInputError, match="daemon is not running"):
            CodexHarness().check()
    assert run.call_args_list[0].args[0] == [
        executable,
        "app-server",
        "daemon",
        "version",
    ]
    if ok:
        assert run.call_args_list[1].args[0] == [executable, "queue", "--help"]


@pytest.mark.parametrize("stdout", [b"bad", b"[]", b"null"])
def test_malformed_daemon_probe(
    stdout: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, stdout)),
    )
    with pytest.raises(PairInputError):
        CodexHarness().check()


@pytest.mark.parametrize(
    ("platform", "executable"), [("linux", "codex"), ("win32", "codex.exe")]
)
def test_codex_send_preserves_message(
    platform: str, executable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    run = Mock(return_value=subprocess.CompletedProcess([], 0, b"queued"))
    monkeypatch.setattr(subprocess, "run", run)
    message = 'line 1\n"quotes"; $(must not execute)'
    CodexHarness().open_inbox(DeliveryTarget("codex", "thread", "Codex")).send(
        message
    )
    assert run.call_args.args[0] == [
        executable,
        "queue",
        "--thread",
        "thread",
        "--message",
        message,
    ]
    assert "shell" not in run.call_args.kwargs


@pytest.mark.parametrize(
    "failure", [OSError("secret"), subprocess.TimeoutExpired("secret", 15)]
)
def test_codex_send_failure_does_not_leak(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=failure))
    with pytest.raises(PairError, match="Could not deliver") as error:
        CodexHarness().open_inbox(
            DeliveryTarget("codex", "thread", "Codex")
        ).send("message")
    assert "secret" not in str(error.value)


def test_process_identity_guards_pid_reuse(owner: ProcessHandle) -> None:
    assert owner.alive()
    reused = ProcessHandle(owner.pid, owner.started - 1)
    assert not reused.alive()
    reused.stop()
    assert owner.alive()
    assert (
        not CodexHarness()
        .open_inbox(DeliveryTarget("codex", "thread", "Codex"))
        .alive()
    )


def test_process_stop() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"]
    )
    try:
        handle = ProcessHandle.capture(process.pid)
        assert handle.alive()
        handle.stop()
        assert not handle.alive()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def record(owner: ProcessHandle, conversation: str = "thread") -> Connection:
    return Connection(
        1,
        connection_identity("s_one", "codex", conversation),
        "s_one",
        "codex",
        owner.pid,
        owner.started,
        owner.pid,
        owner.started,
        1.0,
    )


def test_connection_roundtrip_and_replacement(
    tmp_path: Path, owner: ProcessHandle
) -> None:
    store = ConnectionStore(tmp_path)
    old = record(owner)
    with store.locked(old.identity):
        store.save(old)
    assert store.load(old.identity) == old
    assert store.select("s_one", kind="codex", conversation="thread") == old
    replacement = record(ProcessHandle(owner.pid, owner.started + 1))
    store.save(replacement)
    store.remove(old)
    assert store.load(old.identity) == replacement
    assert set(json.loads(store.path(old.identity).read_bytes())) == {
        "version",
        "identity",
        "notebook",
        "harness_kind",
        "harness_pid",
        "harness_start",
        "forwarder_pid",
        "forwarder_start",
        "created_at",
    }
    if os.name == "posix":
        assert store.path(old.identity).stat().st_mode & 0o777 == 0o600
    store.remove(replacement)
    assert store.load(old.identity) is None


def test_connection_rejects_ambiguous_and_corrupt(
    tmp_path: Path, owner: ProcessHandle
) -> None:
    store = ConnectionStore(tmp_path)
    first = record(owner)
    store.save(first)
    store.save(record(owner, "other"))
    with pytest.raises(PairInputError, match="Several"):
        store.select("s_one", kind="unknown", conversation=None)
    store.path(first.identity).write_text("{}")
    with pytest.raises(PairInputError, match="Invalid Pair connection"):
        store.load(first.identity)
    with pytest.raises(PairInputError, match="Invalid Pair attachment"):
        store.path("../escape")


def test_corrupt_connection_recovery_never_signals(
    tmp_path: Path, owner: ProcessHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ConnectionStore(tmp_path)
    current = record(owner)
    store.path(current.identity).write_text('{"forwarder_pid": 123}')
    stop = Mock(side_effect=AssertionError("No valid process ownership"))
    monkeypatch.setattr(ProcessHandle, "stop", stop)
    with store.locked(current.identity):
        store.stop(current.identity)
        store.save(current)
    assert store.load(current.identity) == current
    stop.assert_not_called()


def test_selection_skips_unrelated_corruption(
    tmp_path: Path, owner: ProcessHandle
) -> None:
    store = ConnectionStore(tmp_path)
    current = record(owner)
    store.save(current)
    store.path(connection_identity("other", "codex", "bad")).write_text("{}")
    assert store.select("s_one", kind="unknown", conversation=None) == current


def test_connection_io_error_does_not_remove_record(
    tmp_path: Path, owner: ProcessHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ConnectionStore(tmp_path)
    current = record(owner)
    store.save(current)
    monkeypatch.setattr(Path, "read_bytes", Mock(side_effect=PermissionError))
    with (
        pytest.raises(PairInputError, match="Could not read"),
        store.locked(current.identity),
    ):
        store.stop(current.identity)
    assert store.path(current.identity).exists()


def test_stop_validated_zombie_does_not_wait(
    owner: ProcessHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psutil

    zombie = Mock()
    zombie.create_time.return_value = owner.started
    zombie.is_running.return_value = True
    zombie.status.return_value = psutil.STATUS_ZOMBIE
    monkeypatch.setattr(psutil, "Process", Mock(return_value=zombie))
    owner.stop()
    zombie.terminate.assert_not_called()
    zombie.wait.assert_not_called()


def test_stop_process_that_becomes_a_zombie(
    owner: ProcessHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psutil

    process = Mock()
    process.create_time.return_value = owner.started
    process.is_running.return_value = True
    process.status.side_effect = [psutil.STATUS_RUNNING, psutil.STATUS_ZOMBIE]
    process.wait.side_effect = psutil.TimeoutExpired(5)
    monkeypatch.setattr(psutil, "Process", Mock(return_value=process))
    owner.stop()
    process.terminate.assert_called_once()
    process.kill.assert_not_called()


PAYLOADS: list[object] = [
    {
        "type": "cell-output",
        "code": "1/0",
        "output": {"traceback": "full\ntraceback"},
    },
    {"lens": [1, 2]},
    "plain text",
    [1, "two"],
    42,
    1.5,
    True,
    None,
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_small_payloads(payload: object) -> None:
    files = AgentMessageFiles()
    message = inbox_message(
        payload, notebook="s_one", budget=8192, files=files
    )
    body = message.split("\n", 1)[1]
    assert (body if isinstance(payload, str) else json.loads(body)) == payload
    assert files.directory is None


@pytest.mark.parametrize("payload", PAYLOADS)
def test_full_json_dump_roundtrip(payload: object, tmp_path: Path) -> None:
    files = AgentMessageFiles()
    files.directory = tmp_path
    path = files.write(payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert path.is_absolute()
    assert files.write(payload) != path
    assert json.loads(path.read_text(encoding="utf-8")) == payload


@pytest.mark.parametrize(
    "payload",
    [
        "😀é" * 10000,
        {"traceback": "line\n" * 10000},
        ["long" * 10000],
        {"lens": "x" * 10000},
    ],
)
def test_oversized_dump_retained(payload: object, tmp_path: Path) -> None:
    files = AgentMessageFiles()
    files.directory = tmp_path
    message = inbox_message(payload, notebook="s_one", budget=512, files=files)
    assert len(message.encode("utf-8")) <= 512
    reference = Path(
        message.rsplit("Complete JSON agent message: ", 1)[1][:-1]
    )
    del files
    assert json.loads(reference.read_text(encoding="utf-8")) == payload


def test_dump_failure_does_not_send_broken_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tempfile, "mkdtemp", Mock(side_effect=OSError("disk full"))
    )
    with pytest.raises(PairError, match="No shortened message was sent"):
        inbox_message(
            "x" * 20000,
            notebook="s_one",
            budget=512,
            files=AgentMessageFiles(),
        )


def test_cleanup_only_owned_aged_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    files = AgentMessageFiles()
    path = files.write({"full": "content"})
    assert files.directory is not None
    unowned = files.directory / "keep.txt"
    unowned.write_text("keep")
    old = files.write("old")
    os.utime(old, (1, 1))
    AgentMessageFiles.cleanup(now=100000)
    assert not old.exists()
    assert path.exists()
    assert unowned.exists()


def test_cleanup_removed_directory_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    files = AgentMessageFiles()
    old = files.write("old")
    directory = old.parent
    os.utime(old, (1, 1))
    os.utime(directory, (1, 1))
    AgentMessageFiles.cleanup(now=100000)
    assert not directory.exists()
    new = files.write("new")
    assert new.parent != directory
    assert json.loads(new.read_text()) == "new"
    if os.name == "posix":
        assert new.stat().st_mode & 0o777 == 0o600


def test_replaced_payload_directory_is_not_followed(tmp_path: Path) -> None:
    files = AgentMessageFiles()
    original = files.write("old")
    directory = original.parent
    original.unlink()
    directory.rmdir()
    try:
        directory.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    try:
        with pytest.raises(PairError, match="No shortened message"):
            files.write("must not reach the replacement")
        assert list(tmp_path.iterdir()) == []
    finally:
        directory.unlink()


def test_nul_and_surrogate_text() -> None:
    message = inbox_message(
        "null\0\ud800", notebook="s", budget=512, files=AgentMessageFiles()
    )
    assert "\0" not in message
    assert "\\u0000" in message
    message.encode("utf-8")


def test_windows_uses_native_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, b"queued"))
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys, "platform", "win32")
    text = 'unicode 😀 & | "quotes" %PATH%'
    CodexHarness().open_inbox(DeliveryTarget("codex", "thread", "Codex")).send(
        text
    )
    assert run.call_args.args[0] == [
        "codex.exe",
        "queue",
        "--thread",
        "thread",
        "--message",
        text,
    ]


def test_missing_queue_support(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, b'{"status":"running"}'),
            subprocess.CompletedProcess([], 1, b"unsupported"),
        ]
    )
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PairInputError, match="queue support"):
        CodexHarness().check()


def test_windows_reference_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import PureWindowsPath

    files = AgentMessageFiles()
    path = PureWindowsPath("C:/Users/Name With Spaces/Temp/😀/handoff.json")
    monkeypatch.setattr(files, "write", Mock(return_value=path))
    message = inbox_message("😀" * 1000, notebook="s", budget=512, files=files)
    assert str(path) in message
    assert len(message.encode("utf-8")) <= 512


def test_windows_lock_releases_on_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    locking = Mock()
    monkeypatch.setitem(
        sys.modules,
        "msvcrt",
        SimpleNamespace(locking=locking, LK_NBLCK=1, LK_UNLCK=2),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    store = ConnectionStore(tmp_path)
    with (
        pytest.raises(RuntimeError),
        store.locked(connection_identity("s", "codex", "thread")),
    ):
        raise RuntimeError("release the lock")
    assert [call.args[1:] for call in locking.call_args_list] == [
        (1, 1),
        (2, 1),
    ]


def test_registry_nested_refusal_and_explicit_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._cli.pair import harnesses

    codex = Mock(kind="codex")
    codex.detect.return_value = DeliveryTarget("codex", "thread", "Codex")
    other = Mock(kind="other")
    other.detect.return_value = DeliveryTarget("other", "inbox", "Other")
    monkeypatch.setattr(
        harnesses, "registered_harnesses", lambda: [codex, other]
    )
    with pytest.raises(PairInputError, match="Nested harnesses"):
        detect_target({}, None)
    assert detect_target({}, "codex") == (codex, codex.detect.return_value)


def test_identity_uses_registered_adapters_and_refuses_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._cli.pair import harnesses

    codex = Mock(kind="codex")
    other = Mock(kind="other")
    codex.identity.return_value = None
    other.identity.return_value = "other-thread"
    monkeypatch.setattr(
        harnesses, "registered_harnesses", lambda: [codex, other]
    )
    assert harnesses.environment_identity({}) == ("other", "other-thread")
    codex.identity.return_value = "codex-thread"
    with pytest.raises(PairInputError, match="Nested harnesses"):
        harnesses.environment_identity({})
    assert harnesses.environment_identity({}, "codex") == (
        "codex",
        "codex-thread",
    )
    other.identity.side_effect = PairInputError("Unresolved conversation")
    with pytest.raises(PairInputError, match="Unresolved conversation"):
        harnesses.environment_identity({})
    codex.identity.return_value = None
    with pytest.raises(PairInputError, match="No codex conversation"):
        harnesses.environment_identity({}, "codex")


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"CLAUDE_PID": "123"}, "inbox socket"),
        ({"CLAUDE_CODE_MESSAGING_SOCKET": ""}, "inbox socket"),
        ({"CLAUDE_CODE_MESSAGING_TOKEN": "private-token"}, "inbox socket"),
        ({"CODEX_SESSION_ID": ""}, "conversation ID"),
        ({"CODEX_THREAD_ID": ""}, "conversation ID"),
    ],
)
def test_unresolved_native_context_cannot_detach_another_conversation(
    env: dict[str, str],
    message: str,
    tmp_path: Path,
    owner: ProcessHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from click.testing import CliRunner

    from marimo._cli.pair import commands

    store = ConnectionStore(tmp_path)
    other = record(owner, "another-conversation")
    store.save(other)
    monkeypatch.setattr(commands, "ConnectionStore", lambda: store)
    stop = Mock(
        side_effect=AssertionError("Unresolved identity cannot stop a process")
    )
    monkeypatch.setattr(ProcessHandle, "stop", stop)
    with patch.dict(os.environ, env, clear=True):
        result = CliRunner().invoke(commands.detach, ["--notebook", "s_one"])
    assert result.exit_code == 1
    assert message in result.output
    assert "private-token" not in result.output
    assert store.load(other.identity) == other
    stop.assert_not_called()


def test_explicit_harness_ignores_unresolved_inherited_harness() -> None:
    from marimo._cli.pair.harnesses import environment_identity

    assert environment_identity(
        {"CLAUDE_PID": "123", "CODEX_SESSION_ID": "thread-one"}, "codex"
    ) == ("codex", "thread-one")
    assert environment_identity(
        {
            "CODEX_THREAD_ID": "",
            "CLAUDE_CODE_MESSAGING_SOCKET": "/native/inbox",
        },
        "claude",
    ) == ("claude", "/native/inbox")
    assert ClaudeHarness().identity({}) is None
    assert CodexHarness().detect({}) is None


def test_pair_lock_rejects_symlink_without_modifying_target(
    tmp_path: Path,
) -> None:
    store = ConnectionStore(tmp_path / "connections")
    store.root.mkdir()
    target = tmp_path / "target"
    target.write_text("unchanged")
    identity = connection_identity("notebook", "codex", "thread")
    try:
        store.path(identity).with_suffix(".lock").symlink_to(target)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(OSError, match="symlink"), store.locked(identity):
        pytest.fail("The lock must reject symlinks")
    assert target.read_text() == "unchanged"


@pytest.mark.parametrize(
    "message", ["division by zero", "division by zero" * 1000]
)
def test_delivery_does_not_add_error_instructions(
    message: str, tmp_path: Path
) -> None:
    payload = {
        "type": "cell-output",
        "cell_id": "vblA",
        "code": "average([])",
        "output": {"type": "error", "message": message},
    }
    files = AgentMessageFiles()
    files.directory = tmp_path
    text = inbox_message(payload, notebook="s_one", budget=512, files=files)
    assert (
        text.split("\n", 1)[0] == "Agent message from marimo (notebook s_one)."
    )
    assert "Fix reported notebook errors" not in text
    assert len(text.encode("utf-8")) <= 512
    if "Complete JSON agent message: " in text:
        path = Path(text.rsplit("Complete JSON agent message: ", 1)[1][:-1])
        assert json.loads(path.read_text(encoding="utf-8")) == payload
    else:
        assert json.loads(text.split("\n", 1)[1]) == payload
