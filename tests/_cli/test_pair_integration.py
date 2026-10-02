# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

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
        "--session",
        server.stable_session_id,
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
    assert server.stable_session_id != server.session_id

    result = _run(server, "-c", "print('stable')")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["stdout"] == "stable\n"
    assert payload["session"]["id"] == server.stable_session_id


def test_connect_persists_across_cli_processes(tmp_path: Path) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("MARIMO_PAIR_HARNESS", "MARIMO_PAIR_CONVERSATION_ID")
    }
    environment["XDG_STATE_HOME"] = str(tmp_path / "state")

    with pair_test_server(
        tmp_path, pair_preview=True, skew_protection=True
    ) as server:
        connected = subprocess.run(
            [
                sys.executable,
                "-m",
                "marimo",
                "pair",
                "connect",
                "--url",
                server.url,
                "--session",
                server.stable_session_id,
            ],
            env=environment,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        executed = subprocess.run(
            _command(server, "-c", "print('connected')"),
            env=environment,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    assert connected.returncode == 0, connected.stderr
    assert json.loads(connected.stdout)["record_created"] is True
    assert executed.returncode == 0, executed.stderr
    payload = json.loads(executed.stdout)
    assert payload["stdout"] == "connected\n"
    assert payload["participant"] == {
        "harness": "unknown",
        "scope": "harness",
    }


def test_handoff_events_stream_and_detach_across_processes(
    tmp_path: Path,
) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("MARIMO_PAIR_HARNESS", "MARIMO_PAIR_CONVERSATION_ID")
    }
    environment["XDG_STATE_HOME"] = str(tmp_path / "state")

    def run_pair(
        server: PairTestServer, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "marimo",
                "pair",
                *arguments,
                "--url",
                server.url,
                "--session",
                server.stable_session_id,
            ],
            env=environment,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def send_handoff(server: PairTestServer, cell_id: str) -> None:
        parsed = urlsplit(server.url)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port)
        try:
            connection.request(
                "POST",
                "/api/participants/handoff",
                body=json.dumps(
                    {
                        "cellId": cell_id,
                        "error": "NameError",
                        "code": "df.head()",
                        "traceback": "Traceback\nNameError",
                    }
                ),
                headers={
                    "Content-Type": "application/json",
                    "Marimo-Stable-Session-Id": server.stable_session_id,
                },
            )
            response = connection.getresponse()
            assert response.status == 200, response.read()
        finally:
            connection.close()

    with pair_test_server(tmp_path, pair_preview=True) as server:
        connected = run_pair(server, "connect")
        assert connected.returncode == 0, connected.stderr

        send_handoff(server, "cell-one")
        events = run_pair(server, "events")
        assert events.returncode == 0, events.stderr
        assert (
            "cell-one"
            in json.loads(events.stdout)["handoffs"]["events"][0]["text"]
        )

        empty = run_pair(server, "events")
        assert empty.returncode == 0, empty.stderr
        assert json.loads(empty.stdout)["handoffs"]["events"] == []

        send_handoff(server, "cell-two")
        listened = run_pair(server, "listen", "--once")
        assert listened.returncode == 0, listened.stderr
        assert "cell-two" in listened.stdout

        detached = run_pair(server, "detach")
        assert detached.returncode == 0, detached.stderr
        assert json.loads(detached.stdout)["attached"] is False
        assert not list(
            (tmp_path / "state" / "marimo" / "pair").rglob("*.json")
        )


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
    assert payload["session"]["id"] == server.stable_session_id


def test_missing_input_does_not_read_stdin_or_execute(
    server: PairTestServer,
) -> None:
    result = _run(server, code_input="print('must not run')\n")

    assert result.returncode == 2
    assert "error: specify -c or --code-file" in result.stderr
    assert "must not run" not in result.stdout
    server.wait_for_kernel("idle", timeout=1)
