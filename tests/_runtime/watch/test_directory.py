# Copyright 2026 Marimo. All rights reserved.
"""A watched directory's fingerprint tracks its entries."""

from __future__ import annotations

from pathlib import Path

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.watch._directory import DirectoryState
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

pytestmark = pytest.mark.usefixtures("cleanup_watchers")


def command(cell_id: int, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=CellId_t(str(cell_id)), code=code)


def test_walk_returns_path_roots(tmp_path: Path) -> None:
    (tmp_path / "added.txt").write_text("x")
    entries = list(DirectoryState(tmp_path).walk())
    assert [(str(root), dirs, files) for root, dirs, files in entries] == [
        (str(tmp_path), [], ["added.txt"])
    ]
    # NB. os.walk yields str roots before 3.12. The wrapper normalizes them.
    assert all(isinstance(root, Path) for root, _, _ in entries)


def test_repr_tracks_entries(tmp_path: Path) -> None:
    state = DirectoryState(tmp_path)
    before = repr(state)
    assert before == repr(state)
    (tmp_path / "added.txt").write_text("x")
    assert repr(state) != before


async def test_watched_directory_change_invalidates(tmp_path: Path) -> None:
    body = (
        "@mo.cache\ndef f(d):\n"
        "    return sorted(p.name for p in d.iterdir())\n"
        "result=f(directory)"
    )
    with mocked_kernel_session() as tk:
        k = tk.kernel
        await k.run(
            [
                command(0, "import marimo as mo"),
                command(1, f"directory=mo.watch.directory({str(tmp_path)!r})"),
                command(2, body),
            ]
        )
        assert k.globals["result"] == []
        (tmp_path / "added.txt").write_text("x")
        # Run the consumer without waiting for the watcher.
        await k.run([command(2, body)])
        assert k.globals["result"] == ["added.txt"]
