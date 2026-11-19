# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest

from marimo._cli.containers.apple import AppleContainerEngine
from marimo._cli.containers.docker import DockerEngine
from marimo._cli.containers.engine import (
    Cancelled,
    CleanupComplete,
    EngineFailure,
    LaunchRequest,
    PortMapping,
    StartFailure,
    WorkloadExit,
)
from marimo._cli.containers.finch import FinchEngine
from marimo._cli.containers.nerdctl import NerdctlEngine
from marimo._cli.containers.podman import PodmanEngine
from marimo._cli.containers.selection import resolve_engine
from marimo._cli.containers.source import prepare_notebook

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._cli.containers.engine import SessionResult

pytestmark = pytest.mark.timeout(90)
_IMAGE = "docker.io/library/alpine@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b"


@pytest.mark.parametrize(
    ("executable", "expected"),
    [
        ("docker", DockerEngine),
        ("podman", PodmanEngine),
        ("nerdctl", NerdctlEngine),
        ("path with spaces/finch", FinchEngine),
        ("path with spaces/custom-engine", DockerEngine),
    ],
)
def test_resolve_container_engine(
    executable: str,
    expected: type[DockerEngine | PodmanEngine | NerdctlEngine | FinchEngine],
) -> None:
    assert isinstance(resolve_engine(executable), expected)


@pytest.mark.parametrize(
    "executable", ["container", "/path with spaces/container"]
)
def test_resolve_apple_container_engine(executable: str) -> None:
    assert isinstance(resolve_engine(executable), AppleContainerEngine)


@pytest.fixture
def executable() -> str:
    configured = os.environ.get("MARIMO_TEST_CONTAINER_ENGINE")
    if configured is None:
        pytest.skip("Set MARIMO_TEST_CONTAINER_ENGINE to test a real engine.")
    return configured


def _run_engine(executable: str, *args: str) -> str:
    return subprocess.check_output([executable, *args], text=True, timeout=20)


def _exists(executable: str, container: str) -> bool:
    if Path(executable).name == "container":
        args = ("list", "--all", "--quiet")
    else:
        args = ("ps", "-aq", "--no-trunc")
    return container in _run_engine(executable, *args).splitlines()


@pytest.mark.parametrize("status", [0, 1, 7])
def test_container_retains_final_logs_and_workload_exit(
    executable: str, status: int
) -> None:
    session = resolve_engine(executable).start(
        LaunchRequest(
            _IMAGE,
            ("sh", "-c", f"echo 'Error: final-output' >&2; exit {status}"),
        )
    )
    assert not isinstance(session, StartFailure), session
    try:
        assert list(session.logs()) == ["Error: final-output\n"]
        assert session.exit_result() == WorkloadExit(status)
        assert session.close() == CleanupComplete("removed")
        assert session.close() == CleanupComplete("removed")
        assert session.exit_result() == WorkloadExit(status)
        assert not _exists(executable, session.identity.container)
    finally:
        assert isinstance(session.close(), CleanupComplete)


def test_container_close_stops_only_the_owned_session(
    executable: str,
) -> None:
    request = LaunchRequest(_IMAGE, ("sh", "-c", "echo ready; sleep 120"))
    engine = resolve_engine(executable)
    unrelated = engine.start(request)
    assert not isinstance(unrelated, StartFailure), unrelated
    try:
        session = engine.start(request)
        assert not isinstance(session, StartFailure), session
        logs = session.logs()
        try:
            assert next(logs) == "ready\n"
            assert session.close() == CleanupComplete("removed")
            assert session.exit_result() == Cancelled()
            assert not _exists(executable, session.identity.container)
            assert _exists(executable, unrelated.identity.container)
        finally:
            assert isinstance(session.close(), CleanupComplete)
    finally:
        assert isinstance(unrelated.close(), CleanupComplete)


