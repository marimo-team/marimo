import asyncio
from typing import AsyncGenerator

import pytest
from pycrdt import Doc, Text

from marimo._server.api.endpoints.ws import (
    CellIdAndFileKey,
    YCell,
    clean_cell,
    ycells,
)
from marimo._server.file_router import MarimoFileKey
from marimo._types.ids import CellId_t


@pytest.fixture  # type: ignore
async def setup_ycell() -> AsyncGenerator[None, None]:
    """Setup and teardown for ycell tests"""
    # Clear any existing ycells
    ycells.clear()
    yield
    # Cleanup after test
    ycells.clear()


@pytest.mark.asyncio  # type: ignore
@pytest.mark.usefixtures("setup_ycell")  # type: ignore
async def test_quick_reconnection() -> None:
    """Test that quick reconnection properly handles cleanup task cancellation"""
    # Setup
    cell_id = CellId_t("test_cell")
    file_key = MarimoFileKey("test_file")
    key = CellIdAndFileKey(cell_id, file_key)

    # Create initial ycell
    ydoc = Doc[Text]()
    ycell = YCell(ydoc=ydoc, clients=1)
    ycells[key] = ycell

    # Start cleanup task
    cleanup_task = asyncio.create_task(clean_cell(key))

    # Simulate quick reconnection by creating a new client before cleanup finishes
    ycells[key].clients += 1

    # Cancel cleanup task (simulating what happens in ycell_provider)
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Verify state
    assert len(ycells) == 1
    assert ycells[key].clients == 2  # Original client + reconnected client
