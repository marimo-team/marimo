# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import select
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import click
import pytest

from marimo._cli.export._common import (
    _export_termination_signals,
    run_python_subprocess,
)
from marimo._environments.environment import Environment, ProcessPlan
from marimo._environments.pixi import PixiMissingScriptMetadataError
from marimo._environments.sandbox import Backend
from marimo._environments.uv import UvMissingScriptMetadataError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def notebook_without_metadata(monkeypatch: pytest.MonkeyPatch) -> str:
    async def missing_metadata(*_args: Any, **_kwargs: Any) -> None:
        raise UvMissingScriptMetadataError(
            ["uv", "sync"], 1, "", "No script metadata"
        )

    monkeypatch.setattr(
        "marimo._environments.backends.sync_notebook_async", missing_metadata
    )
    return "notebook.py"


async def test_export_runs_the_planned_command() -> None:
    code = (
        "import json,os,sys; print(json.dumps([os.getpid(), os.getsid(0)]))"
        if os.name != "nt"
        else "print('done')"
    )
    plan = ProcessPlan((sys.executable, "-c", code), dict(os.environ), True)
    with (
        patch(
            "marimo._environments.backends.sync_notebook_async",
            return_value=Environment(sys.executable, sys.prefix, "unchanged"),
        ),
        patch("marimo._environments.environment.launch", return_value=plan),
    ):
        output = await run_python_subprocess(
            notebook_path="notebook.py",
            backend="uv",
            script="ignored",
            payload={},
            action="export",
        )
    if os.name != "nt":
        pid, session = json.loads(output)
        assert pid == session
    else:
        assert output.strip() == "done"


@pytest.mark.parametrize("backend", ["uv", "pixi"])
async def test_export_without_metadata_uses_current_interpreter(
    notebook_without_metadata: str,
    backend: Backend,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if backend == "pixi":

        async def missing_metadata(*_args: Any, **_kwargs: Any) -> None:
            raise PixiMissingScriptMetadataError(
                ["pixi", "install"], 1, "No script metadata"
            )

        monkeypatch.setattr(
            "marimo._environments.backends.sync_notebook_async",
            missing_metadata,
        )

    payload = {"args": ["value with spaces", "--flag"], "unicode": "🎲"}
    output = await run_python_subprocess(
        notebook_path=notebook_without_metadata,
        backend=backend,
        script="import json,sys; print(json.dumps([sys.executable, json.loads(sys.argv[1])]))",
        payload=payload,
        action="export",
    )
    assert json.loads(output) == [sys.executable, payload]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
async def test_export_fallback_cancellation_stops_descendants(
    notebook_without_metadata: str, tmp_path: Path
) -> None:
    import psutil

    ready = tmp_path / "child.pid"
    child_code = (
        "import os, signal; from pathlib import Path; "
        f"Path({str(ready)!r}).write_text(str(os.getpid())); "
        "signal.pause()"
    )
    script = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}])"
    )
    task = asyncio.create_task(
        run_python_subprocess(
            notebook_path=notebook_without_metadata,
            backend="uv",
            script=script,
            payload={},
            action="export",
        )
    )
    child = None
    try:

        async def wait_for_child() -> int:
            while True:
                try:
                    return int(await asyncio.to_thread(ready.read_text))
                except (FileNotFoundError, ValueError):
                    await asyncio.sleep(0.01)

        child = psutil.Process(await asyncio.wait_for(wait_for_child(), 5))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        _, alive = await asyncio.to_thread(
            psutil.wait_procs, [child], timeout=5
        )
        assert not alive, "Cancelled export left its descendant running"
    finally:
        if child is not None:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_export_failure_identifies_launcher_without_payload_or_credentials(
    notebook_without_metadata: str,
) -> None:
    plan = ProcessPlan(
        (
            sys.executable,
            "-c",
            "import sys; print('failed', file=sys.stderr); sys.exit(2)",
            "https://user:secret@example.org",
            "private notebook",
        ),
        dict(os.environ),
        True,
    )
    with patch(
        "marimo._environments.backends.launch_fallback", return_value=plan
    ):
        with pytest.raises(click.ClickException) as error:
            await run_python_subprocess(
                notebook_path=notebook_without_metadata,
                backend="uv",
                script="private notebook",
                payload={"token": "secret"},
                action="export",
            )
    message = str(error.value)
    assert os.path.basename(sys.executable) in message
    assert "failed" in message
    assert "secret" not in message
    assert "private notebook" not in message


@pytest.mark.skipif(os.name == "nt", reason="POSIX termination signals")
@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGHUP"])
async def test_export_termination_at_completion(signal_name: str) -> None:
    signum = getattr(signal, signal_name)
    previous = signal.getsignal(signum)
    with pytest.raises(SystemExit) as error:
        with _export_termination_signals():
            signal.raise_signal(signum)

    assert error.value.code == 128 + signum
    assert signal.getsignal(signum) == previous
    # Let the queued callback run after the scope closes. It must not cancel
    # subsequent work in the task that owned the export.
    await asyncio.sleep(0)


