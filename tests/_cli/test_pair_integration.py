# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tests._cli._pair_server import PairTestServer, pair_test_server

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping
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
        "--session",
        server.session_id,
        *arguments,
    ]


def _run(
    server: PairTestServer,
    *arguments: str,
    code_input: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command(server, *arguments),
        input=code_input,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def _large_program() -> str:
    return f"value = {'x' * 1_048_576!r}\nprint(len(value))\n"


def test_one_mebibyte_stdin(server: PairTestServer) -> None:
    result = _run(server, code_input=_large_program())

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1048576\n"


def test_one_mebibyte_code_file(
    server: PairTestServer,
    tmp_path: Path,
) -> None:
    code_file = tmp_path / "large.py"
    code_file.write_text(_large_program())

    result = _run(server, "--code-file", str(code_file))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1048576\n"


@pytest.mark.skipif(os.name != "posix", reason="SIGINT requires POSIX")
def test_interrupt_disconnects_and_kernel_recovers(
    server: PairTestServer,
) -> None:
    process = subprocess.Popen(
        _command(server, "-c", "while True: pass"),
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

    assert process.returncode == 130, (stdout, stderr)
    server.wait_for_kernel("idle")

    recovered = _run(server, "-c", "print('alive')")
    assert recovered.returncode == 0, recovered.stderr
    assert recovered.stdout == "alive\n"


@pytest.mark.skipif(os.name != "posix", reason="ps requires POSIX")
def test_code_and_token_are_absent_from_process_arguments(
    server: PairTestServer,
) -> None:
    body_marker = "pair-body-secret-marker"
    token = "pair-token-secret-marker"
    code = f"value = {body_marker + 'x' * 1_048_576!r}\nwhile True: pass\n"
    env = {**os.environ, "MARIMO_TOKEN": token}
    process = subprocess.Popen(
        _command(server),
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdin is not None
        process.stdin.write(code)
        process.stdin.close()
        process.stdin = None
        server.wait_for_kernel("running")
        inspected = subprocess.run(
            ["ps", "-ww", "-o", "command=", "-p", str(process.pid)],
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        ).stdout

        if body_marker in inspected or code in inspected:
            pytest.fail("the code body appeared in the client arguments")
        if token in inspected:
            pytest.fail(
                "the authentication token appeared in client arguments"
            )
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.communicate(timeout=10)

    assert process.returncode == 130
    server.wait_for_kernel("idle")
