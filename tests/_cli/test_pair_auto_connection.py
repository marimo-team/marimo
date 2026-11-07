# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import msgspec
import pytest
from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands, forwarder
from marimo._cli.pair.client import (
    ExecutionResult,
    InboxConnectionError,
    PairInputError,
)
from marimo._cli.pair.connection import (
    Connection,
    ConnectionStore,
    connection_identity,
)
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.forwarder import ensure_connection
from marimo._cli.pair.harnesses import try_detect_target
from marimo._cli.pair.target import ExecutionTarget
from tests._cli.test_pair_delivery import record as connection_record

if TYPE_CHECKING:
    from pathlib import Path


RETRY_NOTICE = (
    "Notebook messaging unavailable. Retry once. "
    "If it fails, continue without messaging.\n"
)


@dataclass
class AutoConnectionSetup:
    owner: ProcessHandle
    delivery: DeliveryTarget
    selected: ExecutionTarget
    store: ConnectionStore
    adapter: Mock
    start: Mock
    stop: Mock
    identity: str


@pytest.fixture
def setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AutoConnectionSetup:
    owner = ProcessHandle.capture(os.getpid())
    delivery = DeliveryTarget("codex", "conversation", "Codex", owner)
    selected = ExecutionTarget(
        "http://localhost:2718", "nb-one", "private-token", "nb-one"
    )
    store = ConnectionStore(tmp_path / "connections-v1")
    adapter = Mock()
    adapter.detect.return_value = delivery
    monkeypatch.setattr(
        forwarder, "try_detect_target", lambda _: (adapter, delivery)
    )
    monkeypatch.setattr(
        forwarder,
        "detect_target",
        lambda *_args, **_kwargs: (adapter, delivery),
    )
    monkeypatch.setattr(forwarder, "resolve_target", lambda **_: selected)
    monkeypatch.setattr(
        forwarder, "resolve_inbox_target", lambda selected: selected
    )
    stop = Mock()
    monkeypatch.setattr(store, "stop", stop)

    def start(
        config: forwarder.ForwarderConfig, target_store: ConnectionStore
    ) -> Connection:
        process = config.target.process
        assert process is not None
        record = msgspec.structs.replace(
            connection_record(process),
            identity=config.identity,
            notebook=config.notebook,
            harness_kind=config.target.kind,
            forwarder_pid=owner.pid,
            forwarder_start=owner.started,
        )
        target_store.save(record)
        return record

    start_mock = Mock(side_effect=start)
    monkeypatch.setattr(forwarder, "start_forwarder", start_mock)
    return AutoConnectionSetup(
        owner=owner,
        delivery=delivery,
        selected=selected,
        store=store,
        adapter=adapter,
        start=start_mock,
        stop=stop,
        identity=connection_identity("nb-one", "codex", "conversation"),
    )


def test_unsupported_shell_and_old_opencode_are_silent() -> None:
    assert try_detect_target({}) is None
    assert try_detect_target({"OPENCODE": "1"}) is None


def test_unsupported_harness_does_not_create_state(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(forwarder, "try_detect_target", lambda _: None)
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True) is None
    )
    assert not setup.store.root.exists()
    setup.start.assert_not_called()


def test_attempt_precedes_readiness_and_is_private(
    setup: AutoConnectionSetup,
) -> None:
    def check(*_args: object, **_kwargs: object) -> DeliveryTarget:
        assert setup.store.attempted(setup.identity, setup.owner)
        return setup.delivery

    setup.adapter.detect.side_effect = check
    first = ensure_connection(setup.selected, setup.store, automatic=True)
    ensure_connection(setup.selected, setup.store, automatic=True)
    assert first is not None
    setup.start.assert_called_once()
    setup.adapter.detect.assert_called_once()
    path = setup.store.root / "attempts" / f"{setup.identity}.json"
    content = json.loads(path.read_text())
    assert set(content) == {"harness_pid", "harness_start", "attempted_at"}
    assert content["harness_pid"] == setup.owner.pid
    assert "private-token" not in path.read_text()
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("stage", ["readiness", "startup"])
def test_failure_is_not_retried_until_explicit_connect(
    setup: AutoConnectionSetup, stage: str
) -> None:
    failing = setup.adapter.detect if stage == "readiness" else setup.start
    success = failing.side_effect
    failing.side_effect = PairInputError("Inbox unavailable")
    error = PairInputError if stage == "readiness" else InboxConnectionError
    with pytest.raises(error, match="Inbox unavailable"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    calls = failing.call_count
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True) is None
    )
    assert failing.call_count == calls
    failing.side_effect = success
    result = ensure_connection(setup.selected, setup.store)
    assert result is not None
    assert failing.call_count == calls + 1


