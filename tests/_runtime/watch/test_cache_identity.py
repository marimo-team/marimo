# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("cleanup_watchers")


@pytest.mark.parametrize("method", ["read_text", "read_bytes"])
async def test_cache_distinguishes_watched_files(
    k: Kernel,
    exec_req: ExecReqProvider,
    tmp_path: Path,
    method: str,
) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_bytes(b"alpha")
    right.write_bytes(b"beta")
    producer = exec_req.get(
        f"""
        values = [
            object(),
            mo.watch.file({str(left)!r}).{method}(),
            mo.watch.file({str(right)!r}).{method}(),
        ]
        """
    )
    consumer = exec_req.get(
        """
        @mo.cache
        def read_pair():
            return tuple(values[1:])
        result = read_pair()
        """
    )
    await k.run([exec_req.get("import marimo as mo"), producer, consumer])
    expected = (
        ("alpha", "beta") if method == "read_text" else (b"alpha", b"beta")
    )
    assert k.globals["result"] == expected

    left.write_bytes(b"beta")
    right.write_bytes(b"alpha")
    await k.run([producer, consumer])

    assert not k.stderr.messages, k.stderr
    assert tuple(k.globals["values"][1:]) == expected[::-1]
    assert k.globals["result"] == expected[::-1]
