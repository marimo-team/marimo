# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.redirect_streams import redirect_streams
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._types.ids import CellId_t
from tests.conftest import _MockStream


def test_nested_from_scratch_swaps_cell_id() -> None:
    """When code_mode runs cells from the scratchpad, the inner cell's
    console output must be tagged with its own cell_id, not __scratch__."""
    stream = _MockStream()
    inner_id = CellId_t("real_cell")

    with redirect_streams(SCRATCH_CELL_ID, stream, None, None, None):
        with redirect_streams(inner_id, stream, None, None, None):
            assert stream.cell_id == inner_id
        assert stream.cell_id == SCRATCH_CELL_ID
