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

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("MARIMO_TEST_CONTAINER_ENGINE") != "docker",
        reason="Set MARIMO_TEST_CONTAINER_ENGINE=docker to test real Docker.",
    ),
    pytest.mark.timeout(90),
]
_IMAGE = "alpine@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b"


def _docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, timeout=10)


def _exists(container: str) -> bool:
    return bool(_docker("ps", "-aq", "--filter", f"id={container}").strip())


@pytest.mark.parametrize("status", [0, 7])
def test_container_retains_final_logs_and_workload_exit(status: int) -> None:
    session = DockerEngine().start(
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
        assert not _exists(session.identity.container)
    finally:
        assert isinstance(session.close(), CleanupComplete)


def test_container_close_stops_only_the_owned_session() -> None:
    request = LaunchRequest(_IMAGE, ("sh", "-c", "echo ready; sleep 120"))
    engine = DockerEngine()
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
            assert not _exists(session.identity.container)
            assert _exists(unrelated.identity.container)
        finally:
            logs.close()
            assert isinstance(session.close(), CleanupComplete)
    finally:
        assert isinstance(unrelated.close(), CleanupComplete)


def test_container_reports_external_removal_without_workload_result() -> None:
    session = DockerEngine().start(LaunchRequest(_IMAGE, ("sleep", "120")))
    assert not isinstance(session, StartFailure), session
    try:
        _docker("rm", "-f", session.identity.container)
        assert isinstance(session.exit_result(), EngineFailure)
        assert session.close() == CleanupComplete("absent")
        assert session.close() == CleanupComplete("absent")
    finally:
        assert isinstance(session.close(), CleanupComplete)


def test_container_removes_resource_after_docker_start_fails() -> None:
    result = DockerEngine().start(LaunchRequest(_IMAGE, ("/missing-program",)))
    if not isinstance(result, StartFailure):
        result.close()
        pytest.fail("Docker started an invalid workload.")
    assert isinstance(result.result, EngineFailure)
    assert result.result.stage == "start"
    assert "/missing-program" in result.result.detail
    assert result.cleanup == CleanupComplete("removed")
    assert result.result.container is not None
    assert not _exists(result.result.container)