@pytest.mark.skipif(os.name == "nt", reason="POSIX termination signals")
@pytest.mark.timeout(10)
async def test_repeated_export_termination_finishes_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._environments import process as command_process

    stop = command_process.stop_subprocess
    processes: list[subprocess.Popen[Any]] = []
    repeated_signals_handled = False

    async def interrupted_cleanup(
        process: subprocess.Popen[Any],
        *,
        start_new_session: bool,
        drain: asyncio.Future[Any] | None = None,
    ) -> None:
        nonlocal repeated_signals_handled
        processes.append(process)
        try:
            signal.raise_signal(signal.SIGHUP)
            await asyncio.sleep(0)
            signal.raise_signal(signal.SIGTERM)
            await asyncio.sleep(0)
            repeated_signals_handled = True
        finally:
            await stop(
                process, start_new_session=start_new_session, drain=drain
            )

    monkeypatch.setattr(
        command_process, "stop_subprocess", interrupted_cleanup
    )
    with pytest.raises(SystemExit) as error:
        with _export_termination_signals():
            await command_process.run_command(
                [
                    sys.executable,
                    "-c",
                    "import sys,time; print('ready', file=sys.stderr, flush=True); time.sleep(30)",
                ],
                on_stderr=lambda _line: signal.raise_signal(signal.SIGTERM),
            )

    assert error.value.code == 128 + signal.SIGTERM
    assert repeated_signals_handled
    assert len(processes) == 1
    assert processes[0].poll() is not None
    await asyncio.sleep(0)


@pytest.mark.skipif(os.name == "nt", reason="POSIX termination signals")
@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_export_termination_during_process_creation(signal_name: str) -> None:
    code = """
import asyncio, json, signal, subprocess, sys
from marimo._cli.export._common import _export_termination_signals
from marimo._environments.process import run_command

processes = []
execute_child = subprocess.Popen._execute_child

def interrupted_spawn(self, *args, **kwargs):
    execute_child(self, *args, **kwargs)
    processes.append(self)
    # Deliver termination after spawning, before Popen returns to its owner.
    signal.raise_signal(getattr(signal, sys.argv[1]))

subprocess.Popen._execute_child = interrupted_spawn

async def main():
    with _export_termination_signals():
        await run_command([sys.executable, '-c', 'import time; time.sleep(30)'])

loop = asyncio.new_event_loop()
try:
    # Do not use asyncio.run here. On Python 3.11+, Runner installs its own
    # SIGINT handler, which deliberately bypasses the default-handler branch
    # that protects Python 3.10 from an interrupt during Popen.
    loop.run_until_complete(main())
except KeyboardInterrupt:
    sys.exit(1)
finally:
    loop.close()
    print(json.dumps([process.poll() is None for process in processes]))
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait()
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, signal_name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == (
        1 if signal_name == "SIGINT" else 128 + getattr(signal, signal_name)
    ), completed.stderr
    assert json.loads(completed.stdout) == [False]


@pytest.mark.skipif(os.name == "nt", reason="POSIX termination signals")
@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGTERM"])
@pytest.mark.parametrize("phase", ["preparation", "execution"])
def test_session_cli_cancellation_stops_active_subprocesses(
    tmp_path: Path, signal_name: str, phase: str
) -> None:
    import psutil

    ready = tmp_path / "ready"
    os.mkfifo(ready)
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        "import marimo\napp = marimo.App()\n@app.cell\ndef _():\n"
        "    import os, time\n    from pathlib import Path\n"
        f"    Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        "    time.sleep(30)\n    return\n",
        encoding="utf-8",
    )
    # Skip dependency installation, but exercise the CLI, worker, and kernel.
    code = """
from marimo._cli.cli import main
from marimo._environments import backends
from marimo._environments.uv import UvMissingScriptMetadataError

async def missing_metadata(*args, **kwargs):
    raise UvMissingScriptMetadataError(["uv", "sync"], 1, "", "No script metadata")

backends.sync_notebook_async = missing_metadata
main(prog_name="marimo")
"""

    env = dict(os.environ)
    if phase == "preparation":
        # Stop in the real preparation path before an export worker exists.
        command = tmp_path / "uv"
        command.write_text(
            f"#!{sys.executable}\n"
            "import os, signal, sys\nfrom pathlib import Path\n"
            "if '--version' in sys.argv:\n"
            "    print('uv 0.12.0')\n"
            "elif 'sync' in sys.argv:\n"
            f"    Path({str(ready)!r}).write_text(str(os.getpid()))\n"
            "    signal.pause()\n",
            encoding="utf-8",
        )
        command.chmod(0o755)
        env["UV"] = str(command)
        code = "from marimo._cli.cli import main; main(prog_name='marimo')"

    children: list[psutil.Process] = []
    with (
        (tmp_path / "stderr").open("w+") as stderr,
        os.fdopen(
            os.open(ready, os.O_RDONLY | os.O_NONBLOCK), "rb"
        ) as readiness,
    ):
        parent = subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                "export",
                "session",
                str(tmp_path),
                "--sandbox",
            ],
            cwd=tmp_path,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            assert select.select([readiness], [], [], 15)[0], (
                "Sandbox subprocess did not start"
            )
            active_pid = int(readiness.read())
            children = psutil.Process(parent.pid).children(recursive=True)
            assert active_pid in {child.pid for child in children}
            signum = getattr(signal, signal_name)
            parent.send_signal(signum)
            exit_code = parent.wait(timeout=5)
            _, alive = psutil.wait_procs(children, timeout=5)
            assert not alive, "Export left children running"
            # Click reports KeyboardInterrupt as an aborted command (exit 1).
            assert exit_code == (
                1 if signal_name == "SIGINT" else 128 + signum
            )
        finally:
            if parent.poll() is None:
                children += psutil.Process(parent.pid).children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            parent.wait(timeout=5)
            stderr.seek(0)
            print(stderr.read())