def test_existing_owned_forwarder_is_reused(
    setup: AutoConnectionSetup,
) -> None:
    previous = msgspec.structs.replace(
        connection_record(setup.owner),
        identity=setup.identity,
        notebook="nb-one",
    )
    setup.store.save(previous)
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True)
        == previous
    )
    setup.start.assert_not_called()
    setup.adapter.detect.assert_not_called()
    setup.stop.assert_not_called()


def test_pending_marker_survives_interruption(
    setup: AutoConnectionSetup,
) -> None:
    setup.store.mark_attempted(setup.identity, setup.owner)
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True) is None
    )
    setup.adapter.detect.assert_not_called()
    setup.start.assert_not_called()


def test_process_start_time_scopes_the_attempt(
    setup: AutoConnectionSetup,
) -> None:
    old_owner = replace(setup.owner, started=setup.owner.started - 1)
    setup.store.mark_attempted(setup.identity, old_owner)
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True)
        is not None
    )
    setup.start.assert_called_once()


def test_concurrent_calls_start_one_forwarder(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    barrier = threading.Barrier(2)

    def detect(_env: object) -> tuple[Mock, DeliveryTarget]:
        barrier.wait(timeout=5)
        return setup.adapter, setup.delivery

    monkeypatch.setattr(forwarder, "try_detect_target", detect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: ensure_connection(
                    setup.selected, setup.store, automatic=True
                ),
                range(2),
            )
        )
    assert sum(result is not None for result in results) == 1
    setup.start.assert_called_once()
    setup.adapter.detect.assert_called_once()