def test_container_reports_external_removal_with_engine_outcome(
    executable: str,
) -> None:
    session = resolve_engine(executable).start(
        LaunchRequest(_IMAGE, ("sh", "-c", "echo ready; sleep 120"))
    )
    assert not isinstance(session, StartFailure), session
    logs = session.logs()
    replacement = False
    try:
        assert next(logs) == "ready\n"
        _run_engine(executable, "rm", "-f", session.identity.container)
        result = session.exit_result()
        if Path(executable).name == "container":
            assert isinstance(result, EngineFailure) or result in (
                WorkloadExit(137),
                WorkloadExit(143),
            )
        else:
            observed = subprocess.run(
                [executable, "wait", session.identity.container],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if observed.returncode == 0 and observed.stdout.strip() == "137":
                assert result == WorkloadExit(137)
            else:
                assert isinstance(result, EngineFailure)
        if Path(executable).name == "container":
            _run_engine(
                executable,
                "create",
                "--name",
                session.identity.container,
                _IMAGE,
                "true",
            )
            replacement = True
        assert session.close() == CleanupComplete("absent")
        assert session.close() == CleanupComplete("absent")
        if replacement:
            assert _exists(executable, session.identity.container)
    finally:
        if replacement and _exists(executable, session.identity.container):
            _run_engine(executable, "rm", "-f", session.identity.container)
        assert isinstance(session.close(), CleanupComplete)


def test_container_removes_resource_after_engine_start_fails(
    executable: str,
) -> None:
    result = resolve_engine(executable).start(
        LaunchRequest(_IMAGE, ("/missing-program",))
    )
    failure: SessionResult
    if isinstance(result, StartFailure):
        failure, cleanup = result.result, result.cleanup
    else:
        try:
            list(result.logs())
            failure = result.exit_result()
        finally:
            cleanup = result.close()
    assert isinstance(failure, EngineFailure)
    assert failure.stage == "start"
    assert "/missing-program" in failure.detail
    assert cleanup == CleanupComplete("removed")
    assert failure.container is not None
    assert not _exists(executable, failure.container)


@pytest.fixture(
    params=["", ", with spaces"], ids=["normal-home", "comma-home"]
)
def staging_home(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    with TemporaryDirectory(
        prefix=f".marimo-test{request.param}-", dir=Path.home()
    ) as home:
        monkeypatch.setattr(Path, "home", lambda: Path(home))
        yield


@pytest.mark.usefixtures("staging_home")
def test_container_can_replace_only_the_staged_notebook(
    executable: str, tmp_path: Path
) -> None:
    original = tmp_path / "local notebook.py"
    original.write_text("original source", encoding="utf-8")
    (tmp_path / "adjacent.txt").touch()
    with prepare_notebook(str(original)) as notebook:
        (mount,) = notebook.mounts
        staged = Path(mount.source)
        assert notebook.path is not None
        request = LaunchRequest(
            _IMAGE,
            (
                "sh",
                "-ec",
                'test ! -e adjacent.txt; echo updated > temporary; mv temporary "$1"; cat "$1"',
                "sh",
                notebook.path,
            ),
            working_directory=notebook.working_directory,
            mounts=notebook.mounts,
        )
        session = resolve_engine(executable).start(request)
        assert not isinstance(session, StartFailure), session
        try:
            assert list(session.logs()) == ["updated\n"]
            assert session.exit_result() == WorkloadExit(0)
        finally:
            assert session.close() == CleanupComplete("removed")
        assert (staged / original.name).read_text(
            encoding="utf-8"
        ) == "updated\n"
    assert not staged.exists()
    assert original.read_text(encoding="utf-8") == "original source"


def test_container_publishes_workload_port(executable: str) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        host_port = listener.getsockname()[1]

    request = LaunchRequest(
        _IMAGE,
        (
            "sh",
            "-ec",
            'printf "%s\\n" "$MESSAGE" > reply; exec nc -lk -p 8080 -e cat reply',
        ),
        environment=(("MESSAGE", "container response"),),
        working_directory="/tmp",
        ports=(PortMapping(host=host_port, container=8080),),
    )
    session = resolve_engine(executable).start(request)
    assert not isinstance(session, StartFailure), session
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with (
                    socket.create_connection(
                        ("127.0.0.1", host_port), timeout=1
                    ) as connection,
                    connection.makefile("rb") as response,
                ):
                    message = response.readline()
            except OSError:
                pass
            else:
                if message:
                    assert message == b"container response\n"
                    break
            time.sleep(0.1)
        else:
            pytest.fail(f"The workload did not listen on port {host_port}.")
    finally:
        assert session.close() == CleanupComplete("removed")
