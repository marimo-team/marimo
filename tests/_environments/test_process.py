# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._environments.process import run_command
from marimo._utils.subprocess import stop_subprocess

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Executor
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


@pytest.mark.timeout(10)
@pytest.mark.parametrize("failed_reader", [0, 1], ids=["stdout", "stderr"])
async def test_pipe_reader_setup_failure_stops_command(
    failed_reader: int,
) -> None:
    loop = asyncio.get_running_loop()
    submit = loop.run_in_executor
    readers: list[asyncio.Future[object]] = []

    def fail_reader(
        executor: Executor | None, function: Callable[[], object]
    ) -> asyncio.Future[object]:
        # Cleanup uses a separate executor, which must still accept work.
        if executor is not None:
            return submit(executor, function)
        if len(readers) == failed_reader:
            raise RuntimeError("Cannot start pipe reader")
        reader = submit(executor, function)
        readers.append(reader)
        return reader

    with (
        patch.object(loop, "run_in_executor", side_effect=fail_reader),
        patch(
            "marimo._environments.process.stop_subprocess",
            wraps=stop_subprocess,
        ) as cleanup,
    ):
        with pytest.raises(RuntimeError, match="Cannot start pipe reader"):
            await run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"]
            )
        cleanup.assert_awaited_once()
        process = cleanup.call_args.args[0]
        assert process.poll() is not None
        assert all(reader.done() for reader in readers)


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
        if stop == "cancel":
            assert not task.done()
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


async def test_repeated_cancellation_waits_for_cleanup_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._utils import subprocess as subprocess_utils

    loop = asyncio.get_running_loop()
    ready = asyncio.Event()
    stopping = asyncio.Event()
    release = threading.Event()
    kill = subprocess_utils.kill_subprocess
    processes = []

    def slow_kill(process, *, start_new_session):
        processes.append(process)
        loop.call_soon_threadsafe(stopping.set)
        try:
            assert release.wait(timeout=10)
        finally:
            kill(process, start_new_session=start_new_session)

    monkeypatch.setattr(subprocess_utils, "kill_subprocess", slow_kill)
    task = asyncio.create_task(
        run_command(
            [
                sys.executable,
                "-c",
                "import sys,time; print('ready', file=sys.stderr, flush=True); time.sleep(60)",
            ],
            on_stderr=lambda _line: ready.set(),
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        task.cancel()
        await asyncio.wait_for(stopping.wait(), timeout=5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        assert processes[0].poll() is not None
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.timeout(15)
async def test_cancellation_with_saturated_default_executor() -> None:
    import psutil

    loop = asyncio.get_running_loop()
    ready = asyncio.Event()
    child: psutil.Process | None = None

    def on_stderr(line: str) -> None:
        nonlocal child
        child = psutil.Process(int(line))
        ready.set()

    # One reader per pipe occupies every worker until the child dies.
    executor = ThreadPoolExecutor(max_workers=2)
    loop.set_default_executor(executor)
    task = asyncio.create_task(
        run_command(
            [
                sys.executable,
                "-c",
                "import os,sys,time; print(os.getpid(), file=sys.stderr, flush=True); time.sleep(60)",
            ],
            on_stderr=on_stderr,
        )
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), timeout=2)
        assert child is not None
        assert not child.is_running()
    finally:
        if child is not None:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        loop.set_default_executor(ThreadPoolExecutor())
        executor.shutdown()
