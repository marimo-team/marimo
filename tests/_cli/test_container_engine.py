# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess

import pytest

from marimo._cli.containers.docker import DockerEngine
from marimo._cli.containers.engine import (
    Cancelled,
    CleanupComplete,
    EngineFailure,
    LaunchRequest,
    StartFailure,
    WorkloadExit,
)
from marimo._cli.containers.finch import FinchEngine
from marimo._cli.containers.nerdctl import NerdctlEngine
from marimo._cli.containers.podman import PodmanEngine
from marimo._cli.containers.selection import resolve_engine

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


@pytest.fixture
def executable() -> str:
    configured = os.environ.get("MARIMO_TEST_CONTAINER_ENGINE")
    if configured is None:
        pytest.skip("Set MARIMO_TEST_CONTAINER_ENGINE to test a real engine.")
    return configured


def _run_engine(executable: str, *args: str) -> str:
    return subprocess.check_output([executable, *args], text=True, timeout=20)


def _exists(executable: str, container: str) -> bool:
    return (
        container
        in _run_engine(executable, "ps", "-aq", "--no-trunc").splitlines()
    )


@pytest.mark.parametrize("status", [0, 7])
def test_container_retains_final_logs_and_workload_exit(
    executable: str, status: int
) -> None:
    session = resolve_engine(executable).start(
        LaunchRequest(
            _IMAGE, ("sh", "-c", f"echo final-output; exit {status}")
        )
    )
    assert not isinstance(session, StartFailure), session
    try:
        assert list(session.logs()) == ["final-output\n"]
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
            logs.close()
            assert isinstance(session.close(), CleanupComplete)
    finally:
        assert isinstance(unrelated.close(), CleanupComplete)


def test_container_reports_external_removal_with_engine_outcome(
    executable: str,
) -> None:
    session = resolve_engine(executable).start(
        LaunchRequest(_IMAGE, ("sleep", "120"))
    )
    assert not isinstance(session, StartFailure), session
    try:
        _run_engine(executable, "rm", "-f", session.identity.container)
        observed = subprocess.run(
            [executable, "wait", session.identity.container],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        result = session.exit_result()
        if observed.returncode == 0 and observed.stdout.strip() == "137":
            assert result == WorkloadExit(137)
        else:
            assert isinstance(result, EngineFailure)
        assert session.close() == CleanupComplete("absent")
        assert session.close() == CleanupComplete("absent")
    finally:
        assert isinstance(session.close(), CleanupComplete)


def test_container_removes_resource_after_engine_start_fails(
    executable: str,
) -> None:
    result = resolve_engine(executable).start(
        LaunchRequest(_IMAGE, ("/missing-program",))
    )
    if not isinstance(result, StartFailure):
        result.close()
        pytest.fail("The engine started an invalid workload.")
    assert isinstance(result.result, EngineFailure)
    assert result.result.stage == "start"
    assert "/missing-program" in result.result.detail
    assert result.cleanup == CleanupComplete("removed")
    assert result.result.container is not None
    assert not _exists(executable, result.result.container)
