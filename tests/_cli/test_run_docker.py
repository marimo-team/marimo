# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._cli.errors import MarimoCLIRuntimeError
from marimo._cli.run_docker import (
    prompt_run_in_docker_container,
    run_in_docker,
)
from marimo._config.settings import GLOBAL_SETTINGS

if TYPE_CHECKING:
    from collections.abc import Callable

URL = "https://example.com/nb.py"


def _fail_on(subcommand: str, error: Exception) -> Callable[..., MagicMock]:
    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        if cmd[1] == subcommand:
            raise error
        return MagicMock(stdout="")

    return fake_run


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("podman"),
        PermissionError("permission denied"),
        subprocess.CalledProcessError(1, "--version"),
    ],
)
def test_engine_not_installed(error: Exception) -> None:
    with (
        patch(
            "marimo._cli.run_docker.subprocess.run",
            side_effect=_fail_on("--version", error),
        ),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        run_in_docker(URL, "edit", engine="podman", port=None)

    assert excinfo.value.message == (
        "podman is not installed. Please install podman and try again, "
        "or choose another engine with --container-engine."
    )


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "info"),
        subprocess.TimeoutExpired("info", 10),
        PermissionError("permission denied"),
    ],
)
def test_engine_not_running(error: Exception) -> None:
    with (
        patch(
            "marimo._cli.run_docker.subprocess.run",
            side_effect=_fail_on("info", error),
        ),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        run_in_docker(URL, "edit", engine="podman", port=None)

    assert excinfo.value.message == (
        "podman is not running or not responding. Please start podman and "
        "try again, or choose another engine with --container-engine."
    )


def test_prompt_shows_engine(monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert prompt_run_in_docker_container(URL, engine="podman")

    message = confirm.call_args.args[0]
    assert "Container engine: podman (change with --container-engine)" in (
        message
    )
    assert "secure container" in message


def test_run_in_docker_uses_given_engine(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Any engine with docker-style commands works, not just a fixed list.
    engine = "nerdctl"

    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        stdout = "abc123\n" if cmd[1] == "run" else ""
        return MagicMock(stdout=stdout)

    with (
        patch(
            "marimo._cli.run_docker.subprocess.run", side_effect=fake_run
        ) as run,
        patch("marimo._cli.run_docker.subprocess.Popen") as popen,
    ):
        popen.return_value.__enter__.return_value.stdout = []
        run_in_docker(URL, "edit", engine=engine, port=None)

    commands = [c.args[0] for c in run.call_args_list]
    assert [cmd[:2] for cmd in commands] == [
        [engine, "--version"],
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


def test_run_failure_shows_engine_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = subprocess.CalledProcessError(
        125, "run", stderr="Error: image pull failed\n"
    )
    with (
        patch(
            "marimo._cli.run_docker.subprocess.run",
            side_effect=_fail_on("run", error),
        ),
        pytest.raises(MarimoCLIRuntimeError) as excinfo,
    ):
        run_in_docker(URL, "edit", engine="podman", port=None)

    assert excinfo.value.message.startswith(
        "Failed to start podman container: "
    )
    assert excinfo.value.message.endswith("\nError: image pull failed")
    # No container was started, so there is nothing to stop.
    assert "Stopping" not in capsys.readouterr().out


def test_port_in_use_suggests_engine_stop_command() -> None:
    def fake_run(cmd: list[str], **_: object) -> MagicMock:
        if cmd[1] == "ps":
            return MagicMock(stdout="abc123\t0.0.0.0:8080->8080/tcp\n")
        return MagicMock(stdout="")

    with (
        patch("marimo._cli.run_docker.subprocess.run", side_effect=fake_run),
        pytest.raises(MarimoCLIRuntimeError, match="podman stop abc123"),
    ):
        run_in_docker(URL, "edit", engine="podman", port=8080)