def test_failed_marker_write_does_not_start_or_stop(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object) -> None:
        raise PairInputError("State is not writable")

    monkeypatch.setattr(setup.store, "mark_attempted", fail)
    with pytest.raises(PairInputError, match="not writable"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    setup.adapter.detect.assert_not_called()
    setup.stop.assert_not_called()
    setup.start.assert_not_called()


def test_changed_conversation_does_not_replace_forwarder(
    setup: AutoConnectionSetup,
) -> None:
    setup.adapter.detect.return_value = replace(
        setup.delivery, address="other-conversation"
    )
    with pytest.raises(PairInputError, match="conversation changed"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    setup.stop.assert_not_called()
    setup.start.assert_not_called()


def test_nested_detection_does_not_attempt_a_connection(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    def nested(_env: object) -> None:
        raise PairInputError("Nested harnesses detected")

    monkeypatch.setattr(forwarder, "try_detect_target", nested)
    with pytest.raises(PairInputError, match="Nested harnesses"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    assert not setup.store.root.exists()
    setup.start.assert_not_called()


@pytest.mark.parametrize(
    ("stage", "error", "notice"),
    [
        (
            "readiness",
            PairInputError("Run connect again with private-token"),
            "",
        ),
        (
            "startup",
            PairInputError("Run connect again with private-token"),
            RETRY_NOTICE,
        ),
        (
            "startup",
            "process-exited",
            RETRY_NOTICE,
        ),
        (
            "startup",
            "process-denied",
            RETRY_NOTICE,
        ),
    ],
    ids=["readiness", "startup", "process-exited", "process-denied"],
)
def test_cli_preserves_json_and_limits_retry_guidance(
    setup: AutoConnectionSetup,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    error: Exception | str,
    notice: str,
) -> None:
    import psutil

    if isinstance(error, str):
        error = (
            psutil.NoSuchProcess(123456789)
            if error == "process-exited"
            else psutil.AccessDenied(123456789)
        )
    monkeypatch.setattr(commands, "ConnectionStore", lambda: setup.store)
    monkeypatch.setattr(commands, "resolve_target", lambda **_: setup.selected)
    execute = Mock(return_value=ExecutionResult(True, None, "done\n", ""))
    monkeypatch.setattr(commands, "execute_code", execute)
    failing = setup.adapter.detect if stage == "readiness" else setup.start
    failing.side_effect = error
    runner = CliRunner()
    arguments = [
        "pair",
        "execute",
        "--session",
        "nb-one",
        "--code",
        "print('done')",
    ]
    first = runner.invoke(cli_main, arguments)
    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["success"] is True
    assert first.stderr == notice
    assert "private-token" not in first.output
    second = runner.invoke(cli_main, arguments)
    assert second.exit_code == 0
    assert second.stderr == ""
    assert json.loads(second.stdout)["stdout"] == "done\n"
    assert execute.call_count == 2
    assert failing.call_count == 1
    setup.adapter.detect.assert_called_once()


def test_other_live_owner_is_not_stopped(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ProcessHandle, "alive", lambda _: True)
    previous = msgspec.structs.replace(
        connection_record(setup.owner),
        identity=setup.identity,
        notebook="nb-one",
        harness_pid=setup.owner.pid + 1,
    )
    setup.store.save(previous)
    with pytest.raises(PairInputError, match="another harness process"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    setup.stop.assert_not_called()
    setup.start.assert_not_called()


@pytest.mark.parametrize(
    ("notebook", "conversation"),
    [("nb-other", "conversation"), ("nb-one", "other-conversation")],
)
def test_attempt_does_not_block_another_identity(
    setup: AutoConnectionSetup, notebook: str, conversation: str
) -> None:
    identity = connection_identity(notebook, "codex", conversation)
    setup.store.mark_attempted(identity, setup.owner)
    assert (
        ensure_connection(setup.selected, setup.store, automatic=True)
        is not None
    )
    setup.start.assert_called_once()


def test_identity_only_detection_defers_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._cli.pair.harnesses.claude import ClaudeHarness
    from marimo._cli.pair.harnesses.codex import CodexHarness

    owner = ProcessHandle.capture(os.getpid())
    for adapter, env in (
        (CodexHarness(), {"CODEX_SESSION_ID": "conversation"}),
        (ClaudeHarness(), {"CLAUDE_CODE_MESSAGING_SOCKET": "/missing/socket"}),
    ):
        check = Mock(side_effect=PairInputError("Not ready"))
        monkeypatch.setattr(adapter, "check", check)
        target = adapter.detect(env, process=owner, check_ready=False)
        assert target is not None
        assert target.process == owner
        check.assert_not_called()
        with pytest.raises(PairInputError, match="Not ready"):
            adapter.detect(env, process=owner)


def test_optional_detection_rejects_multiple_harnesses(
    setup: AutoConnectionSetup, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._cli.pair import harnesses

    codex = Mock()
    claude = Mock()
    codex.detect.return_value = setup.delivery
    claude.detect.return_value = replace(
        setup.delivery, kind="claude", address="socket"
    )
    monkeypatch.setattr(
        harnesses, "registered_harnesses", lambda: [codex, claude]
    )
    with pytest.raises(PairInputError, match="Nested harnesses"):
        harnesses.try_detect_target({})


def test_explicit_connect_recovers_a_malformed_connection(
    setup: AutoConnectionSetup,
) -> None:
    path = setup.store.path(setup.identity)
    path.parent.mkdir(parents=True)
    path.write_text("malformed")
    result = ensure_connection(setup.selected, setup.store)
    assert result is not None
    setup.stop.assert_called_once_with(setup.identity)
    assert setup.store.load(setup.identity) == result


@pytest.mark.parametrize("known_notebook", [False, True])
def test_connection_target_is_resolved_once(
    setup: AutoConnectionSetup,
    monkeypatch: pytest.MonkeyPatch,
    known_notebook: bool,
) -> None:
    selected = (
        setup.selected
        if known_notebook
        else replace(setup.selected, id="sess-one", notebook_id=None)
    )
    resolve = Mock(return_value=setup.selected)
    monkeypatch.setattr(forwarder, "resolve_target", resolve)
    assert ensure_connection(selected, setup.store, automatic=True) is not None
    assert resolve.call_count == (0 if known_notebook else 1)


def test_connection_resolution_cannot_change_notebooks(
    setup: AutoConnectionSetup,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = replace(setup.selected, id="nb-other", notebook_id="nb-other")
    monkeypatch.setattr(forwarder, "resolve_inbox_target", lambda _: other)
    with pytest.raises(PairInputError, match="notebook changed"):
        ensure_connection(setup.selected, setup.store, automatic=True)
    setup.start.assert_not_called()
    setup.stop.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [PairInputError("Nested harnesses detected"), OSError("Unavailable")],
)
def test_cli_skips_unidentified_inboxes_without_retry_guidance(
    setup: AutoConnectionSetup,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    monkeypatch.setattr(commands, "ConnectionStore", lambda: setup.store)
    monkeypatch.setattr(commands, "resolve_target", lambda **_: setup.selected)
    monkeypatch.setattr(
        commands,
        "execute_code",
        lambda **_: ExecutionResult(True, None, "done\n", ""),
    )
    monkeypatch.setattr(
        forwarder, "try_detect_target", Mock(side_effect=error)
    )
    result = CliRunner().invoke(
        cli_main, ["pair", "execute", "--session", "nb-one", "--code", "42"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["success"] is True
    assert result.stderr == ""
    setup.start.assert_not_called()


def test_explicit_connect_keeps_detailed_errors(
    setup: AutoConnectionSetup,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(commands, "ConnectionStore", lambda: setup.store)
    monkeypatch.setattr(commands, "resolve_target", lambda **_: setup.selected)
    setup.start.side_effect = PairInputError("Forwarder startup was refused")
    result = CliRunner().invoke(
        cli_main, ["pair", "connect", "--session", "nb-one"]
    )
    assert result.exit_code != 0
    assert "Forwarder startup was refused" in result.stderr
    assert "Retry once" not in result.stderr
