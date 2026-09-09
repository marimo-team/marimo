# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any
from unittest.mock import patch

import click
import pytest

from marimo._cli.export._common import SandboxTarget, run_python_subprocess
from marimo._environments.environment import Environment, ProcessPlan


@pytest.mark.parametrize("isolated", [False, True])
def test_export_runs_the_planned_command(isolated: bool) -> None:
    handle = (
        None
        if isolated
        else Environment(sys.executable, sys.prefix, "unchanged")
    )
    module = "marimo._environments.environment"
    target = f"{module}.launch_isolated" if isolated else f"{module}.launch"
    code = (
        "import json,os,sys; print(json.dumps([os.getpid(), os.getsid(0)]))"
        if os.name != "nt"
        else "print('done')"
    )
    plan = ProcessPlan((sys.executable, "-c", code), dict(os.environ), True)
    with patch(target, return_value=plan):
        output = run_python_subprocess(
            sandbox=SandboxTarget(handle),
            script="ignored",
            payload={},
            action="export",
        )
    if os.name != "nt":
        import json

        pid, session = json.loads(output)
        assert pid == session
    else:
        assert output.strip() == "done"


def test_export_failure_identifies_launcher_without_payload_or_credentials() -> (
    None
):
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
        "marimo._environments.environment.launch_isolated", return_value=plan
    ):
        with pytest.raises(click.ClickException) as error:
            run_python_subprocess(
                sandbox=SandboxTarget(None),
                script="private notebook",
                payload={"token": "secret"},
                action="export",
            )
    message = str(error.value)
    assert os.path.basename(sys.executable) in message
    assert "failed" in message
    assert "secret" not in message
    assert "private notebook" not in message


@pytest.mark.parametrize("new_session", [False, True])
def test_export_interrupt_reaps_the_child(new_session: bool) -> None:
    children = []
    popen = subprocess.Popen

    class InterruptedProcess(subprocess.Popen):
        def communicate(self, *_args: Any, **_kwargs: Any):
            assert self.stdout.readline().strip() == "ready"
            raise KeyboardInterrupt

    def launch(*args: Any, **kwargs: Any):
        # `patch` mutates the shared subprocess module, so Windows taskkill
        # launched by `kill_subprocess` must keep using the real Popen.
        if args[0][0] == "taskkill":
            return popen(*args, **kwargs)
        child = InterruptedProcess(*args, **kwargs)
        children.append(child)
        return child

    plan = ProcessPlan(
        (
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(30)",
        ),
        dict(os.environ),
        new_session,
    )
    with (
        patch(
            "marimo._environments.environment.launch_isolated",
            return_value=plan,
        ),
        patch(
            "marimo._cli.export._common.subprocess.Popen", side_effect=launch
        ),
    ):
        with pytest.raises(KeyboardInterrupt):
            run_python_subprocess(
                sandbox=SandboxTarget(None),
                script="",
                payload={},
                action="export",
            )
    child = children[0]
    assert child.poll() is not None
    assert child.stdout.closed
    assert child.stderr.closed


@pytest.mark.skipif(os.name == "nt", reason="POSIX termination signals")
def test_export_sigterm_reaps_isolated_child(tmp_path) -> None:
    import signal
    import time

    ready = tmp_path / "ready"
    code = f"""
import os, sys
from marimo._cli.export._common import SandboxTarget, run_python_subprocess
from marimo._environments import environment
child = "import os,time; from pathlib import Path; Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(30)"
environment.launch_isolated = lambda *a, **kw: environment.ProcessPlan((sys.executable, '-c', child), dict(os.environ), True)
run_python_subprocess(sandbox=SandboxTarget(None), script='', payload={{}}, action='export')
"""
    parent = subprocess.Popen([sys.executable, "-c", code])
    child_pid = None
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            assert parent.poll() is None
            time.sleep(0.02)
        child_pid = int(ready.read_text())
        parent.send_signal(signal.SIGTERM)
        assert parent.wait(timeout=10) == 128 + signal.SIGTERM
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        parent.kill()
        parent.wait(timeout=5)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
