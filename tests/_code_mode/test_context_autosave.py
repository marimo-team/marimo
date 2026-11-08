# Copyright 2026 Marimo. All rights reserved.
"""Agent host edits persist through the real server's autosave path."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from marimo._runtime.commands import ExecuteScratchpadCommand
from marimo._server.scratchpad import (
    ScratchCellListener,
    extract_result,
    snapshot_for_scratchpad,
)
from tests._server.host.live import open_host

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("suffix", ["py", "md"])
async def test_host_edits_persist(tmp_path: Path, suffix: str) -> None:
    source = (
        "import marimo\napp = marimo.App()\n"
        if suffix == "py"
        else "---\ntitle: Test\nmarimo-version: 0.0.1\n---\n\n```python {.marimo}\n```\n"
    )
    filename = f"notebook.{suffix}"
    async with open_host(tmp_path, source, filename=filename) as (app, _, _):
        session = next(iter(app.state.session_manager.sessions.values()))
        listener = ScratchCellListener(run_id="autosave")
        cells, outputs = snapshot_for_scratchpad(session)
        code = (
            "import marimo._code_mode as cm\n"
            "async with cm.get_context() as ctx:\n"
            "    first = ctx.create_cell('first = 1')\n"
            "    second = ctx.create_cell('second = 2')\n"
            "async with cm.get_context() as ctx:\n"
            "    ctx.edit_cell(first, code='first = 100')\n"
            "    ctx.create_cell('third = 3')\n"
            "    ctx.delete_cell(second)\n"
            "for version in range(101, 105):\n"
            "    async with cm.get_context() as ctx:\n"
            "        ctx.edit_cell(first, code=f'first = {version}')\n"
        )
        with session.scoped(listener):
            session.put_control_request(
                ExecuteScratchpadCommand(
                    code=code,
                    notebook_cells=cells,
                    cell_outputs=outputs,
                    run_id="autosave",
                ),
                from_consumer_id=None,
            )
            await listener.wait(timeout=5)
            assert not listener.timed_out
            assert extract_result(session, listener).success
    # Shutdown drains queued saves, including slower earlier snapshots.
    contents = await asyncio.to_thread((tmp_path / filename).read_text)
    assert "first = 104" in contents
    assert "third = 3" in contents
    assert "second = 2" not in contents
    assert "_unparsable_cell" not in contents
