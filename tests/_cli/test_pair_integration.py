# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Literal

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


def _command(
    server: PairTestServer,
    *arguments: str,
    selector: Literal["notebook", "session", "auto"] = "notebook",
) -> list[str]:
    target = []
    if selector == "notebook":
        target = ["--notebook", server.notebook_id]
    elif selector == "session":
        target = ["--session", server.stable_session_id]
    return [
        sys.executable,
        "-m",
        "marimo",
        "pair",
        "execute",
        "--url",
        server.url,
        *target,
        *arguments,
    ]


def _run(
    server: PairTestServer,
    *arguments: str,
    code_input: str | None = None,
    timeout: float = 20,
    selector: Literal["notebook", "session", "auto"] = "notebook",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command(server, *arguments, selector=selector),
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


@pytest.mark.parametrize("selector", ["notebook", "session", "auto"])
def test_execution_target_selection(
    server: PairTestServer,
    selector: Literal["notebook", "session", "auto"],
) -> None:
    assert server.notebook_id != server.session_id

    result = _run(server, "-c", "print('stable')", selector=selector)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["stdout"] == "stable\n"
    if selector != "session":
        assert payload["notebook"] == {"id": server.notebook_id}
        assert "session" not in payload
    else:
        assert payload["session"] == {
            "id": server.stable_session_id
            if selector == "session"
            else server.notebook_id
        }


@pytest.fixture(scope="module")
def editor_server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[PairTestServer, None, None]:
    with pair_test_server(
        tmp_path_factory.mktemp("pair-editor"),
        token="pair-editor-private-token",
    ) as running:
        yield running


@pytest.mark.parametrize("selector", ["session", "auto"])
def test_authenticated_execution_preserves_session_contract(
    editor_server: PairTestServer,
    tmp_path: Path,
    selector: Literal["session", "auto"],
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("pair-editor-private-token")
    result = _run(
        editor_server,
        "--token-file",
        str(token_file),
        "-c",
        "print('editor'); 42",
        selector=selector,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["stdout"] == "editor\n"
    assert payload["output"] == {
        "mimetype": "text/html",
        "data": "<pre class='text-xs'>42</pre>",
    }
    assert payload["notebook"] == {"id": editor_server.notebook_id}
    assert "session" not in payload


def test_explicit_wrong_token_does_not_fall_back_to_local_credentials(
    editor_server: PairTestServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    result = _run(
        editor_server,
        "--token",
        "wrong-token",
        "-c",
        "print('must not execute')",
        selector="session",
    )
    assert result.returncode == 2
    assert "must not execute" not in result.stdout
    assert "pair-editor-private-token" not in result.stdout + result.stderr
    editor_server.wait_for_kernel("idle")


@pytest.mark.parametrize("stream", [False, True])
def test_editor_execution_failure_preserves_output(
    editor_server: PairTestServer,
    tmp_path: Path,
    stream: bool,
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("pair-editor-private-token")
    result = _run(
        editor_server,
        "--token-file",
        str(token_file),
        *(["--stream"] if stream else []),
        "-c",
        "print('before error'); 1 / 0",
        selector="session",
    )
    assert result.returncode == 1, result.stderr
    if stream:
        assert result.stdout == "before error\n"
        assert "ZeroDivisionError" in result.stderr
    else:
        payload = json.loads(result.stdout)
        assert payload["success"] is False
        assert payload["stdout"] == "before error\n"
        assert "ZeroDivisionError" in payload["stderr"]
        assert payload["notebook"] == {"id": editor_server.notebook_id}
        assert "session" not in payload


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
    assert stdout == ""
    assert stderr == "Interrupted.\n"
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
    assert "error: specify exactly one of --code or --file" in result.stderr
    assert "must not run" not in result.stdout
    server.wait_for_kernel("idle", timeout=1)


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("1 / 0", "ZeroDivisionError"),
        ("raise ValueError('bad value')", "ValueError"),
    ],
)
def test_execution_error_returns_failed_result(
    server: PairTestServer, code: str, error: str
) -> None:
    result = _run(server, "-c", code)
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "failed"
    assert payload["success"] is False
    assert error in payload["stderr"]


def test_concurrent_execution_waits_for_the_active_run(
    server: PairTestServer,
) -> None:
    first = subprocess.Popen(
        _command(
            server,
            "-c",
            "import builtins, time\n"
            "time.sleep(2)\n"
            "builtins._pair_first_done = True",
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        server.wait_for_kernel("running")
        # Accepted while the first run executes, and queued behind it.
        second = _run(
            server,
            "-c",
            "import builtins\n"
            "print(builtins._pair_first_done)\n"
            "del builtins._pair_first_done",
        )
    finally:
        stdout, stderr = first.communicate(timeout=20)

    assert first.returncode == 0, (stdout, stderr)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["stdout"] == "True\n"
    server.wait_for_kernel("idle")


def test_execution_without_runtime_reports_error(tmp_path: Path) -> None:
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
        assert "No running notebook matches" in payload["error"]
        assert "marimo pair list" in payload["next"]


@pytest.mark.parametrize("identifier", ["notebook_id", "stable_session_id"])
def test_legacy_execute_accepts_the_local_credential(
    editor_server: PairTestServer, identifier: str
) -> None:
    import io

    from marimo._cli.pair.client import execute, resolve_host

    host = resolve_host(editor_server.url)
    result = execute(
        url=editor_server.url,
        session_id=getattr(editor_server, identifier),
        token=host.token,
        code="print('local credential')",
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        stream=False,
    )
    assert result.success, result.stderr
    assert result.stdout == "local credential\n"


def test_list_discovers_an_authenticated_running_notebook(
    editor_server: PairTestServer,
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "marimo", "pair", "list"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    listing = json.loads(result.stdout)
    [notebook] = [
        n for n in listing["notebooks"] if n["id"] == editor_server.notebook_id
    ]
    assert notebook["status"] == "running"
    assert notebook["path"].endswith(".py")
    assert "pair-editor-private-token" not in result.stdout


@pytest.mark.parametrize("source", ["code", "file", "stdin"])
def test_execute_discovered_id_without_url_or_credentials(
    editor_server: PairTestServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    code = "print('discovered notebook')"
    path = tmp_path / "experiment.py"
    path.write_text(code)
    arguments = {
        "code": ["--code", code],
        "file": ["--file", str(path)],
        "stdin": ["--file", "-"],
    }[source]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "marimo",
            "pair",
            "execute",
            "--session",
            editor_server.notebook_id,
            *arguments,
        ],
        input=code if source == "stdin" else None,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["stdout"] == "discovered notebook\n"
    assert payload["notebook"] == {"id": editor_server.notebook_id}
    assert "session" not in payload


def test_discovered_notebook_supports_code_mode_edits(
    editor_server: PairTestServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "marimo",
            "pair",
            "execute",
            "--session",
            editor_server.notebook_id,
            "--file",
            "-",
        ],
        input=(
            "import marimo._code_mode as cm\n"
            "async with cm.get_context() as ctx:\n"
            '    cell = ctx.create_cell("pair_discovery_value = 314")\n'
            "    ctx.run_cell(cell)\n"
        ),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    inspected = _run(editor_server, "--code", "print(pair_discovery_value)")
    assert inspected.returncode == 0, (inspected.stdout, inspected.stderr)
    assert json.loads(inspected.stdout)["stdout"] == "314\n"


def test_notebook_id_targets_the_replacement_kernel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time
    import urllib.request

    from marimo._cli.pair.client import resolve_host
    from marimo._cli.pair.discovery import list_running_notebooks

    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    with pair_test_server(tmp_path, token="restart-editor-secret") as running:
        host = resolve_host(running.url)
        request = urllib.request.Request(
            f"{host.url}/notebooks/{running.notebook_id}/runtime/restart",
            method="POST",
            data=b"{}",
            headers={
                "Authorization": f"Bearer {host.token}",
                "Idempotency-Key": "pair-restart-test",
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 202
        deadline = time.monotonic() + 10
        while not list_running_notebooks([host]).notebooks:
            assert time.monotonic() < deadline, (
                "Replacement kernel did not start"
            )
            time.sleep(0.05)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "marimo",
                "pair",
                "execute",
                "--session",
                running.notebook_id,
                "--code",
                "print('replacement')",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert json.loads(result.stdout)["stdout"] == "replacement\n"


@pytest.mark.parametrize("selector", ["--notebook", "--session"])
@pytest.mark.parametrize("scoped", [False, True])
def test_notebook_identity_is_independent_of_selector_and_url(
    editor_server: PairTestServer,
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
    scoped: bool,
) -> None:
    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "marimo",
            "pair",
            "execute",
            selector,
            editor_server.notebook_id,
            *(["--url", editor_server.url] if scoped else []),
            "--code",
            "print(2)",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json.loads(result.stdout) == {
        "success": True,
        "outcome": "succeeded",
        "output": None,
        "stdout": "2\n",
        "stderr": "",
        "notebook": {"id": editor_server.notebook_id},
    }


@pytest.mark.parametrize("selector", ["--notebook", "--session"])
def test_url_does_not_discover_a_notebook_on_another_server(
    server: PairTestServer,
    editor_server: PairTestServer,
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
) -> None:
    monkeypatch.delenv("MARIMO_TOKEN", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "marimo",
            "pair",
            "execute",
            "--url",
            server.url,
            selector,
            editor_server.notebook_id,
            "--code",
            "print('must not execute')",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 2, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["error"] == (
        f"No running notebook matches {editor_server.notebook_id!r} on {server.url}."
        if selector == "--notebook"
        else f"No notebook {editor_server.notebook_id} on {server.url}. Run pair list to find the current notebook."
    )
    assert "must not execute" not in result.stdout
