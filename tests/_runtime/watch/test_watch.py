# Copyright 2025 Marimo. All rights reserved.
import asyncio
from pathlib import Path

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


@pytest.mark.flaky(reruns=5)
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
                mo.watch._file._TEST_SLEEP_INTERVAL = 0.01
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
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])

    assert not k.stdout.messages, k.stdout
    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == "1"


@pytest.mark.flaky(reruns=5)
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
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == b"000"


@pytest.mark.flaky(reruns=5)
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
    await asyncio.sleep(0.02)
    # Flakey in CI 3.13
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == 3


@pytest.mark.flaky(reruns=5)
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
                mo.watch._directory._TEST_SLEEP_INTERVAL = 0.01
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
    await asyncio.sleep(0.02)
    # Flakey in CI 3.13
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])
    await asyncio.sleep(0.02)
    await k.run([])

    assert not k.stderr.messages, k.stderr
    assert k.globals["x"] == 1


async def test_file_same_cell_access_raises_error(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test that accessing watched file in same cell raises RuntimeError."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp = Path("{test_file.as_posix()}")'),
            exec_req.get(
                """
                path = mo.watch.file(tmp)
                try:
                    path.read_text()
                    result = "fail"
                except RuntimeError as e:
                    result = "pass"
                    msg = str(e)
                """
            ),
        ]
    )

    assert k.globals["result"] == "pass"
    assert (
        "Accessing or modifying a watched value in the cell that created it is not allowed"
        in k.globals["msg"]
    )


async def test_file_same_cell_write_raises_error(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test write operations in same cell raise RuntimeError."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"content")

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp = Path("{test_file.as_posix()}")'),
            exec_req.get(
                """
                path = mo.watch.file(tmp)
                errors = []
                try:
                    path.write_text("new")
                except RuntimeError:
                    errors.append("write_text")
                try:
                    path.write_bytes(b"new")
                except RuntimeError:
                    errors.append("write_bytes")
                """
            ),
        ]
    )

    assert k.globals["errors"] == ["write_text", "write_bytes"]


async def test_file_same_cell_methods_raise_error(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test various file methods in same cell raise RuntimeError."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp = Path("{test_file.as_posix()}")'),
            exec_req.get(
                """
                path = mo.watch.file(tmp)
                errors = []
                for method in ["read_bytes", "exists", "name"]:
                    try:
                        if method == "name":
                            _ = path.name
                        else:
                            getattr(path, method)()
                    except RuntimeError:
                        errors.append(method)
                """
            ),
        ]
    )

    assert k.globals["errors"] == ["read_bytes", "exists", "name"]


async def test_directory_same_cell_methods_raise_error(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test directory methods in same cell raise RuntimeError."""
    k = execution_kernel

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp = Path("{tmp_path.as_posix()}")'),
            exec_req.get(
                """
                path = mo.watch.directory(tmp)
                errors = []
                for method in ["walk", "iterdir", "glob", "rglob"]:
                    try:
                        if method in ["glob", "rglob"]:
                            list(getattr(path, method)('*'))
                        else:
                            list(getattr(path, method)())
                    except RuntimeError:
                        errors.append(method)
                """
            ),
        ]
    )

    assert k.globals["errors"] == ["walk", "iterdir", "glob", "rglob"]


async def test_access_different_cell_works(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test accessing watched values in different cells works."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    (tmp_path / "a.txt").write_text("a")

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp_file = Path("{test_file.as_posix()}")'),
            exec_req.get(f'tmp_dir = Path("{tmp_path.as_posix()}")'),
            exec_req.get("file_watch = mo.watch.file(tmp_file)"),
            exec_req.get("dir_watch = mo.watch.directory(tmp_dir)"),
            exec_req.get("file_content = file_watch.read_text()"),
            exec_req.get("dir_files = [f.name for f in dir_watch.iterdir()]"),
        ]
    )

    assert k.globals["file_content"] == "content"
    assert "a.txt" in k.globals["dir_files"]


async def test_file_hash_property(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test _hash property uses usedforsecurity=False."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    await k.run(
        [
            exec_req.get(
                "import marimo as mo; from pathlib import Path; import hashlib"
            ),
            exec_req.get(f'tmp = Path("{test_file.as_posix()}")'),
            exec_req.get("path = mo.watch.file(tmp)"),
            exec_req.get(
                """
                expected = hashlib.sha256(tmp.read_bytes(), usedforsecurity=False).hexdigest()
                has_hash = expected in repr(path)
                """
            ),
        ]
    )

    assert k.globals["has_hash"] is True


async def test_write_debouncing(
    execution_kernel: Kernel, exec_req: ExecReqProvider, tmp_path: Path
) -> None:
    """Test write operations set debounce flag."""
    k = execution_kernel
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial")

    await k.run(
        [
            exec_req.get("import marimo as mo; from pathlib import Path"),
            exec_req.get(f'tmp = Path("{test_file.as_posix()}")'),
            exec_req.get("path = mo.watch.file(tmp)"),
            exec_req.get(
                "path.write_text('new'); debounced_text = path._debounced"
            ),
            exec_req.get(
                "path.write_bytes(b'newer'); debounced_bytes = path._debounced"
            ),
        ]
    )

    assert k.globals["debounced_text"] is True
    assert k.globals["debounced_bytes"] is True
