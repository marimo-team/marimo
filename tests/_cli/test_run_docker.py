# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._cli.errors import MarimoCLIRuntimeError
from marimo._cli.run_docker import (
    CONTAINER_ENGINES,
    _find_container_engine,
    prompt_run_in_docker_container,
    run_in_docker,
)
from marimo._config.settings import GLOBAL_SETTINGS

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _engines(
    installed: tuple[str, ...], running: tuple[str, ...] | None = None
) -> Iterator[None]:
    """Fake which engines are installed, and which of those are running.

    With `running=None`, the real running check is used.
    """
    with patch(
        "marimo._cli.run_docker.DependencyManager.which",
        lambda engine: engine in installed,
    ):
        if running is None:
            yield
            return
        with patch(
            "marimo._cli.run_docker._check_engine_running",
            lambda engine: engine in running,
        ):
            yield


@pytest.mark.parametrize("engine", CONTAINER_ENGINES)
def test_find_container_engine_skips_not_running(engine: str) -> None:
    with _engines(installed=CONTAINER_ENGINES, running=(engine,)):
        assert _find_container_engine() == engine


@pytest.mark.parametrize("engine", CONTAINER_ENGINES)
def test_find_container_engine_skips_not_installed(engine: str) -> None:
    with _engines(installed=(engine,), running=CONTAINER_ENGINES):
        assert _find_container_engine() == engine


@pytest.mark.parametrize("index", range(len(CONTAINER_ENGINES)))
def test_find_container_engine_prefers_earlier_engine(index: int) -> None:
    usable = CONTAINER_ENGINES[index:]
    with _engines(installed=usable, running=usable):
        assert _find_container_engine() == CONTAINER_ENGINES[index]


def test_find_container_engine_none_installed() -> None:
    with (
        _engines(installed=()),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        _find_container_engine()

    assert excinfo.value.message == (
        "No usable container engine found:\n"
        + "".join(f"  {engine}: not found\n" for engine in CONTAINER_ENGINES)
        + "Please install or start one of them and try again."
    )


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "info"),
        subprocess.TimeoutExpired("info", 10),
        PermissionError("permission denied"),
    ],
)
def test_find_container_engine_none_running(error: Exception) -> None:
    def fail(*_: object, **__: object) -> None:
        raise error

    with (
        _engines(installed=CONTAINER_ENGINES),
        patch("marimo._cli.run_docker.subprocess.run", side_effect=fail),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        _find_container_engine()

    assert excinfo.value.message == (
        "No usable container engine found:\n"
        + "".join(
            f"  {engine}: installed but not running or not responding\n"
            for engine in CONTAINER_ENGINES
        )
        + "Please install or start one of them and try again."
    )


def test_prompt_lists_supported_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(GLOBAL_SETTINGS, "IN_SECURE_ENVIRONMENT", False)
    monkeypatch.setattr(GLOBAL_SETTINGS, "MANAGE_SCRIPT_METADATA", False)
    monkeypatch.setattr(GLOBAL_SETTINGS, "YES", False)
    with (
        patch("marimo._cli.run_docker.sys") as terminal,
        patch(
            "marimo._cli.run_docker.click.confirm", return_value=True
        ) as confirm,
    ):
        terminal.stdin.isatty.return_value = True
        assert prompt_run_in_docker_container("https://example.com/nb.py")

    message = confirm.call_args.args[0]
    assert ", ".join(CONTAINER_ENGINES) in message
    assert "secure container" in message


@pytest.mark.parametrize("engine", CONTAINER_ENGINES)
def test_run_in_docker_uses_found_engine(
    engine: str, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        stdout = "abc123\n" if cmd[1] == "run" else ""
        return MagicMock(stdout=stdout)

    with (
        _engines(installed=(engine,)),
        patch(
            "marimo._cli.run_docker.subprocess.run", side_effect=fake_run
        ) as run,
        patch("marimo._cli.run_docker.subprocess.Popen") as popen,
    ):
        popen.return_value.__enter__.return_value.stdout = []
        run_in_docker("https://example.com/nb.py", "edit", port=None)

    commands = [c.args[0] for c in run.call_args_list]
    assert [cmd[:2] for cmd in commands] == [
        [engine, "info"],
        [engine, "ps"],
        [engine, "run"],
        [engine, "stop"],
    ]
    assert commands[-1] == [engine, "stop", "abc123"]
    assert popen.call_args.args[0] == [engine, "logs", "-f", "abc123"]
    assert "Container stopped and removed successfully" in (
        capsys.readouterr().out
    )


@pytest.mark.parametrize("engine", CONTAINER_ENGINES)
def test_run_failure_shows_engine_stderr(
    engine: str, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        if cmd[1] == "run":
            raise subprocess.CalledProcessError(
                125, cmd, stderr="Error: image pull failed\n"
            )
        return MagicMock(stdout="")

    with (
        _engines(installed=(engine,)),
        patch("marimo._cli.run_docker.subprocess.run", side_effect=fake_run),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        run_in_docker("https://example.com/nb.py", "edit", port=None)

    assert excinfo.value.message.startswith(
        f"Failed to start {engine} container: "
    )
    assert excinfo.value.message.endswith("\nError: image pull failed")
    # No container was started, so there is nothing to stop.
    assert "Stopping" not in capsys.readouterr().out


@pytest.mark.parametrize("engine", CONTAINER_ENGINES)
def test_port_in_use_suggests_engine_stop_command(engine: str) -> None:
    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        if cmd[1] == "ps":
            return MagicMock(stdout="abc123\t0.0.0.0:8080->8080/tcp\n")
        return MagicMock(stdout="")

    with (
        _engines(installed=(engine,)),
        patch("marimo._cli.run_docker.subprocess.run", side_effect=fake_run),
        pytest.raises(MarimoCLIRuntimeError, match=f"{engine} stop abc123"),
    ):
        run_in_docker("https://example.com/nb.py", "edit", port=8080)
