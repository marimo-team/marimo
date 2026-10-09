# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest

from tests._cli._pair_server import PairTestServer, pair_test_server

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture(scope="module")
def server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[PairTestServer, None, None]:
    with pair_test_server(tmp_path_factory.mktemp("pair")) as running:
        yield running


def _command(server: PairTestServer, *arguments: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "marimo",
        "pair",
        "execute",
        "--url",
        server.url,
        "--notebook",
        server.notebook_id,
        *arguments,
    ]


def _run(
    server: PairTestServer,
    *arguments: str,
    code_input: str | None = None,
    timeout: float = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command(server, *arguments),
        input=code_input,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def test_streams_output_before_execution_finishes(
    server: PairTestServer,
) -> None:
    process = subprocess.Popen(
        _command(
            server,
            "--stream",
            "-c",
            'import time; print("a"); time.sleep(1); print("b")',
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        with ThreadPoolExecutor(max_workers=1) as executor:
            first_line = executor.submit(process.stdout.readline).result(
                timeout=10
            )
        assert first_line == "a\n"
        assert process.poll() is None
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0, stderr
    assert stdout == "b\n"


def test_executes_by_stable_session_id(server: PairTestServer) -> None:
    assert server.notebook_id != server.session_id

    result = _run(server, "-c", "print('stable')")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["stdout"] == "stable\n"
    assert payload["notebook"]["id"] == server.notebook_id


@pytest.mark.skipif(os.name != "posix", reason="SIGINT requires POSIX")
def test_interrupt_disconnects_and_kernel_recovers(
    server: PairTestServer,
) -> None:
    process = subprocess.Popen(
        _command(server, "-c", "import time; time.sleep(30)"),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        server.wait_for_kernel("running")
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 1, (stdout, stderr)
    assert json.loads(stdout)["outcome"] == "interrupted"
    assert stderr == ""
    server.wait_for_kernel("idle")

    recovered = _run(server, "-c", "print('alive')")
    assert recovered.returncode == 0, recovered.stderr
    payload = json.loads(recovered.stdout)
    assert payload["success"] is True
    assert payload["stdout"] == "alive\n"
    assert payload["output"] is None
    assert payload["notebook"]["id"] == server.notebook_id


def test_missing_input_does_not_read_stdin_or_execute(
    server: PairTestServer,
) -> None:
    result = _run(server, code_input="print('must not run')\n")

    assert result.returncode == 2
    assert "error: specify -c or --code-file" in result.stderr
    assert "must not run" not in result.stdout
    server.wait_for_kernel("idle", timeout=1)


@pytest.mark.parametrize(
    ("code", "error"),
    [("1 / 0", "ZeroDivisionError"), ("input()", "EOFError")],
)
def test_host_run_error_returns_failed_result(
    server: PairTestServer, code: str, error: str
) -> None:
    result = _run(server, "-c", code)
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "failed"
    assert payload["success"] is False
    assert error in payload["stderr"]


def test_concurrent_host_run_reports_conflict(server: PairTestServer) -> None:
    process = subprocess.Popen(
        _command(server, "-c", "import time; time.sleep(30)"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        server.wait_for_kernel("running")
        second = _run(server, "-c", "print('must not run')")
        assert second.returncode == 2
        payload = json.loads(second.stdout)
        assert (
            "active" in payload["error"].lower()
            or "progress" in payload["error"].lower()
        )
        assert payload["stdout"] is None
    finally:
        process.send_signal(signal.SIGINT)
        process.communicate(timeout=10)
    server.wait_for_kernel("idle")


def test_host_run_without_runtime_reports_error(tmp_path: Path) -> None:
    import urllib.request

    from marimo._cli.pair.client import resolve_host

    with pair_test_server(tmp_path) as server:
        host = resolve_host(server.url)
        request = urllib.request.Request(
            f"{host.url}/notebooks/{server.notebook_id}/runtime",
            method="DELETE",
            headers={
                "Authorization": f"Bearer {host.token}",
                "Idempotency-Key": "stop-test-runtime",
            },
        )
        with urllib.request.urlopen(request, timeout=5):
            pass
        result = _run(server, "-c", "1")
        assert result.returncode == 2
        payload = json.loads(result.stdout)
        assert "runtime" in payload["error"].lower()
        assert "kernel" in payload["next"]
