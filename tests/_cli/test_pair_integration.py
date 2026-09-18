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
        "--session",
        server.session_id,
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
    assert stderr == "Interrupted.\n"
    server.wait_for_kernel("idle")

    recovered = _run(server, "-c", "print('alive')")
    assert recovered.returncode == 0, recovered.stderr
    payload = json.loads(recovered.stdout)
    assert payload["success"] is True
    assert payload["stdout"] == "alive\n"
    assert payload["output"] is None
    assert payload["session"]["id"] == server.session_id


def test_missing_input_does_not_read_stdin_or_execute(
    server: PairTestServer,
) -> None:
    result = _run(
        server,
        code_input="print('must not run')\n",
        timeout=2,
    )

    assert result.returncode == 2
    assert "error: specify -c or --code-file" in result.stderr
    assert "must not run" not in result.stdout
    server.wait_for_kernel("idle", timeout=1)
