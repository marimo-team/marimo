# Copyright 2025 Marimo. All rights reserved.
import asyncio
from pathlib import Path

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


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
