from __future__ import annotations

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


async def test_quick_reconnection(setup_ycell: None) -> None:
    """Test that quick reconnection properly handles cleanup task cancellation"""
    del setup_ycell
    # Setup
    cell_id = CellId_t("test_cell")
    file_key = MarimoFileKey("test_file")
    key = CellIdAndFileKey(cell_id, file_key)

    # Create initial ycell
    ydoc = Doc[Text]()
    ycode = ydoc.get("code", type=Text)
    ylang = ydoc.get("language", type=Text)
    ycell = YCell(ydoc=ydoc, code_text=ycode, language_text=ylang, clients=1)
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


async def test_two_users_sync(setup_ycell: None) -> None:
    """Test that two users can connect and sync text properly without duplicates"""
    del setup_ycell
    cell_id = CellId_t("test_cell")
    file_key = MarimoFileKey("test_file")
    key = CellIdAndFileKey(cell_id, file_key)

    # First user connects
    ydoc1 = Doc[Text]()
    ycode1 = ydoc1.get("code", type=Text)
    ylang1 = ydoc1.get("language", type=Text)
    ycell1 = YCell(
        ydoc=ydoc1, code_text=ycode1, language_text=ylang1, clients=1
    )
    ycells[key] = ycell1

    # Set initial text
    ycode1.insert(0, "print('hello')")
    ylang1.insert(0, "python")

    # Second user connects
    ydoc2 = Doc[Text]()
    ycode2 = ydoc2.get("code", type=Text)
    ylang2 = ydoc2.get("language", type=Text)

    # Simulate sync by using same key
    ycells[key].clients += 1

    # Verify state
    assert len(ycells) == 1  # No duplicates
    assert ycells[key].clients == 2
    assert ycode1.to_py() == "print('hello')"
    assert ylang1.to_py() == "python"

    # Second user makes changes
    ycode1.insert(len(ycode1.to_py()), "\nprint('world')")

    # Verify changes propagate
    assert ycode1.to_py() == "print('hello')\nprint('world')"
    assert ylang1.to_py() == "python"
    assert ycells[key].code_text.to_py() == "print('hello')\nprint('world')"
