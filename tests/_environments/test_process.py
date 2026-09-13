# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._environments.process import run_command

if TYPE_CHECKING:
    from pathlib import Path


async def test_command_captures_output_and_exit_status(tmp_path: Path) -> None:
    # Fill both pipes beyond their buffers so sequential reads would hang.
    code = r"""
import json, os, sys
print(json.dumps([os.getcwd(), os.environ['SANDBOX_TEST_VALUE']]))
sys.stdout.write('x' * 131072)
sys.stdout.flush()
sys.stderr.write('y' * 131072 + '\nfinished 🎲\n')
sys.exit(3)
"""
    lines: list[str] = []
    result = await run_command(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "SANDBOX_TEST_VALUE": "value with spaces",
        },
        on_stderr=lines.append,
        timeout=10,
    )
    context, stdout = result.stdout.split("\n", 1)
    expected_cwd = str(tmp_path.resolve())  # noqa: ASYNC240
    assert json.loads(context) == [expected_cwd, "value with spaces"]
    assert stdout == "x" * 131072
    assert result.stderr == "y" * 131072 + "\nfinished 🎲\n"
    assert "".join(lines) == result.stderr
    assert result.returncode == 3


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.timeout(15)
async def test_stopping_command_cleans_up_after_launcher_exits(
    stop: str,
) -> None:
    import psutil

    # The child keeps the capture pipes open after its launcher exits.
    child_code = """
import os, signal, sys
sys.stdin.read()
print(f'{sys.argv[1]} {os.getpid()}', file=sys.stderr, flush=True)
signal.pause()
"""
    code = f"""
import os, subprocess, sys
subprocess.Popen(
    [sys.executable, '-c', {child_code!r}, str(os.getpid())],
    stdin=subprocess.PIPE,
)
"""
    ready = asyncio.Event()
    pids: list[int] = []

    def on_stderr(line: str) -> None:
        pids.extend(map(int, line.split()))
        ready.set()

    task = asyncio.create_task(
        run_command(
            [sys.executable, "-c", code],
            on_stderr=on_stderr,
            timeout=3 if stop == "timeout" else None,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        launcher, child = (psutil.Process(pid) for pid in pids)
        await asyncio.to_thread(launcher.wait, timeout=5)
        assert not task.done()
        if stop == "cancel":
            task.cancel()
        with pytest.raises(
            asyncio.CancelledError
            if stop == "cancel"
            else asyncio.TimeoutError
        ):
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        _, alive = await asyncio.to_thread(
            psutil.wait_procs, [child], timeout=5
        )
        assert not alive, "Cancelled command left its child running"
    finally:
        for pid in reversed(pids):
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
