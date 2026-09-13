# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

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

from marimo._cli.export._common import run_python_subprocess
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
