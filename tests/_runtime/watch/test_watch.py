# Copyright 2026 Marimo. All rights reserved.
import asyncio
import os
import threading
from pathlib import Path

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

pytestmark = pytest.mark.usefixtures("cleanup_watchers")


@pytest.mark.xfail(
    True, reason="Flaky in CI, can't repro locally", strict=False
)
async def test_read_and_write_path(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("from pathlib import Path"),
            exec_req.get(
                f'tmp = Path("{tmp_path.as_posix()}") / "test.txt"; tmp.write_text("0")'
            ),
            exec_req.get(
                """
                import time
                import marimo as mo
                mo.watch._file._TEST_SLEEP_INTERVAL = 0.05
                """
            ),
            exec_req.get("path = mo.watch.file(tmp)"),
            exec_req.get("x = path.read_text()"),
            exec_req.get(
                """
                x
                if x == "0":
                    path.write_text("1")
                """
            ),
        ]
    )
    await asyncio.sleep(0.1)

    assert not k.stdout.messages, k.stdout
    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == "1"


@pytest.mark.xfail(
    True, reason="Flaky in CI, can't repro locally", strict=False
)
async def test_read_and_write_iteration(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("from pathlib import Path"),
            exec_req.get(
                f'tmp = Path("{tmp_path.as_posix()}") / "test.txt"; tmp.touch()'
            ),
            exec_req.get(
                """
                import asyncio
                import marimo as mo
                mo.watch._file._TEST_SLEEP_INTERVAL = 0.01
                """
            ),
            exec_req.get("path = mo.watch.file(tmp)"),
            exec_req.get("x = path.read_bytes()"),
            exec_req.get(
                """
                x
                if len(x) < 3:
                    print("Writing 0")
                    path.write_bytes(b"0" * (len(x) + 1))
                """
            ),
        ]
    )
    await asyncio.sleep(0.1)

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == b"000"


@pytest.mark.xfail(
    True, reason="Flaky in CI, can't repro locally", strict=False
)
async def test_allow_self_loops(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("from pathlib import Path"),
            exec_req.get(
                """
                import asyncio
                import marimo as mo
                mo.watch._file._TEST_SLEEP_INTERVAL = 0.01
                """
            ),
            exec_req.get(
                f'tmp = Path("{tmp_path.as_posix()}") / "test.txt"; tmp.touch()'
            ),
            exec_req.get("path = mo.watch.file(tmp)"),
            exec_req.get(
                """
                path() # Just returns the path
                x = len(path.read_bytes())
                if x < 3:
                    path.write_bytes(b"0" * (x + 1))
                """
            ),
        ]
    )
    await asyncio.sleep(0.1)
    # Flakey in CI 3.13
    await k.run([])

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == 3


@pytest.mark.xfail(
    True, reason="Flaky in CI, can't repro locally", strict=False
)
async def test_directory_watch(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    k = execution_kernel
    await k.run(
        [
            exec_req.get("from pathlib import Path"),
            exec_req.get(f'tmp = Path("{tmp_path.as_posix()}")'),
            exec_req.get(
                """
                import time
                import marimo as mo
                mo.watch._directory._TEST_SLEEP_INTERVAL = 0.05
                """
            ),
            exec_req.get("path = mo.watch.directory(tmp)"),
            exec_req.get("x = len(list(path.glob('*')))"),
            exec_req.get(
                """
                x
                if x == 0:
                    (tmp / "test.txt").write_text("1")
                """
            ),
        ]
    )
    await asyncio.sleep(0.25)
    await k.run([])

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == 1


async def test_unchanged_file_does_not_rerun_dependents(
    k: Kernel,
    exec_req: ExecReqProvider,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.watch import _file

    monkeypatch.setattr(_file, "_TEST_SLEEP_INTERVAL", 0.01)
    tmp = tmp_path / "test.txt"
    tmp.write_text("0")
    await k.run(
        [
            exec_req.get("import marimo as mo; runs = []"),
            exec_req.get(f"path = mo.watch.file({str(tmp)!r})"),
            exec_req.get("path.read_text(); runs.append(1)"),
        ]
    )
    # Wait past several polls without touching the file.
    await asyncio.sleep(0.1)
    await k.run_stale_cells()

    assert not k.stderr.messages, k.stderr
    assert k.globals["runs"] == [1]


async def test_edit_before_watcher_starts_reruns_dependents(
    k: Kernel,
    exec_req: ExecReqProvider,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._runtime.threads import Thread
    from marimo._runtime.watch import _file

    monkeypatch.setattr(_file, "_TEST_SLEEP_INTERVAL", 0.01)
    # Hold the watcher thread so the edit lands before it runs.
    pending: list[Thread] = []
    monkeypatch.setattr(Thread, "start", lambda self: pending.append(self))
    tmp = tmp_path / "test.txt"
    tmp.write_text("0")
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(f"path = mo.watch.file({str(tmp)!r})"),
            exec_req.get("x = path.read_text()"),
        ]
    )
    tmp.write_text("1")
    mtime = tmp.stat().st_mtime + 1
    os.utime(tmp, (mtime, mtime))
    for thread in pending:
        threading.Thread.start(thread)
    await asyncio.sleep(0.1)
    await k.run_stale_cells()

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == "1"
